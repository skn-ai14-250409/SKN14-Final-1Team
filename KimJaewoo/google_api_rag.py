import os
import json
import torch
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Literal
from transformers import AutoModelForCausalLM, AutoTokenizer
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.prompts import PromptTemplate
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
import openai


class GoogleAPIRAGSystem:
    """구글 API 문서 검색을 위한 RAG 시스템 (GPT-4o & Qwen3:8B)"""

    def __init__(self,
                 api_data_dir: str = "./GOOGLE_API_DATA",
                 api_qa_dir: str = "./GOOGLE_API_DATA/GOOGLE_API_DATA_QA",
                 db_dir: str = "./chroma_google_api_db",
                 openai_api_key: Optional[str] = None):
        """
        Args:
            api_data_dir: 구글 API 원본 데이터 디렉토리
            api_qa_dir: 구글 API QA 데이터 디렉토리
            db_dir: Chroma DB 저장 경로
            openai_api_key: OpenAI API 키 (GPT-4o 사용시)
        """
        self.api_data_dir = Path(api_data_dir)
        self.api_qa_dir = Path(api_qa_dir)
        self.db_dir = db_dir

        # OpenAI 설정 (GPT-4o용)
        if openai_api_key:
            os.environ["OPENAI_API_KEY"] = openai_api_key
            openai.api_key = openai_api_key

        # 컴포넌트 초기화
        self.documents = []
        self.vectorstore = None
        self.retriever = None

        # 모델 관련
        self.qwen_model = None
        self.qwen_tokenizer = None
        self.gpt4o_model = None
        self.embedding_model = None

        # 현재 사용 모델
        self.current_model: Literal["gpt4o", "qwen"] = "qwen"

    def load_api_documents(self) -> List[Document]:
        """구글 API 문서들을 로드하고 Document 객체로 변환"""
        documents = []

        # 1. GOOGLE_API_DATA_QA 폴더에서 QA 형식 데이터 로드
        if self.api_qa_dir.exists():
            print(f"📂 QA 데이터 로드 중: {self.api_qa_dir}")

            # JSON 파일 로드
            for file_path in self.api_qa_dir.glob("*.json"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        qa_data = json.load(f)

                    # QA 쌍을 문서로 변환
                    if isinstance(qa_data, list):
                        for item in qa_data:
                            doc = Document(
                                page_content=f"질문: {item.get('question', '')}\n답변: {item.get('answer', '')}",
                                metadata={
                                    'type': 'qa',
                                    'question': item.get('question', ''),
                                    'answer': item.get('answer', ''),
                                    'api_category': self._extract_api_category_from_content(item.get('question', '')),
                                    'source_file': file_path.name
                                }
                            )
                            documents.append(doc)

                except Exception as e:
                    print(f"⚠️ Error loading {file_path}: {e}")

            # TXT 파일 로드
            for file_path in self.api_qa_dir.glob("*.txt"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Q&A 형식 파싱 시도
                    if "Q:" in content or "질문:" in content:
                        qa_pairs = self._parse_qa_format(content)
                        for q, a in qa_pairs:
                            doc = Document(
                                page_content=f"질문: {q}\n답변: {a}",
                                metadata={
                                    'type': 'qa',
                                    'question': q,
                                    'answer': a,
                                    'source_file': file_path.name
                                }
                            )
                            documents.append(doc)
                    else:
                        # 일반 텍스트로 처리
                        doc = Document(
                            page_content=content,
                            metadata={
                                'type': 'text',
                                'source_file': file_path.name
                            }
                        )
                        documents.append(doc)

                except Exception as e:
                    print(f"⚠️ Error loading {file_path}: {e}")

        # 2. GOOGLE_API_DATA 폴더에서 원본 API 문서 로드
        if self.api_data_dir.exists():
            print(f"📂 원본 API 데이터 로드 중: {self.api_data_dir}")

            # 텍스트 파일들을 청킹하여 로드
            for file_path in self.api_data_dir.glob("*.txt"):
                if file_path.parent == self.api_data_dir:  # 하위 폴더 제외
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        # 텍스트 청킹
                        text_splitter = RecursiveCharacterTextSplitter(
                            chunk_size=1500,
                            chunk_overlap=300,
                            separators=["\n\n\n", "\n\n", "\n", ".", " "]
                        )

                        chunks = text_splitter.split_text(content)

                        for i, chunk in enumerate(chunks):
                            doc = Document(
                                page_content=chunk,
                                metadata={
                                    'type': 'api_doc',
                                    'source_file': file_path.name,
                                    'chunk_id': i,
                                    'api_category': self._extract_api_category(file_path.name)
                                }
                            )
                            documents.append(doc)

                    except Exception as e:
                        print(f"⚠️ Error loading {file_path}: {e}")

        # 샘플 데이터 추가 (실제 데이터가 없을 경우)
        if not documents:
            documents = self._create_sample_documents()

        self.documents = documents
        print(f"✅ 총 {len(documents)}개의 문서를 로드했습니다.")
        return documents

    def _parse_qa_format(self, content: str) -> List[Tuple[str, str]]:
        """Q&A 형식의 텍스트를 파싱"""
        qa_pairs = []

        # 다양한 Q&A 패턴 처리
        import re

        # 패턴 1: Q: ... A: ...
        pattern1 = r'Q[:\.]?\s*(.*?)\s*A[:\.]?\s*(.*?)(?=Q[:\.]?|\Z)'
        matches1 = re.findall(pattern1, content, re.DOTALL)

        # 패턴 2: 질문: ... 답변: ...
        pattern2 = r'질문[:\.]?\s*(.*?)\s*답변[:\.]?\s*(.*?)(?=질문[:\.]?|\Z)'
        matches2 = re.findall(pattern2, content, re.DOTALL)

        qa_pairs.extend(matches1)
        qa_pairs.extend(matches2)

        # 정리
        qa_pairs = [(q.strip(), a.strip()) for q, a in qa_pairs if q.strip() and a.strip()]

        return qa_pairs

    def _extract_api_category(self, filename: str) -> str:
        """파일명에서 API 카테고리 추출"""
        filename_lower = filename.lower()

        # 구글 API 카테고리 매핑
        api_categories = {
            'gmail': 'gmail',
            'drive': 'drive',
            'calendar': 'calendar',
            'sheets': 'sheets',
            'docs': 'docs',
            'slides': 'slides',
            'meet': 'meet',
            'maps': 'maps',
            'youtube': 'youtube',
            'analytics': 'analytics'
        }

        for key in api_categories:
            if key in filename_lower:
                return api_categories[key]

        return 'general'

    def _extract_api_category_from_content(self, content: str) -> str:
        """내용에서 API 카테고리 추출"""
        content_lower = content.lower()

        api_keywords = {
            'gmail': ['gmail', '이메일', 'email', 'messages.send'],
            'drive': ['drive', '드라이브', 'files.list', 'files.create'],
            'calendar': ['calendar', '캘린더', 'events.insert', 'events.list'],
            'sheets': ['sheets', '스프레드시트', 'spreadsheet', 'values.update'],
            'docs': ['docs', '문서', 'documents.create'],
            'youtube': ['youtube', '유튜브', 'videos.list'],
            'maps': ['maps', '지도', 'geocoding', 'directions']
        }

        for category, keywords in api_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                return category

        return 'general'

    def _create_sample_documents(self) -> List[Document]:
        """샘플 구글 API QA 데이터 생성"""
        sample_qa_data = [
            {
                "question": "Gmail API로 이메일을 보내려면 어떻게 해야 하나요?",
                "answer": """Gmail API로 이메일을 보내려면 다음 단계를 따르세요:

1. OAuth 2.0 인증 설정 (gmail.send 스코프 필요)
2. MIME 메시지 생성
3. base64url 인코딩
4. messages.send() 메서드 호출

예제 코드:
```python
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64

# 메시지 생성
message = MIMEText('안녕하세요!')
message['to'] = 'recipient@example.com'
message['subject'] = '테스트 이메일'

# base64 인코딩
raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

# 전송
service.users().messages().send(userId='me', body={'raw': raw}).execute()
```"""
            },
            {
                "question": "Google Drive에서 특정 파일 타입만 검색하는 방법은?",
                "answer": """Drive API의 files.list() 메서드에서 q 파라미터를 사용하세요:

1. PDF 파일만: q="mimeType='application/pdf'"
2. 이미지 파일: q="mimeType contains 'image/'"
3. 특정 폴더 내: q="'FOLDER_ID' in parents"
4. 이름 포함: q="name contains 'report'"

예제:
```python
results = service.files().list(
    q="mimeType='application/pdf' and name contains '2024'",
    pageSize=10,
    fields="files(id, name, mimeType)"
).execute()
```"""
            },
            {
                "question": "Calendar API로 반복 이벤트를 만들려면?",
                "answer": """반복 이벤트는 recurrence 필드를 사용해요:

```python
event = {
    'summary': '주간 회의',
    'start': {'dateTime': '2024-01-15T10:00:00', 'timeZone': 'Asia/Seoul'},
    'end': {'dateTime': '2024-01-15T11:00:00', 'timeZone': 'Asia/Seoul'},
    'recurrence': [
        'RRULE:FREQ=WEEKLY;COUNT=10'  # 10주간 매주 반복
    ]
}

service.events().insert(calendarId='primary', body=event).execute()
```

RRULE 예시:
- 매일: FREQ=DAILY
- 매주 월,수,금: FREQ=WEEKLY;BYDAY=MO,WE,FR
- 매월 15일: FREQ=MONTHLY;BYMONTHDAY=15"""
            }
        ]

        documents = []
        for item in sample_qa_data:
            doc = Document(
                page_content=f"질문: {item['question']}\n답변: {item['answer']}",
                metadata={
                    'type': 'qa',
                    'question': item['question'],
                    'answer': item['answer'],
                    'api_category': self._extract_api_category_from_content(item['question'])
                }
            )
            documents.append(doc)

        return documents

    def initialize_vectorstore(self):
        """벡터 저장소 초기화 및 문서 임베딩"""
        print("🔧 임베딩 모델 초기화 중...")
        self.embedding_model = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={'device': 'cuda' if torch.cuda.is_available() else 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )

        print("💾 벡터 저장소 생성 중...")
        self.vectorstore = Chroma.from_documents(
            documents=self.documents,
            embedding=self.embedding_model,
            persist_directory=self.db_dir,
            collection_metadata={"hnsw:space": "cosine"}
        )

        # 리트리버 설정
        self.retriever = self.vectorstore.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={
                "k": 5,
                "score_threshold": 0.3
            }
        )

        print(f"✅ 벡터 저장소가 {self.db_dir}에 생성되었습니다.")

    def initialize_models(self, use_gpt4o: bool = False, openai_api_key: Optional[str] = None):
        """LLM 모델 초기화"""

        if use_gpt4o:
            # GPT-4o 초기화
            if openai_api_key:
                os.environ["OPENAI_API_KEY"] = openai_api_key

            print("🤖 GPT-4o 모델 초기화 중...")
            self.gpt4o_model = ChatOpenAI(
                model="gpt-4o",
                temperature=0.7,
                max_tokens=1024
            )
            self.current_model = "gpt4o"
            print("✅ GPT-4o 모델 준비 완료")

        else:
            # Qwen3:8B 초기화 (로컬 모델)
            print("🤖 Qwen3:8B 모델 초기화 중...")

            model_name = "Qwen/Qwen2.5-7B-Instruct"  # 더 나은 성능을 위해 업그레이드
            local_model_path = "./Qwen2.5-7B-Instruct"

            if os.path.exists(local_model_path):
                print(f"📂 로컬 모델 로드 중: {local_model_path}")
                self.qwen_tokenizer = AutoTokenizer.from_pretrained(
                    local_model_path,
                    local_files_only=True
                )
                self.qwen_model = AutoModelForCausalLM.from_pretrained(
                    local_model_path,
                    device_map="auto",
                    torch_dtype=torch.float16,
                    local_files_only=True
                )
            else:
                print(f"⬇️ Hugging Face에서 모델 다운로드 중: {model_name}")
                self.qwen_tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.qwen_model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    torch_dtype=torch.float16,
                    device_map="auto"
                )
                # 로컬 저장
                self.qwen_tokenizer.save_pretrained(local_model_path)
                self.qwen_model.save_pretrained(local_model_path)
                print(f"💾 모델이 {local_model_path}에 저장되었습니다.")

            self.current_model = "qwen"
            print("✅ Qwen3:8B 모델 준비 완료")

    def format_docs_for_context(self, docs: List[Document]) -> str:
        """검색된 문서를 컨텍스트로 포맷팅"""
        formatted = []

        for i, doc in enumerate(docs, 1):
            if doc.metadata.get('type') == 'qa':
                # QA 형식 문서
                formatted.append(f"[참고 {i}]\n{doc.page_content}")
            else:
                # 일반 문서
                content = f"[참고 {i}]\n"
                content += f"내용: {doc.page_content[:500]}..."  # 길이 제한
                if 'api_category' in doc.metadata:
                    content += f"\n카테고리: {doc.metadata['api_category']}"
                formatted.append(content)

        return "\n\n---\n\n".join(formatted)

    def get_prompt_template(self, use_haeyoche: bool = False) -> str:
        """프롬프트 템플릿 생성"""

        if use_haeyoche:
            # Qwen 모델용 (해요체)
            template = """당신은 구글 API 전문가예요. 다음의 참고 자료를 바탕으로 개발자에게 친근하고 도움이 되는 답변을 제공해주세요.

참고 자료:
{context}

질문: {question}

답변할 때 다음 사항을 지켜주세요:
1. 정확한 API 메서드명과 파라미터를 알려주세요
2. 실제 코드 예시를 포함해주세요
3. 필요한 권한이나 주의사항이 있다면 언급해주세요
4. 친근한 해요체로 설명해주세요

답변:"""
        else:
            # GPT-4o용 (멀티턴 고려)
            template = """You are a Google API expert. Based on the following reference materials, provide accurate and practical answers to help developers.

Reference Materials:
{context}

Question: {question}

Please ensure your answer includes:
1. Exact API method names and parameters
2. Practical code examples
3. Required permissions or important notes
4. Clear and structured explanation

Answer in Korean:"""

        return template

    def retrieve_with_scores(self, query: str, k: int = 5) -> Tuple[List[Document], List[float]]:
        """쿼리와 관련된 문서 검색 (유사도 점수 포함)"""
        results = self.vectorstore.similarity_search_with_score(query, k=k)
        docs = [doc for doc, _ in results]
        scores = [score for _, score in results]
        return docs, scores

    def generate_response_with_gpt4o(self, query: str, context: str) -> str:
        """GPT-4o를 사용한 응답 생성 (멀티턴 지원)"""
        messages = [
            SystemMessage(content="""당신은 구글 API 전문가입니다. 
            개발자들에게 정확하고 실용적인 답변을 제공하세요.
            코드 예시와 함께 단계별로 설명해주세요."""),
            HumanMessage(content=f"""
참고 자료:
{context}

질문: {query}

답변해주세요:""")
        ]

        response = self.gpt4o_model.invoke(messages)
        return response.content

    def generate_response_with_qwen(self, query: str, context: str) -> str:
        """Qwen 모델을 사용한 응답 생성 (해요체)"""
        prompt_template = self.get_prompt_template(use_haeyoche=True)
        prompt_text = prompt_template.format(context=context, question=query)

        # 토큰화
        inputs = self.qwen_tokenizer(
            prompt_text,
            return_tensors="pt",
            max_length=2048,
            truncation=True
        ).to(self.qwen_model.device)

        # 응답 생성
        with torch.no_grad():
            outputs = self.qwen_model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.7,
                do_sample=True,
                top_p=0.9,
                pad_token_id=self.qwen_tokenizer.eos_token_id,
                eos_token_id=self.qwen_tokenizer.eos_token_id
            )

        # 디코딩
        full_response = self.qwen_tokenizer.decode(outputs[0], skip_special_tokens=True)
        answer_only = full_response.replace(prompt_text, "").strip()

        return answer_only

    def generate_response(self, query: str, use_gpt4o: Optional[bool] = None) -> Tuple[
        List[Document], List[float], str]:
        """사용자 질문에 대한 응답 생성"""

        # 모델 선택
        if use_gpt4o is None:
            use_gpt4o = (self.current_model == "gpt4o")

        # 관련 문서 검색
        docs, scores = self.retrieve_with_scores(query)

        # 컨텍스트 생성
        context = self.format_docs_for_context(docs)

        # 응답 생성
        if use_gpt4o and self.gpt4o_model:
            response = self.generate_response_with_gpt4o(query, context)
        elif self.qwen_model:
            response = self.generate_response_with_qwen(query, context)
        else:
            response = "모델이 초기화되지 않았습니다. initialize_models()를 먼저 실행해주세요."

        return docs, scores, response

    def initialize_all(self, use_gpt4o: bool = False, openai_api_key: Optional[str] = None):
        """전체 시스템 초기화"""
        print("=" * 60)
        print("🚀 Google API RAG 시스템 초기화 시작")
        print("=" * 60)

        # 1. 문서 로드
        print("\n📚 [1/3] API 문서 로드 중...")
        self.load_api_documents()

        # 2. 벡터 저장소 초기화
        print("\n🔍 [2/3] 벡터 저장소 초기화 중...")
        self.initialize_vectorstore()

        # 3. LLM 초기화
        print("\n🤖 [3/3] LLM 모델 초기화 중...")
        self.initialize_models(use_gpt4o=use_gpt4o, openai_api_key=openai_api_key)

        print("\n" + "=" * 60)
        print("✅ 초기화 완료!")
        print(f"📊 현재 모델: {'GPT-4o' if self.current_model == 'gpt4o' else 'Qwen3:8B'}")
        print("=" * 60 + "\n")

    def search_api(self, query: str, use_gpt4o: Optional[bool] = None, verbose: bool = True):
        """API 검색 및 응답 제공"""
        docs, scores, response = self.generate_response(query, use_gpt4o)

        if verbose:
            print("\n" + "=" * 60)
            print(f"🔍 질문: {query}")
            print(f"🤖 모델: {'GPT-4o' if (use_gpt4o or self.current_model == 'gpt4o') else 'Qwen3:8B (해요체)'}")
            print("=" * 60)

            print("\n📚 검색된 관련 문서:")
            for i, (doc, score) in enumerate(zip(docs[:3], scores[:3]), 1):  # 상위 3개만 표시
                doc_type = doc.metadata.get('type', 'unknown')
                if doc_type == 'qa':
                    print(f"\n  [{i}] QA 문서 (유사도: {score:.4f})")
                    print(f"      질문: {doc.metadata.get('question', 'N/A')[:50]}...")
                else:
                    category = doc.metadata.get('api_category', 'general')
                    print(f"\n  [{i}] API 문서 - {category} (유사도: {score:.4f})")
                    print(f"      내용: {doc.page_content[:80]}...")

            print("\n" + "-" * 60)
            print("💡 답변:")
            print("-" * 60)
            print(response)
            print("=" * 60 + "\n")

        return response

    def add_conversation_history(self, query: str, response: str):
        """대화 히스토리 추가 (멀티턴 지원)"""
        # 향후 멀티턴 대화를 위한 히스토리 저장
        if not hasattr(self, 'conversation_history'):
            self.conversation_history = []

        self.conversation_history.append({
            'query': query,
            'response': response,
            'model': self.current_model
        })


