import os
import datetime as dt
from pathlib import Path
from textwrap import dedent
from typing import List, Dict

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DOCS_DIR = Path("docs_DataAiTeam")
DOCS_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

TEMPERATURE = 0.5
MAX_TOKENS = 1100  # A4 한 장 분량 

data_security = [
    ("데이터 관리 & 보안", "데이터 파이프라인 설계 문서"),
    ("데이터 관리 & 보안", "데이터 접근/보안 정책"),
    ("데이터 관리 & 보안", "데이터 거버넌스 정책"),
    ("데이터 관리 & 보안", "데이터 보존 및 폐기 정책"),
    ("데이터 관리 & 보안", "수집된 데이터 및 전처리 기록서"),
]

model_docs = [
    ("모델 개발 & 성능", "모델 성능 평가 보고서"),
    ("모델 개발 & 성능", "모델 학습 결과서"),
    ("모델 개발 & 성능", "성능 비교표"),
    ("모델 개발 & 성능", "테스트 계획 및 결과 보고서"),
    ("모델 개발 & 성능", "데이터 품질 점검 보고서"),
]

ops_collab = [
    ("팀 운영 문서", "데이터팀 주간 업무 계획"),
    ("팀 운영 문서", "AI팀 주간 업무 계획"),
    ("팀 운영 문서", "회의록(정기회의) #1"),
    ("팀 운영 문서", "회의록(정기회의) #2"),
    ("팀 운영 문서", "AI 윤리/리스크 관리 문서"),
]

DOC_SPECS: List[Dict] = [
    *[{"category": c, "title": t} for c, t in data_security],
    *[{"category": c, "title": t} for c, t in model_docs],
    *[{"category": c, "title": t} for c, t in ops_collab],
]

# ====== (C) 프롬프트 ======
SYSTEM_PROMPT = dedent(
    """
    너는 한국 AI 스타트업 '코드노바(CodeNova)'의 내부 문서 저자이다.
    독자: '데이터/AI팀'.
    금지: 회사 전략/재무 수치/계약 조건/미공개 로드맵/고객 실명·식별정보/개인정보/내부 비공개 URL.
    문서는 당장 실행 가능한 단계/체크리스트 중심으로 작성한다.
    출력은 Markdown 형식으로 작성한다 (제목, 소제목, 목록, 표 사용 가능).
"""
).strip()


def make_user_prompt(category: str, title: str, today: str) -> str:
    base = f"""# {title}
(분류: {category}) | 회사: CodeNova | 버전: v1.0 | 작성일: {today}

---
**작성 지침**
- 언어: 한국어, Markdown 형식 허용
- 분량: A4 1장(약 550~750단어) 내외
- 데이터/AI팀 수준에서 필요한 정보만 포함, 민감/전략/고객 식별정보 제외
- 실행 단계/체크리스트/검증 포인트 포함
"""
    if category == "데이터 관리 & 보안":
        body = dedent(
            """
            ## 포함 섹션
            1. 개요 및 목적
            2. 적용 범위/대상
            3. 표준 절차 및 실행 단계
            4. 검증 포인트/품질 기준
            5. 보안/프라이버시 준수
            6. 운영 체크리스트(일일/주간)
            7. 개정 이력 (v1.0 — 오늘)
        """
        ).strip()

    elif category == "모델 개발 & 성능":
        body = dedent(
            """
            ## 포함 섹션
            1. 프로젝트 개요 및 배경
            2. 모델/알고리즘 범위
            3. 실험/테스트 절차(데이터셋/환경/하이퍼파라미터)
            4. 성능 지표 및 기준(예: Accuracy/F1/ROC-AUC 등)
            5. 결과 요약 및 검증 포인트(재현성/통계적 유의성)
            6. 리스크/한계 및 개선 제안
            7. 개정 이력 (v1.0 — 오늘)
        """
        ).strip()

    elif category == "팀 운영 문서":
        if "주간 업무 계획" in title:
            body = dedent(
                """
                ## 포함 섹션
                1. 이번 주 최우선 과제(Top 3: 목표/성공기준/담당/마감)
                2. 팀원별 주요 작업(3~5개, 의존성/리스크 포함)
                3. 회의/마일스톤
                4. 협업/의존성
                5. 리스크/차질 대비
                6. 마감 후 점검(완료 기준/산출물 위치)
                7. 개정 이력 (v1.0 — 오늘)
            """
            ).strip()
        elif "회의록" in title:
            body = dedent(
                """
                ## 포함 섹션
                1. 회의 개요(일시/참석자/의제)
                2. 논의된 주요 사항
                3. 의사결정/결론
                4. 후속 Action Item (담당/마감)
                5. 리스크 및 보류 과제
                6. 개정 이력 (v1.0 — 오늘)
            """
            ).strip()
        else:
            body = dedent(
                """
                ## 포함 섹션
                1. 목적 및 적용 범위
                2. 윤리 원칙 요약
                3. 편향/공정성 점검 항목
                4. 법적/규제 리스크 검토
                5. 완화 전략 및 대응 프로세스
                6. 팀원 실천 체크리스트
                7. 개정 이력 (v1.0 — 오늘)
            """
            ).strip()

    footer = dedent(
        """
        ---
        주의:
        - 민감 지표/내부 링크/고객 실명/재무 수치/전략 비공개 정보는 절대 포함하지 말 것.
        - 데이터/AI팀이 당장 실행할 수 있게 단계/체크리스트를 구체적으로 작성할 것.
    """
    ).strip()

    return f"{base}\n{body}\n\n{footer}"


def safe_slug(text: str) -> str:
    keep = []
    for ch in text:
        if ch.isalnum() or ch in " ._-()[]{}&":
            keep.append(ch)
        else:
            keep.append("_")
    slug = "".join(keep).strip().replace("  ", " ")
    return "_".join(slug.split())


def generate_and_write_docs():
    client = OpenAI(api_key=API_KEY)

    today = dt.date.today().isoformat()
    index_lines = []
    for idx, spec in enumerate(DOC_SPECS, start=1):
        category, title = spec["category"], spec["title"]
        user_prompt = make_user_prompt(category, title, today)

        completion = client.chat.completions.create(
            model=MODEL,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = completion.choices[0].message.content.strip()

        prefix = f"{idx:02d}"
        filename = f"{prefix}_{safe_slug(category)}__{safe_slug(title)}.txt"
        out_path = DOCS_DIR / filename

        header = (
            f"# {category} | {title}\n\n"
            f"작성일: {today}\n회사: CodeNova | 대상: 데이터/AI팀\n\n---\n"
        )
        out_path.write_text(header + content + "\n", encoding="utf-8")

        index_lines.append(f"{prefix}. {category} - {title} -> {filename}")

    (DOCS_DIR / "INDEX.txt").write_text(
        "CodeNova 데이터/AI팀 문서 — 생성 결과 목록\n"
        + "\n".join(index_lines)
        + "\n",
        encoding="utf-8",
    )

    print(f"[완료] docs/ 폴더에 {len(DOC_SPECS)}개 문서를 저장했습니다")
    print("목록: docs/INDEX.txt 를 확인하세요.")


if __name__ == "__main__":
    generate_and_write_docs()
load_dotenv()