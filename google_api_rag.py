import os
import re
import torch
from pathlib import Path
from typing import List, Optional
from tqdm import tqdm
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from concurrent.futures import ThreadPoolExecutor, as_completed


class GoogleAPIDocumentProcessor:
    def __init__(self,
                 api_data_dir: str = "./GOOGLE_API_DATA",
                 db_dir: str = "./chroma_google_api_db"):
        self.api_data_dir = Path(api_data_dir)
        self.db_dir = db_dir
        self.documents: List[Document] = []
        self.vectorstore: Optional[Chroma] = None
        self.embedding_model: Optional[HuggingFaceEmbeddings] = None

    def get_api_tag_from_path(self, path: str) -> str:
        folder = os.path.basename(os.path.dirname(path))
        if folder.endswith("_docs_crawled"):
            return folder.replace("_docs_crawled", "")
        return folder

    def _extract_source_url(self, content: str) -> str:
        pattern = r'(?i)Source\s*URL\s*:\s*(https?://\S+)'
        m = re.search(pattern, content)
        if m:
            return m.group(1).strip()
        head = content[:2048]
        m2 = re.search(pattern, head)
        return m2.group(1).strip() if m2 else ""

    def load_api_documents(self) -> List[Document]:
        documents = []

        if not self.api_data_dir.exists():
            print(f"⚠️ 데이터 디렉토리가 존재하지 않습니다: {self.api_data_dir}")
            return documents

        print(f"📂 API 데이터 로드 중 (.txt 파일만 탐색): {self.api_data_dir}")
        file_paths = list(self.api_data_dir.rglob("*.txt"))

        for file_path in file_paths:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                source_url = self._extract_source_url(content)
                tag = self.get_api_tag_from_path(str(file_path))  # str() 추가

                if tag is None:
                    continue

                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1200,
                    chunk_overlap=150,
                    separators=["\n\n", "\n", ". ", " ", ""]
                )
                chunks = text_splitter.split_text(content)

                for i, chunk in enumerate(chunks):
                    doc = Document(
                        page_content=chunk,
                        metadata={
                            'chunk_id': i,
                            'source': source_url,
                            'tags': tag,
                            'source_file': file_path.name,
                            'last_verified': '2025-08-19'
                        }
                    )
                    documents.append(doc)

            except Exception as e:
                print(f"⚠️ {file_path} 파일 로드 중 오류 발생: {e}")

        self.documents = documents
        print(f"✅ 총 {len(documents)}개의 문서 청크를 로드했습니다.")
        return documents

    def initialize_vectorstore_parallel(self, batch_size: int = 100, max_workers: int = 4):
        if not self.documents:
            print("⚠️ 벡터 DB를 생성할 문서가 없습니다. `load_api_documents`를 먼저 실행해주세요.")
            return

        print("🔧 임베딩 모델 초기화 중... (BAAI/bge-m3)")

        # GPU 사용 가능 여부 확인
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"📱 사용 중인 디바이스: {device}")

        self.embedding_model = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={'device': device},
            encode_kwargs={'normalize_embeddings': True}
        )

        if os.path.exists(self.db_dir) and any(Path(self.db_dir).iterdir()):
            print(f"💾 기존 벡터 저장소가 '{self.db_dir}'에 존재합니다.")
            user_input = input("덮어쓰시겠습니까? (y/n): ").lower()
            if user_input != 'y':
                print("작업을 취소합니다.")
                return
            else:
                import shutil
                shutil.rmtree(self.db_dir)
                print(f"🗑️ 기존 '{self.db_dir}' 폴더를 삭제했습니다.")

        print("💾 새 벡터 저장소 생성 중...")

        # 첫 배치로 DB 생성
        first_batch = self.documents[:batch_size]
        self.vectorstore = Chroma.from_documents(
            documents=first_batch,
            embedding=self.embedding_model,
            persist_directory=self.db_dir,
            collection_name="google_api_docs"  # 컬렉션 이름 명시
        )

        # 나머지 배치 처리
        remaining_docs = self.documents[batch_size:]
        if remaining_docs:
            batches = [remaining_docs[i:i + batch_size] for i in range(0, len(remaining_docs), batch_size)]

            for batch in tqdm(batches, desc="임베딩 및 DB 저장 중"):
                self.vectorstore.add_documents(batch)

        # 명시적으로 persist 호출 (중요!)
        self.vectorstore.persist()

        print(f"✅ 벡터 저장소 생성 완료 ({self.db_dir})")
        print(f"📊 저장된 문서 수: {self.vectorstore._collection.count()}")

    def verify_db(self):
        """DB가 제대로 생성되었는지 확인"""
        if os.path.exists(self.db_dir):
            print(f"\n🔍 DB 검증 중...")

            # 임베딩 모델 재초기화
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            embedding_model = HuggingFaceEmbeddings(
                model_name="BAAI/bge-m3",
                model_kwargs={'device': device},
                encode_kwargs={'normalize_embeddings': True}
            )

            # DB 로드
            loaded_db = Chroma(
                persist_directory=self.db_dir,
                embedding_function=embedding_model,
                collection_name="google_api_docs"
            )

            doc_count = loaded_db._collection.count()
            print(f"📚 DB에 저장된 문서 수: {doc_count}")

            # 샘플 쿼리 테스트
            if doc_count > 0:
                results = loaded_db.similarity_search("Google API", k=3)
                print(f"🔎 샘플 검색 결과: {len(results)}개 문서 검색됨")
                for i, doc in enumerate(results[:2], 1):
                    print(f"\n  [{i}] {doc.metadata.get('source_file', 'Unknown')}")
                    print(f"      Tag: {doc.metadata.get('tags', 'Unknown')}")
                    print(f"      내용 일부: {doc.page_content[:100]}...")

            return doc_count > 0
        else:
            print(f"❌ DB 디렉토리가 존재하지 않습니다: {self.db_dir}")
            return False


if __name__ == "__main__":
    try:
        processor = GoogleAPIDocumentProcessor(
            api_data_dir='../GOOGLE_API_DATA',
            db_dir='./chroma_google_api_db'
        )

        print("=" * 60)
        print("🚀 API 문서 벡터 DB 구축 시작")
        print("=" * 60)

        processor.load_api_documents()
        processor.initialize_vectorstore_parallel()

        # DB 검증
        processor.verify_db()

        print("\n" + "=" * 60)
        print("✅ 모든 작업이 완료되었습니다.")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"💥 시스템 실행 중 심각한 오류 발생: {e}")