# 메인 실행 코드
if __name__ == "__main__":
    import argparse

    # 명령줄 인자 파서
    parser = argparse.ArgumentParser(description='Google API RAG System')
    parser.add_argument('--use-gpt4o', action='store_true', help='Use GPT-4o instead of Qwen')
    parser.add_argument('--api-key', type=str, help='OpenAI API key for GPT-4o')
    args = parser.parse_args()

    # RAG 시스템 초기화
    rag_system = GoogleAPIRAGSystem(
        api_data_dir="../GOOGLE_API_DATA",
        api_qa_dir="../GOOGLE_API_DATA/GOOGLE_API_DATA_QA",
        db_dir="../chroma_google_api_db",
        openai_api_key=args.api_key
    )

    # 전체 시스템 초기화
    rag_system.initialize_all(
        use_gpt4o=args.use_gpt4o,
        openai_api_key=args.api_key
    )

    # 테스트 쿼리
    test_queries = [
        "Gmail API로 첨부파일 있는 이메일 보내는 방법 알려줘",
        "Google Drive에서 최근 수정된 파일 찾기",
        "Calendar API로 참석자 초대하는 방법",
    ]

    print("\n" + "🧪 테스트 시작 " + "=" * 40)

    for query in test_queries:
        response = rag_system.search_api(query)
        rag_system.add_conversation_history(query, response)
        input("\n다음 질문으로 계속하려면 Enter를 누르세요...")

    # 대화형 모드
    print("\n" + "💬 대화형 모드 " + "=" * 40)
    print("종료: 'quit', 'exit', '종료' 입력")
    print("모델 전환: 'switch model' 입력")
    print("=" * 60)

    while True:
        user_query = input("\n❓ 질문: ")

        if user_query.lower() in ['quit', 'exit', '종료']:
            print("👋 프로그램을 종료합니다.")
            break

        if user_query.lower() == 'switch model':
            # 모델 전환
            if rag_system.current_model == "qwen":
                if args.api_key:
                    rag_system.initialize_models(use_gpt4o=True, openai_api_key=args.api_key)
                    print("✅ GPT-4o로 전환되었습니다.")
                else:
                    print("⚠️ OpenAI API 키가 필요합니다. --api-key 옵션을 사용하세요.")
            else:
                rag_system.initialize_models(use_gpt4o=False)
                print("✅ Qwen3:8B로 전환되었습니다.")
            continue

        response = rag_system.search_api(user_query)
        rag_system.add_conversation_history(user_query, response)