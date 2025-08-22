import os
import json
import torch
from pathlib import Path
from typing import List, Tuple, Optional
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
import openai
from dotenv import load_dotenv


class GoogleAPIRAGSystem:
    """구글 API 문서 검색을 위한 RAG 시스템 (GPT-4o 전용)"""

    def __init__(self,
                 api_data_dir: str = "./GOOGLE_API_DATA",
                 db_dir: str = "./chroma_google_api_db_gpt",
                 openai_api_key: str = None):
        """
        Args:
            api_data_dir: 구글 API 원본 데이터 디렉토리. 하위 폴더명을 API 카테고리로 사용합니다.
            db_dir: Chroma DB 저장 경로
            openai_api_key: OpenAI API 키 (필수)
        """
        if not openai_api_key:
            raise ValueError("OpenAI API 키가 필요합니다. `openai_api_key` 인자를 제공해주세요.")

        self.api_data_dir = Path(api_data_dir)
        self.db_dir = db_dir

        # OpenAI 설정
        os.environ["OPENAI_API_KEY"] = openai_api_key
        openai.api_key = openai_api_key

        # 컴포넌트 초기화
        self.documents: List[Document] = []
        self.vectorstore: Optional[Chroma] = None
        self.retriever = None
        self.embedding_model: Optional[HuggingFaceEmbeddings] = None
        self.llm: Optional[ChatOpenAI] = None

    def _get_category_from_path(self, file_path: Path) -> str:
        """
        파일 경로의 부모 디렉토리 이름으로부터 API 카테고리를 추출합니다.
        이 방식은 메타데이터를 파일의 내용이 아닌 폴더 구조에 따라 고정시킵니다.

        예시:
        - ./GOOGLE_API_DATA/gmail/send_email.txt -> 'gmail'
        - ./GOOGLE_API_DATA/drive/list_files.txt -> 'drive'
        - ./GOOGLE_API_DATA/some_other_doc.txt -> 'general'
        """
        try:
            relative_path = file_path.relative_to(self.api_data_dir)
            # 상대 경로의 첫 번째 부분이 카테고리 (폴더명)
            if len(relative_path.parts) > 1:
                return relative_path.parts[0]
        except ValueError:
            # api_data_dir 외부에 있는 경우 (일반적으로 발생하지 않음)
            pass
        # 파일이 데이터 루트 디렉토리에 직접 있을 경우 'general'로 분류
        return 'general'

    def load_api_documents(self) -> List[Document]:
        """
        구글 API 원문 문서들을 로드하고 Document 객체로 변환합니다.
        하위 디렉토리를 탐색하며, 디렉토리 이름을 API 카테고리로 사용합니다.
        """
        documents = []

        if not self.api_data_dir.exists():
            print(f"⚠️ 데이터 디렉토리가 존재하지 않습니다: {self.api_data_dir}")
            self.documents = documents
            return documents

        print(f"📂 API 데이터 로드 중 (하위 폴더 포함): {self.api_data_dir}")
        file_paths = list(self.api_data_dir.rglob("*.txt")) + list(self.api_data_dir.rglob("*.json"))

        for file_path in file_paths:
            try:
                content = ""
                if file_path.suffix == '.txt':
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                elif file_path.suffix == '.json':
                    with open(file_path, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    content = json.dumps(json_data, ensure_ascii=False, indent=2)

                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1500, chunk_overlap=300
                )
                chunks = text_splitter.split_text(content)

                for i, chunk in enumerate(chunks):
                    # 메타데이터 구조를 통일하고, 폴더명으로 카테고리를 고정
                    doc = Document(
                        page_content=chunk,
                        metadata={
                            'source_file': str(file_path.relative_to(self.api_data_dir)),
                            'chunk_id': i,
                            'api_category': self._get_category_from_path(file_path)
                        }
                    )
                    documents.append(doc)

            except Exception as e:
                print(f"⚠️ {file_path} 파일 로드 중 오류 발생: {e}")

        self.documents = documents
        print(f"✅ 총 {len(documents)}개의 문서 청크를 로드했습니다.")
        return documents

    def initialize_vectorstore(self):
        """벡터 저장소 초기화 및 문서 임베딩"""
        print("🔧 임베딩 모델 초기화 중... (BAAI/bge-m3)")
        self.embedding_model = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={'device': 'cuda' if torch.cuda.is_available() else 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )

        if os.path.exists(self.db_dir) and any(Path(self.db_dir).iterdir()):
            print(f"💾 기존 벡터 저장소 로드 중: {self.db_dir}")
            self.vectorstore = Chroma(
                persist_directory=self.db_dir,
                embedding_function=self.embedding_model
            )
        else:
            if not self.documents:
                self.load_api_documents()
            if not self.documents:
                print("⚠️ 벡터 DB를 생성할 문서가 없습니다. 데이터 디렉토리를 확인해주세요.")
                return

            print("💾 새 벡터 저장소 생성 중...")
            self.vectorstore = Chroma.from_documents(
                documents=self.documents,
                embedding=self.embedding_model,
                persist_directory=self.db_dir,
            )

        self.retriever = self.vectorstore.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={"k": 5, "score_threshold": 0.3}
        )
        print(f"✅ 벡터 저장소 준비 완료 ({self.db_dir})")

    def initialize_llm(self):
        """LLM 모델(GPT-4o) 초기화"""
        print("🤖 GPT-4o 모델 초기화 중...")
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.7, max_tokens=1024)
        print("✅ GPT-4o 모델 준비 완료")

    def format_docs_for_context(self, docs: List[Document]) -> str:
        """검색된 문서를 컨텍스트로 포맷팅"""
        formatted = []
        for i, doc in enumerate(docs, 1):
            content = f"[참고 자료 {i}]\n"
            content += f"- 출처: {doc.metadata.get('source_file', 'N/A')}\n"
            content += f"- 카테고리: {doc.metadata.get('api_category', 'N/A')}\n"
            content += f"- 내용: {doc.page_content}"
            formatted.append(content)
        return "\n\n---\n\n".join(formatted)

    def generate_response(self, query: str) -> Tuple[List[Document], str]:
        """사용자 질문에 대한 응답 생성"""
        if not self.llm or not self.retriever:
            raise RuntimeError("시스템이 초기화되지 않았습니다. `initialize_all()`을 먼저 실행해주세요.")

        # 1. 관련 문서 검색
        docs = self.retriever.invoke(query)

        # 2. 컨텍스트 생성
        context = self.format_docs_for_context(docs)

        # 3. LLM에 전달할 메시지 구성
        messages = [
            SystemMessage(content="""당신은 구글 API 전문가입니다. 개발자들에게 정확하고 실용적인 답변을 제공하세요.
            제공된 '참고 자료'를 바탕으로 답변해야 하며, 자료에 없는 내용은 추측하지 마세요.
            코드 예시와 함께 단계별로 명확하게 설명해주세요."""),
            HumanMessage(content=f"참고 자료:\n{context}\n\n---\n질문: {query}\n\n위 참고 자료를 바탕으로 질문에 답변해주세요:")
        ]

        # 4. 응답 생성
        response = self.llm.invoke(messages)
        return docs, response.content

    def initialize_all(self):
        """전체 시스템 초기화 (문서 로드, 벡터DB, LLM)"""
        print("=" * 60)
        print("🚀 Google API RAG 시스템 초기화 시작 (GPT-4o 전용)")
        print("=" * 60)

        self.load_api_documents()
        self.initialize_vectorstore()
        self.initialize_llm()

        print("\n" + "=" * 60)
        print("✅ 초기화 완료! 시스템을 사용할 준비가 되었습니다.")
        print("=" * 60 + "\n")

    def search(self, query: str, verbose: bool = True) -> str:
        """API 검색 및 응답 제공을 위한 메인 메소드"""
        docs, response = self.generate_response(query)

        if verbose:
            print("\n" + "=" * 60)
            print(f"🔍 질문: {query}")
            print("=" * 60)

            print("\n📚 검색된 관련 문서 (상위 3개):")
            if not docs:
                print("  관련 문서를 찾지 못했습니다.")
            for i, doc in enumerate(docs[:3], 1):
                category = doc.metadata.get('api_category', 'N/A')
                source = doc.metadata.get('source_file', 'N/A')
                print(f"\n  [{i}] 출처: {source} (카테고리: {category})")
                print(f"      내용 미리보기: {doc.page_content[:100].replace(os.linesep, ' ')}...")

            print("\n" + "-" * 60)
            print("💡 생성된 답변:")
            print("-" * 60)
            print(response)
            print("=" * 60 + "\n")

        return response


