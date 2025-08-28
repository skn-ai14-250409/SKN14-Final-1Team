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

from dotenv import load_dotenv
load_dotenv()


class GoogleAPIDocumentProcessor:
    def __init__(self,
                 api_data_dir: str = "./GOOGLE_API_DATA",
                 db_dir: str = "./chroma_google_api_db"):
        self.api_data_dir = Path(api_data_dir)
        self.db_dir = db_dir
        self.documents: List[Document] = []
        self.vectorstore: Optional[Chroma] = None
        self.embedding_model: Optional[HuggingFaceEmbeddings] = None

    def get_api_tag_from_path(self,path: str) -> str:
       folder = os.path.basename(os.path.dirname(path))
       if folder.endswith("_docs_crawled"):
         return folder.replace("_docs_crawled", "")
       return folder

    def _extract_source_url(self, content: str) -> str:
        pattern = r'SourceURL:\s*(https?://[^\s\n]+)'
        match = re.search(pattern, content)
        if match:
            return match.group(1)
        return ""

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
                tag = self.get_api_tag_from_path(file_path)

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
                    print(source_url)
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
        self.embedding_model = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={'device': 'cuda'},
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
        )

        # 나머지 배치를 병렬 처리
        batches = [self.documents[i:i + batch_size] for i in range(batch_size, len(self.documents), batch_size)]

        def add_batch(batch):
            self.vectorstore.add_documents(batch)
            return len(batch)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(add_batch, batch) for batch in batches]
            for f in tqdm(as_completed(futures), total=len(futures), desc="임베딩 및 DB 저장 중"):
                _ = f.result()

        print(f"✅ 벡터 저장소 생성 완료 ({self.db_dir})")


if __name__ == "__main__":
    try:
        # 데이터가 저장된 상위 폴더 및 DB를 저장할 경로를 지정
        processor = GoogleAPIDocumentProcessor(
            api_data_dir='../GOOGLE_API_DATA',
            db_dir='./chroma_google_api_db'
        )
        # DB 구축 실행
        print("=" * 60)
        print("🚀 API 문서 벡터 DB 구축 시작")
        print("=" * 60)

        processor.load_api_documents()
        processor.initialize_vectorstore_parallel()

        print("\n" + "=" * 60)
        print("✅ 모든 작업이 완료되었습니다.")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"💥 시스템 실행 중 심각한 오류 발생: {e}")
