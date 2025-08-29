import os
import datetime as dt
from pathlib import Path
from textwrap import dedent
from typing import List, Dict, Optional

from dotenv import load_dotenv
from openai import OpenAI

# 0) 환경 로드
load_dotenv()

# 1) 출력 폴더
DOCS_DIR = Path("docs2")
DOCS_DIR.mkdir(parents=True, exist_ok=True)

# 2) OpenAI 설정
API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
TEMPERATURE = 0.5
MAX_TOKENS = 1100  # A4 1장 내외

# 3) 공통 시스템 프롬프트 (모든 문서에 공통 적용)
SYSTEM_PROMPT = dedent("""
당신은 한국 AI 스타트업 '코드노바(CodeNova)'의 내부 문서를 작성하는 역할이다.
코드노바회사의 자세한 정보는 아래와 같다
- **회사명**: 코드노바 (CodeNova)
- **설립**: 2021년
- **대표**: 사용자(본인)
- **위치**: 서울 서초구
- **주요 서비스**:
    - **코드노바**: 생성형 AI 글쓰기·이미지·요약 플랫폼
    - **크랙(Crack)**: AI 페르소나 챗봇 앱
    - **Wrtn Ads**: 대화형 광고 제작·보상 플랫폼
- **특징**: 빠른 사용자 성장, 무료 확산 전략
- **현재 과제**: 수익 모델 확보
- **비전**: 단순 AI 도구 → 사용자의 감정을 이해하는 **AI 컴패니언**

“한국형 생성형 AI 플랫폼 기업”이다

                  
내부문서대상: 주니어~미들 프론트엔드 개발자

금지:
- 회사 전략
- 재무·민감 수치
- 계약 조건
- 미공개 로드맵
- 고객 식별정보
- 개인정보
- 내부 비공개 URL
- 영업기밀
- 코드
- 이미지
- 파일구조

스타일:
- 실행 가능한 단계/체크리스트/검증 포인트 중심
- 마크다운 문법 사용
- 과도한 사내 용어 금지

출력 규칙 (중요):
- 아래 "작성 지침"과 "주의"는 참고용이며 **최종 문서에 포함하지 않는다**
- 최종 결과는 완결된 문서만 출력한다

작성 지침:
- 언어: 한국어, 마크다운 문법
- 분량: A4 1장(약 550~750 단어)
- 직원이 바로 실행할 수 있도록 단계/체크리스트/검증 포인트 구체화
- 문서 끝에 '다음 개정 제안' 2~3줄 작성

주의:
- 민감 지표/내부 링크/고객 실명/재무 수치/전략 비공개 정보는 금지
""").strip()

def today_str() -> str:
    return dt.date.today().isoformat()

# 4) 공통 머리말
def base_prompt(category: str, title: str, today: str) -> str:
    return dedent(f"""
    # {title}
    분류: {category} | 회사: 코드노바 | 버전: v1.0 | 작성일: {today}
    ---
    """).strip()

# 5) 문서별 사용자 프롬프트 정의 (각 문서마다 서로 다르게!)
PROMPT_ARCH = dedent("""
코드노바회사의 프론트엔드 아키텍처 문서를 작성하라.문서안에 코드부분은 전부 제거해주고 글자만 작성해줘 

""").strip()

PROMPT_API = dedent("""
코드노바 회사 프론트엔드 팀의 API 연동 매뉴얼 문서를 작성하라.문서안에 코드부분은 전부 제거해주고 글자만 작성해줘 

""").strip()





PROMPT_BUILD = dedent("""
코드노바 회사 프론트엔드 팀의  빌드/배포 가이드 문서를 작성하라.문서안에 코드부분은 전부 제거해주고 글자만 작성해줘 

""").strip()

PROMPT_CODE_CON = dedent("""
코드노바 회사 프론트엔드팀의  코딩 컨벤션 & 스타일 가이드 문서를 작성하라.문서안에 코드부분은 전부 제거해주고 글자만 작성해줘  

""").strip()

PROMPT_UI = dedent("""
코드노바 회사 프론트엔드팀의  UI/UX 디자인 가이드라인 문서를 작성하라.문서안에 코드부분은 전부 제거해주고 글자만 작성해줘  

""").strip()

PROMPT_QA = dedent("""
코드노바 회사 프론트엔드팀의 테스트 전략 및 QA 가이드 문서를 작성하라.문서안에 코드부분은 전부 제거해주고 글자만 작성해줘  

""").strip()

PROMPT_SECURITY = dedent("""
코드노바 회사 프론트엔드팀의 보안 가이드라인 문서를  작성하라.문서안에 코드부분은 전부 제거해주고 글자만 작성해줘 

""").strip()

PROMPT_LOG = dedent("""
코드노바 회사 프론트엔드 팀의 로그/모니터링 가이드 문서를 작성하라.문서안에 코드부분은 전부 제거해주고 글자만 작성해줘 

""").strip()

PROMPT_CORP = dedent("""
코드노바 회사 프론트엔드팀의  협업 프로세스 문서를 작성하라.문서안에 코드부분은 전부 제거해주고 글자만 작성해줘 

""").strip()

PROMPT_ONBOARD = dedent("""
코드노바 회사 프론트엔드팀의  신규 입사자 온보딩 가이드를 작성하라.문서안에 코드부분은 전부 제거해주고 글자만 작성해줘 

""").strip()

PROMPT_Daily = dedent("""
코드노바회사 프론트엔드팀의 주간업무계획 문서를  작성해라 
""").strip()