# --- 메인 실행 코드 ---
if __name__ == "__main__":
    # .env 파일에서 환경 변수 로드
    load_dotenv()

    # OpenAI API 키 가져오기
    # 1. 환경변수에서 OPENAI_API_KEY를 찾습니다.
    # 2. .env 파일이 있다면 거기서 찾습니다.
    # 3. 모두 없다면 사용자에게 직접 입력을 요청할 수 있습니다 (여기서는 오류 발생).
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API 키를 찾을 수 없습니다. 'OPENAI_API_KEY' 환경 변수를 설정하거나 .env 파일을 생성해주세요.")

    # RAG 시스템 인스턴스 생성 및 초기화
    try:
        rag_system = GoogleAPIRAGSystem(
            api_data_dir='../GOOGLE_API_DATA',
            db_dir='../chroma_google_api_db_gpt',
            openai_api_key=api_key
        )
        rag_system.initialize_all()

        # 대화형 모드로 질문/답변 시작
        print("💬 대화형 모드가 시작되었습니다. 종료하려면 'quit' 또는 'exit'를 입력하세요.")
        while True:
            user_query = input("\n❓ 질문: ").strip()
            if user_query.lower() in ['quit', 'exit', '종료']:
                print("👋 프로그램을 종료합니다.")
                break
            if not user_query:
                continue

            rag_system.search(user_query)

    except Exception as e:
        print(f"💥 시스템 실행 중 오류 발생: {e}")