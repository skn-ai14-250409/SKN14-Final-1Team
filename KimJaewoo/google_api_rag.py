import os
import json
import torch
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from tqdm import tqdm


class GoogleAPIDocumentProcessor:
    """구글 API 문서를 처리하고 벡터 데이터베이스를 구축하는 시스템"""

    def __init__(self,
                 api_data_dir: str = "./GOOGLE_API_DATA",
                 db_dir: str = "./chroma_google_api_db_gpt"):
        """
        Args:
            api_data_dir: 구글 API 원본 데이터 디렉토리. 하위 폴더명을 'tags' 메타데이터로 사용합니다.
            db_dir: Chroma DB 저장 경로
        """
        self.api_data_dir = Path(api_data_dir)
        self.db_dir = db_dir

        # 컴포넌트 초기화
        self.documents: List[Document] = []
        self.vectorstore: Optional[Chroma] = None
        self.embedding_model: Optional[HuggingFaceEmbeddings] = None

    def _get_tag_from_path(self, file_path: Path) -> str:
        """
        파일 경로의 상위 폴더명을 태그(대분류)로 추출합니다.

        예시:
        - ./GOOGLE_API_DATA/gmail/send_email.txt -> 'gmail'
        - ./GOOGLE_API_DATA/drive/list_files.txt -> 'drive'
        - ./GOOGLE_API_DATA/some_other_doc.txt -> 'general'
        """
        try:
            relative_path = file_path.relative_to(self.api_data_dir)
            if len(relative_path.parts) > 1:
                return relative_path.parts[0]
        except ValueError:
            pass
        return 'general'

    def load_api_documents(self) -> List[Document]:
        """
        구글 API 원문(.txt) 문서들을 로드하고 Document 객체로 변환합니다.
        """
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

                # 요구사항에 맞게 청킹 방식 수정
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1200,
                    chunk_overlap=150,
                    separators=["\n\n", "\n", ". ", " ", ""]  # 의미 단위 보존 시도
                )
                chunks = text_splitter.split_text(content)

                for i, chunk in enumerate(chunks):
                    # 요구사항에 맞게 최종 메타데이터 구조 수정
                    doc = Document(
                        page_content=chunk,
                        metadata={
                            'chunk_id': i,
                            'source': str(file_path.relative_to(self.api_data_dir)),
                            'tags': self._get_tag_from_path(file_path),
                            'source_file': file_path.name,
                            'last_verified': datetime.fromtimestamp(file_path.stat().st_mtime).strftime('%Y-%m-%d')
                        }
                    )
                    documents.append(doc)

            except Exception as e:
                print(f"⚠️ {file_path} 파일 로드 중 오류 발생: {e}")

        self.documents = documents[:1000]
        print(f"✅ [테스트 모드] 총 {len(documents)}개의 청크 중 1000개만 사용합니다.")

        print(f"✅ 총 {len(documents)}개의 문서 청크를 로드했습니다.")
        return documents

    def initialize_vectorstore(self):
        """벡터 저장소 초기화 및 문서 임베딩"""
        if not self.documents:
            print("⚠️ 벡터 DB를 생성할 문서가 없습니다. `load_api_documents`를 먼저 실행해주세요.")
            return

        print("🔧 임베딩 모델 초기화 중... (BAAI/bge-m3)")
        self.embedding_model = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={'device': 'cuda' if torch.cuda.is_available() else 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )

        if os.path.exists(self.db_dir) and any(Path(self.db_dir).iterdir()):
            print(f"💾 기존 벡터 저장소가 '{self.db_dir}'에 존재합니다.")
            user_input = input("덮어쓰시겠습니까? (y/n): ").lower()
            if user_input != 'y':
                print("작업을 취소합니다.")
                return
            else:
                # 기존 폴더 삭제
                import shutil
                shutil.rmtree(self.db_dir)
                print(f"🗑️ 기존 '{self.db_dir}' 폴더를 삭제했습니다.")

        print("💾 새 벡터 저장소 생성 중... (진행률 표시)")

        # 첫 번째 청크로 DB 초기화
        self.vectorstore = Chroma.from_documents(
            documents=[self.documents[0]],  # 첫 문서 하나로만 초기화
            embedding=self.embedding_model,
            persist_directory=self.db_dir,
        )

        # 나머지 문서를 tqdm으로 진행률을 보며 추가
        batch_size = 100  # 한 번에 100개씩 추가
        for i in tqdm(range(1, len(self.documents), batch_size), desc="임베딩 및 DB 저장 중"):
            batch = self.documents[i:i + batch_size]
            self.vectorstore.add_documents(batch)

        print(f"✅ 벡터 저장소 생성 완료 ({self.db_dir})")

    def build_database(self):
        """전체 파이프라인 실행: 문서 로드 및 벡터 DB 구축"""
        print("=" * 60)
        print("🚀 API 문서 벡터 DB 구축 시작")
        print("=" * 60)

        self.load_api_documents()
        self.initialize_vectorstore()

        print("\n" + "=" * 60)
        print("✅ 모든 작업이 완료되었습니다.")
        print("=" * 60 + "\n")


# --- 메인 실행 코드 ---
if __name__ == "__main__":
    # 이 스크립트는 이제 문서를 처리하고 벡터 DB를 생성하는 역할만 합니다.
    try:
        # 데이터가 저장된 상위 폴더 및 DB를 저장할 경로를 지정합니다.
        processor = GoogleAPIDocumentProcessor(
            api_data_dir='../GOOGLE_API_DATA',
            db_dir='../chroma_google_api_db_gpt'
        )
        # DB 구축 실행
        processor.build_database()

    except Exception as e:
        print(f"💥 시스템 실행 중 심각한 오류 발생: {e}")