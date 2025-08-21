import os
import sys
import yaml
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# .env 파일 로드
load_dotenv()

# RAG 시스템 임포트 (파일명에 맞게 수정 필요)
from google_api_rag import GoogleAPIRAGSystem


def load_config(config_path: str = "config.yaml"):
    """설정 파일 로드"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def main():
    """메인 실행 함수"""

    # 설정 로드
    config = load_config()

    # 환경변수에서 API 키 가져오기
    openai_api_key = os.getenv("OPENAI_API_KEY")
    default_model = os.getenv("DEFAULT_MODEL", config['models']['default'])

    # 모델 선택
    use_gpt4o = (default_model == "gpt4o")

    if use_gpt4o and not openai_api_key:
        print("⚠️ GPT-4o를 사용하려면 OPENAI_API_KEY 환경변수를 설정해주세요.")
        print("💡 .env 파일에 OPENAI_API_KEY=your_key_here 형식으로 추가하거나")
        print("💡 export OPENAI_API_KEY=your_key_here 명령을 실행하세요.\n")
        use_gpt4o = False
        print("🔄 Qwen3:8B 모델로 전환합니다.\n")

    # RAG 시스템 초기화
    print("🚀 Google API RAG 시스템을 시작합니다...")
    print(f"📊 선택된 모델: {'GPT-4o' if use_gpt4o else 'Qwen3:8B (해요체)'}\n")

    rag_system = GoogleAPIRAGSystem(
        api_data_dir=config['paths']['api_data_dir'],
        api_qa_dir=config['paths']['api_qa_dir'],
        db_dir=config['paths']['chroma_db_dir'],
        openai_api_key=openai_api_key
    )

    # 시스템 초기화
    rag_system.initialize_all(
        use_gpt4o=use_gpt4o,
        openai_api_key=openai_api_key
    )

    # 웰컴 메시지
    print("\n" + "=" * 60)
    print("🎉 Google API RAG 시스템이 준비되었습니다!")
    print("=" * 60)
    print("\n💡 사용 가능한 명령어:")
    print("  • 질문 입력: Google API 관련 질문을 입력하세요")
    print("  • 'switch': 모델 전환 (GPT-4o ↔ Qwen3:8B)")
    print("  • 'history': 대화 히스토리 보기")
    print("  • 'clear': 화면 지우기")
    print("  • 'quit/exit/종료': 프로그램 종료")
    print("=" * 60 + "\n")

    # 대화형 모드
    while True:
        try:
            user_input = input("❓ 질문: ").strip()

            # 종료 명령
            if user_input.lower() in ['quit', 'exit', '종료', 'q']:
                print("\n👋 프로그램을 종료합니다. 감사합니다!")
                break

            # 모델 전환
            elif user_input.lower() == 'switch':
                if rag_system.current_model == "qwen":
                    if openai_api_key:
                        rag_system.initialize_models(use_gpt4o=True, openai_api_key=openai_api_key)
                        print("✅ GPT-4o 모델로 전환되었습니다.\n")
                    else:
                        print("⚠️ OpenAI API 키가 없어서 전환할 수 없습니다.\n")
                else:
                    rag_system.initialize_models(use_gpt4o=False)
                    print("✅ Qwen3:8B 모델로 전환되었습니다. (해요체)\n")
                continue

            # 대화 히스토리
            elif user_input.lower() == 'history':
                if hasattr(rag_system, 'conversation_history') and rag_system.conversation_history:
                    print("\n📜 대화 히스토리:")
                    print("-" * 60)
                    for i, item in enumerate(rag_system.conversation_history[-5:], 1):
                        print(f"\n[{i}] 질문: {item['query']}")
                        print(f"    모델: {item['model'].upper()}")
                        print(f"    답변: {item['response'][:100]}...")
                    print("-" * 60 + "\n")
                else:
                    print("📭 대화 히스토리가 없습니다.\n")
                continue

            # 화면 지우기
            elif user_input.lower() == 'clear':
                os.system('clear' if os.name == 'posix' else 'cls')
                print("🎉 Google API RAG 시스템")
                print("=" * 60 + "\n")
                continue

            # 빈 입력 처리
            elif not user_input:
                continue

            # API 검색 및 응답
            response = rag_system.search_api(user_input)
            rag_system.add_conversation_history(user_input, response)

        except KeyboardInterrupt:
            print("\n\n⚠️ 프로그램이 중단되었습니다.")
            break
        except Exception as e:
            print(f"\n❌ 오류가 발생했습니다: {e}")
            print("다시 시도해주세요.\n")


if __name__ == "__main__":
    main()