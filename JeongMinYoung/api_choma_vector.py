import os
import json
import torch
import re
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from tqdm import tqdm


class GoogleAPIDocumentProcessor:
    def __init__(self,
                 api_data_dir: str = "./GOOGLE_API_DATA",
                 db_dir: str = "./chroma_google_api_db_gpt"):
        self.api_data_dir = Path(api_data_dir)
        self.db_dir = db_dir
        self.documents: List[Document] = []
        self.vectorstore: Optional[Chroma] = None
        self.embedding_model: Optional[HuggingFaceEmbeddings] = None

    def _get_tag_from_path(self, file_path: Path) -> str:
        try:
            relative_path = file_path.relative_to(self.api_data_dir)
            if len(relative_path.parts) > 1:
                folder_name = relative_path.parts[0]
                return folder_name.split('_')[0]
        except ValueError:
            pass
        return None

    def _extract_source_url(self, content: str) -> str:
        pattern = r'Source\s+URL:\s*(https?://[^\s\n]+)'
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
                tag = self._get_tag_from_path(file_path)

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
                    print(f'chunk_id: {i}')
                    print(f'source: {source_url}')
                    print(f'tags: {tag}')
                    print(f'source_file: {file_path.name}')
                    documents.append(doc)

            except Exception as e:
                print(f"⚠️ {file_path} 파일 로드 중 오류 발생: {e}")

        self.documents = documents
        print(f"✅ 총 {len(documents)}개의 문서 청크를 로드했습니다.")
        return documents

    def initialize_vectorstore(self):
        if not self.documents:
            print("⚠️ 벡터 DB를 생성할 문서가 없습니다. `load_api_documents`를 먼저 실행해주세요.")
            return

        print("🔧 임베딩 모델 초기화 중... (BAAI/bge-m3)")
        self.embedding_model = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={'device': 'cuda' if torch.cuda.is_available() else 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )

        batch_size = 100
        first_batch = self.documents[:batch_size]
        self.vectorstore = Chroma.from_documents(
            documents=first_batch,
            embedding=self.embedding_model,
            persist_directory=self.db_dir,
        )

        for i in tqdm(range(batch_size, len(self.documents), batch_size), desc="임베딩 및 DB 저장 중"):
            batch = self.documents[i:i + batch_size]
            self.vectorstore.add_documents(batch)

        print(f"✅ 벡터 저장소 생성 완료 ({self.db_dir})")

    def build_database(self):
        print("=" * 60)
        print("🚀 API 문서 벡터 DB 구축 시작")
        print("=" * 60)

        self.load_api_documents()
        self.initialize_vectorstore()

        print("\n" + "=" * 60)
        print("✅ 모든 작업이 완료되었습니다.")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    try:
        processor = GoogleAPIDocumentProcessor(
            api_data_dir='../GOOGLE_API_DATA',
            db_dir='../chroma_google_api_db_gpt'
        )
        processor.build_database()

    except Exception as e:
        print(f"💥 시스템 실행 중 심각한 오류 발생: {e}")