PROMPT_POSTMORTEM = dedent("""
코드노바 회사 프론트엔드팀의 실패 사례 & 대응 기록(Postmortem) 문서 템플릿을 작성하라.가상으로 실패사례/대응기록을 만들어 그리고 문서안에 코드부분은 전부 제거해주고 글자만 작성해줘 

""").strip()

PROMPT_RELEASE = dedent("""
코드노바 회사 프론트엔드팀의 프로젝트/제품 릴리즈 노트 관리 문서를 작성하라.문서안에 코드부분은 전부 제거해주고 글자만 작성해줘 

""").strip()

PROMPT_meeting1=dedent("""
코드노바 회사 프론트엔드팀의 회의록(정기회의) #1 문서를 작성해라  다음 항목을 포함해라
## 포함 섹션
1. 회의 개요(일시/참석자/의제)
2. 논의된 주요 사항
3. 의사결정/결론
4. 후속 Action Item (담당/마감)
5. 리스크 및 보류 과제
6. 개정 이력 (v1.0 — 오늘)
    """)

PROMPT_meeting2=dedent("""
코드노바 회사 프론트엔드팀의 회의록(정기회의) #2 문서를  작성해라  다음 항목을 포함해라
## 포함 섹션
1. 회의 개요(일시/참석자/의제)
2. 논의된 주요 사항
3. 의사결정/결론
4. 후속 Action Item (담당/마감)
5. 리스크 및 보류 과제
6. 개정 이력 (v1.0 — 오늘)
    """)

# 6) 문서 스펙: 문서별로 'prompt'를 명시
DOC_SPECS: List[Dict] = [
    {"category": "frontend", "title": "프론트엔드 아키텍처 문서",                 "prompt": PROMPT_ARCH},
    {"category": "frontend", "title": "API 연동 매뉴얼",                          "prompt": PROMPT_API},
    {"category": "frontend", "title": "빌드/배포 가이드",                         "prompt": PROMPT_BUILD},
    {"category": "frontend", "title": "코딩 컨벤션 & 스타일 가이드",              "prompt": PROMPT_CODE_CON},
    {"category": "frontend", "title": "UI/UX 디자인 가이드라인",                 "prompt": PROMPT_UI},
    {"category": "frontend", "title": "테스트 전략 및 QA 가이드",                 "prompt": PROMPT_QA},
    {"category": "frontend", "title": "보안 가이드라인",                          "prompt": PROMPT_SECURITY},
    {"category": "frontend", "title": "로그/모니터링 가이드",                     "prompt": PROMPT_LOG},
    {"category": "frontend", "title": "협업 프로세스 문서",                       "prompt": PROMPT_CORP},
    {"category": "frontend", "title": "신규 입사자 온보딩 가이드",                "prompt": PROMPT_ONBOARD},
    {"category": "meeting", "title": "프론트엔드팀 주간 업무 계획",                    "prompt": PROMPT_Daily},
    {"category": "meeting", "title": "프론트엔드팀_회의록(정기회의) #1",                    "prompt": PROMPT_meeting1},
    {"category": "meeting", "title": "프론트엔드팀_회의록(정기회의) #2",                    "prompt": PROMPT_meeting2},
    {"category": "frontend", "title": "실패 사례 & 대응 기록 (Postmortem 문서)", "prompt": PROMPT_POSTMORTEM},
    {"category": "frontend", "title": "프로젝트/제품 릴리즈 노트 관리 문서",      "prompt": PROMPT_RELEASE},
]

# 7) 최종 사용자 프롬프트 생성: 머리말 + (문서별) 사용자 프롬프트
def make_user_prompt(category: str, title: str, today: str, prompt: str) -> str:
    base = base_prompt(category, title, today)
    return f"{base}\n\n{prompt}"

# 8) 파일명 안전 변환
def safe_slug(text: str) -> str:
    keep = []
    for ch in text:
        if ch.isalnum() or ch in " ._-()[]{}&":
            keep.append(ch)
        else:
            keep.append("_")
    slug = "".join(keep).strip().replace("  ", " ")
    return "_".join(slug.split())

# 9) 생성/저장 루프
def generate_and_write_docs():
    if not API_KEY:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다. .env를 확인하세요.")
    client = OpenAI(api_key=API_KEY)
    today = today_str()
    index_lines = []

    for idx, spec in enumerate(DOC_SPECS, start=1):
        category, title, prompt = spec["category"], spec["title"], spec["prompt"]
        user_prompt = make_user_prompt(category, title, today, prompt)

        completion = client.chat.completions.create(
            model=MODEL,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},   # 공통 규칙
                {"role": "user", "content": user_prompt},       # 문서별 사용자 프롬프트
            ],
        )
        content = completion.choices[0].message.content.strip()

        prefix = f"{idx:02d}"
        filename = f"{prefix}_{safe_slug(category)}__{safe_slug(title)}.txt"
        out_path = DOCS_DIR / filename

        header = f"<!-- 회사: 코드노바 | 대상: 사원(프론트엔드) | 작성일: {today} -->\n"
        out_path.write_text(header + content + "\n", encoding="utf-8")
        index_lines.append(f"{prefix}. {category} - {title} -> {filename}")

    (DOCS_DIR / "INDEX.txt").write_text(
        "코드노바 프론트엔드 문서 — 생성 결과 목록\n" + "\n".join(index_lines) + "\n",
        encoding="utf-8",
    )
    print(f"[완료] docs/ 폴더에 {len(DOC_SPECS)}개 문서를 저장했습니다.")
    print("목록: docs/INDEX.txt 를 확인하세요.")

if __name__ == "__main__":
    generate_and_write_docs()
