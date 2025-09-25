import re
import torch
from pathlib import Path
from typing import List, Optional
from tqdm import tqdm
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter


class GoogleAPIDocumentProcessor:
    """
    Google API 문서를 로드하고 벡터 DB(Chroma)에 저장하는 프로세서 클래스
    """

    def __init__(
        self,
        api_data_dir: str = "./GOOGLE_API_DATA",
        db_dir: str = "./chroma_text_api",
        collection_name: str = "google_api_docs",
        embedding_model_name: str = "BAAI/bge-m3",
    ):
        self.api_data_dir = Path(api_data_dir)
        self.db_dir = Path(db_dir)
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model_name

        self.documents: List[Document] = []
        self.vectorstore: Optional[Chroma] = None
        self.embedding_model: Optional[HuggingFaceEmbeddings] = None

    # ============================================================
    # 유틸 메서드
    # ============================================================

    @staticmethod
    def _extract_source_url(content: str) -> str:
        """문서에서 Source URL 추출"""
        pattern = r"(?i)Source\s*URL\s*:\s*(https?://\S+)"
        match = re.search(pattern, content)
        if match:
            return match.group(1).strip()
        else:
            return ""

    @staticmethod
    def _get_api_tag_from_path(path: Path) -> str:
        """파일 경로에서 API 태그 추출"""
        folder = path.parent.name
        return (
            folder.replace("_docs_crawled", "")
            if folder.endswith("_docs_crawled")
            else folder
        )

    @staticmethod
    def _get_device() -> str:
        """가장 적합한 디바이스 선택"""
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"

    # ============================================================
    # 문서 로드 및 처리
    # ============================================================

    def load_api_documents(self) -> List[Document]:
        """데이터 디렉토리에서 txt 문서를 읽고 청크 단위 Document 리스트 생성"""
        if not self.api_data_dir.exists():
            print(f"데이터 디렉토리가 존재하지 않습니다: {self.api_data_dir}")
            return []

        print(f"API 문서 로드 중: {self.api_data_dir}")
        file_paths = list(self.api_data_dir.rglob("*.txt"))
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1200, chunk_overlap=150, separators=["\n\n", "\n", ". ", " ", ""]
        )

        documents = []
        for file_path in file_paths:
            try:
                content = file_path.read_text(encoding="utf-8")
                source_url = self._extract_source_url(content)
                tag = self._get_api_tag_from_path(file_path)

                chunks = text_splitter.split_text(content)
                for i, chunk in enumerate(chunks):
                    documents.append(
                        Document(
                            page_content=chunk,
                            metadata={
                                "chunk_id": i,
                                "source": source_url,
                                "tags": tag,
                                "source_file": file_path.name,
                                "last_verified": "2025-08-19",
                            },
                        )
                    )
            except Exception as e:
                print(f"⚠️ {file_path} 로드 중 오류 발생: {e}")

        self.documents = documents
        print(f"✅ 총 {len(documents)}개의 문서 청크 로드 완료")
        return documents

    # ============================================================
    # 벡터 DB 구축
    # ============================================================

    def _init_embedding_model(self):
        """임베딩 모델 초기화"""
        if self.embedding_model is None:
            device = self._get_device()
            print(
                f"임베딩 모델 초기화 ({self.embedding_model_name}, device={device})..."
            )
            self.embedding_model = HuggingFaceEmbeddings(
                model_name=self.embedding_model_name,
                model_kwargs={"device": device},
                encode_kwargs={"normalize_embeddings": True},
            )

    def initialize_vectorstore(self, batch_size: int = 100):
        """문서를 벡터화하여 DB 생성"""
        if not self.documents:
            print("문서가 없습니다. 먼저 `load_api_documents()`를 실행하세요.")
            return

        self._init_embedding_model()

        # 첫 배치로 DB 생성
        first_batch, remaining_docs = (
            self.documents[:batch_size],
            self.documents[batch_size:],
        )
        self.vectorstore = Chroma.from_documents(
            documents=first_batch,
            embedding=self.embedding_model,
            persist_directory=str(self.db_dir),
            collection_name=self.collection_name,
        )

        # 나머지 배치 추가
        for batch in tqdm(
            [
                remaining_docs[i : i + batch_size]
                for i in range(0, len(remaining_docs), batch_size)
            ],
            desc="임베딩 및 저장",
        ):
            self.vectorstore.add_documents(batch)

        print(f"벡터 저장소 생성 완료: {self.db_dir}")
        print(f"저장된 문서 수: {self.vectorstore._collection.count()}")

    # ============================================================
    # DB 검증
    # ============================================================

    def verify_db(self) -> bool:
        """DB 유효성 검증 및 샘플 검색"""
        if not self.db_dir.exists():
            print(f"DB 디렉토리 없음: {self.db_dir}")
            return False

        self._init_embedding_model()
        loaded_db = Chroma(
            persist_directory=str(self.db_dir),
            embedding_function=self.embedding_model,
            collection_name=self.collection_name,
        )

        doc_count = loaded_db._collection.count()
        print(f"DB 저장 문서 수: {doc_count}")

        if doc_count > 0:
            results = loaded_db.similarity_search("Google API", k=3)
            print(f"샘플 검색 결과: {len(results)}개")
            for i, doc in enumerate(results[:2], 1):
                print(f"\n  [{i}] {doc.metadata.get('source_file', 'Unknown')}")
                print(f"      Tag: {doc.metadata.get('tags', 'Unknown')}")
                print(f"      내용 일부: {doc.page_content[:100]}...")

        return doc_count > 0


# ============================================================
# 실행 스크립트
# ============================================================

if __name__ == "__main__":
    processor = GoogleAPIDocumentProcessor()

    print("=" * 60)
    print("Google API 문서 벡터 DB 구축 시작")
    print("=" * 60)

    processor.load_api_documents()
    processor.initialize_vectorstore()
    processor.verify_db()

    print("\n" + "=" * 60)
    print("✅ 모든 작업 완료")
    print("=" * 60 + "\n")
