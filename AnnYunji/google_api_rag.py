import os
import re
import torch
from pathlib import Path
from typing import List, Optional
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

from transformers import AutoTokenizer

MODEL_NAME = "BAAI/bge-m3"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

def token_len(text: str) -> int:
    return len(tokenizer(text, add_special_tokens=False)["input_ids"])

class GoogleAPIRAGSystem:
    def __init__(self,
                 api_data_dir: str = "./GOOGLE_API_DATA",
                 db_dir: str = "./chroma_google_api_db_gpt"):
        
        self.api_data_dir = Path(api_data_dir)
        self.db_dir = db_dir

        self.documents: List[Document] = []
        self.vectorstore: Optional[Chroma] = None
        self.embedding_model: Optional[HuggingFaceEmbeddings] = None
        

    def _clean_content(self, content: str) -> str:
        content = re.sub(r"이 페이지는 Cloud Translation API.*를 통해 번역되었습니다.\nSwitch to English", "", content)
        content = re.sub(r"도움이 되었나요?", "", content)
        content = re.sub(r"의견 보내기", "", content)
        content = re.sub(r"Send feedback", "", content)
        content = re.sub(r"bookmark_border", "", content)
    
        return content.strip()
        

    def load_api_documents(self) -> List[Document]:
        documents = []
        if not self.api_data_dir.exists():
            print(f"데이터 디렉토리가 존재하지 않습니다: {self.api_data_dir}")
            return documents

        print(f"API 데이터 로드 중 (하위 폴더 포함): {self.api_data_dir}")
        file_paths = list(self.api_data_dir.rglob("*.txt"))

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=900,            # 토큰 기준
            chunk_overlap=120,         # 토큰 기준
            length_function=token_len, # 토큰 단위 길이 함수
            separators=["\n\n--- 탭: ", "\n\n", "\n", ".\n", ".", " ", ""] # 큰 구조 → 문단 → 문장 → 단어
        )

        MAX_TOKENS = 8192  # bge-m3 입력 한도

        for file_path in file_paths:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                cleaned_content = self._clean_content(content)

                source_url = "N/A"
                first_line = content.split('\n', 1)[0]
                if first_line.startswith('Source URL: '):
                    source_url = first_line.replace('Source URL: ', '').strip()

                api_category = file_path.parent.name.split('_')[0]

                chunks = text_splitter.split_text(cleaned_content)

                for i, chunk in enumerate(chunks):
                    if token_len(chunk) > MAX_TOKENS:
                        print(f"청크가 {token_len(chunk)} 토큰으로 너무 큽니다. 잘라냅니다...")
                        sub_chunks = text_splitter.split_text(chunk)
                        for j, sub in enumerate(sub_chunks):
                            if token_len(sub) <= MAX_TOKENS:
                                doc = Document(
                                    page_content=sub,
                                    metadata={
                                        'chunk_id': f"{i}-{j}",
                                        'sources': source_url,
                                        'api_category': api_category,
                                        'source_file': str(file_path.relative_to(self.api_data_dir)),
                                    }
                                )
                                documents.append(doc)
                        continue

                    doc = Document(
                        page_content=chunk,
                        metadata={
                            'chunk_id': i,
                            'sources': source_url,
                            'api_category': api_category,
                            'source_file': str(file_path.relative_to(self.api_data_dir)),
                        }
                    )
                    documents.append(doc)

            except Exception as e:
                print(f"{file_path} 파일 로드 중 오류 발생: {e}")

        self.documents = documents
        print(f"총 {len(documents)}개의 문서 청크를 로드했습니다.")
        return documents

    def initialize_vectorstore(self):
        print("임베딩 모델 초기화 중... (BAAI/bge-m3)")
        self.embedding_model = HuggingFaceEmbeddings(
            # model_name="BAAI/bge-m3",
            model_name=MODEL_NAME,
            model_kwargs={'device': 'cuda' if torch.cuda.is_available() else 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )

        collection_name = Path(self.db_dir).name
        
        if os.path.exists(self.db_dir) and any(Path(self.db_dir).iterdir()):
            print(f"기존 벡터 저장소 로드 중: {self.db_dir}")
            self.vectorstore = Chroma(
                persist_directory=self.db_dir,
                embedding_function=self.embedding_model,
                collection_name=collection_name 
            )
        else:
            if not self.documents:
                print("벡터 DB를 생성할 문서가 없습니다. 데이터 디렉토리를 확인해주세요.")
                return

            print("새 벡터 저장소 생성 중...")
            self.vectorstore = Chroma.from_documents(
                documents=self.documents,
                embedding=self.embedding_model,
                persist_directory=self.db_dir,
                collection_name=collection_name
            )
        print(f"벡터 저장소 준비 완료 ({self.db_dir})")


# --- 메인 실행 코드 ---
if __name__ == "__main__":
    
    try:
        ingester = GoogleAPIRAGSystem(
            api_data_dir='../GOOGLE_API_DATA/calendar_docs_crawled',
            db_dir='./chroma_google_api_db_calendar3'
        )
        
        print("구글 API 문서 벡터 DB 인덱싱 시작")
        
        ingester.load_api_documents()
        ingester.initialize_vectorstore()
        
        print("모든 문서가 벡터 DB에 성공적으로 저장")
        
        # 조회
        print("\n--- ChromaDB 저장 정보 ---")
        print(f"총 {ingester.vectorstore._collection.count()}개의 문서가 "
              f"'{os.path.abspath(ingester.db_dir)}' 경로에 저장되었습니다.")
        
    except Exception as e:
        print(f"시스템 실행 중 오류 발생: {e}")