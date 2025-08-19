import os
import datetime as dt
from pathlib import Path
from textwrap import dedent
from typing import List, Dict

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DOCS_DIR = Path("docs2")
DOCS_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")  # 실제 존재하는 모델로 변경

TEMPERATURE = 1
MAX_TOKENS = 1100

# -------- 문서 스펙(부장용 10개) --------
executive_documents = [
    ("전사 전략 문서", "엠코아 중장기 전략 계획 (2025-2028)"),
    ("전사 전략 문서", "경영진 회의 자료 (2025년 Q1)"),
    ("전사 전략 문서", "2025년도 성장 목표 및 KPI"),
    ("재무 관련 문서", "2025 연간 예산안"),
    ("재무 관련 문서", "2025 결산 보고서"),
    ("재무 관련 문서", "2025 투자 검토 자료"),
    ("고위 기밀 문서", "2025 신규 사업 추진 기획서"),
    ("고위 기밀 문서", "대외 협력/파트너십 계약서 초안"),
    ("고위 기밀 문서", "주요 인사(승진/이동/해고) 관련 문서"),
    ("고위 기밀 문서", "M-Core 2.0 론칭 및 파트너십 전략")
]

DOC_SPECS: List[Dict] = [
    *[{"category": c, "title": t} for c, t in executive_documents],
]

# -------- 프롬프트 --------
SYSTEM_PROMPT = dedent("""\
    너는 디지털 교육회사 M-Core의 고위 관리자용 내부 문서 저자이다.
    독자: '부장(고위 관리자)'.
    금지: 일반 직원/대리/과장이 접근할 수 없는 전략/재무/인사/고위 기밀 자료.
    문서는 구체적이고, 실행 가능한 단계/체크리스트 중심으로, 평문 텍스트로만 작성한다.
""").strip()


def make_user_prompt(category: str, title: str, today: str) -> str:
    base = f"""{title}
(분류: {category}) | 회사: M-Core | 버전: v1.0 | 작성일: {today}
{"-" * 70}
작성 지침:
- 언어: 한국어, 평문 텍스트(마크다운/표 금지)
- 분량: A4 1장(약 850~1000단어) 내외
- 부장 수준에서 필요한 정보만 포함, 민감/전략/고객 식별정보 제외
- 실행 단계/체크리스트/검증 포인트 포함
"""
    if category == "전사 전략 문서":
        body = dedent("""\
            포함 섹션:
            1) 개요(중장기 전략 목표)
            2) 핵심 목표 및 KPI(연간 목표 포함)
            3) 전략적 방향(시장/기술 혁신/교육 확대)
            4) 예산 계획(각 부문별 예산 및 리소스 배분)
            5) 리스크 관리 계획(위험 요소 및 대응 방안)
            6) 변경 이력(v1.0 — 오늘)
        """).strip()
    elif category == "재무 관련 문서":
        body = dedent("""\
            포함 섹션:
            1) 예산/결산 개요(수익, 지출, 예상 순이익)
            2) 예산 계획(각 부문/부서별 배분 계획)
            3) 결산 보고서(실적 분석 및 예측)
            4) 투자 및 자금 운영 계획(자본 지출 및 확보 계획)
            5) 리스크 관리 및 대응 방안
            6) 변경 이력(v1.0 — 오늘)
        """).strip()
    elif category == "고위 기밀 문서":
        body = dedent("""\
            포함 섹션:
            1) 신규 사업 개요(목표 및 필요성)
            2) 사업 계획서(전략적 방향 및 예산)
            3) 대외 파트너십 계획(협상 조건 및 예상 결과)
            4) 주요 인사 관련 계획(승진/이동/해고 등)
            5) 법률/규정 관련 검토 사항
            6) 변경 이력(v1.0 — 오늘)
        """).strip()

    footer = dedent("""\
        주의:
        - 민감 지표/내부 링크/고객 실명/재무 수치/전략 비공개 정보는 쓰지 말 것.
        - 고위 관리자 수준에서만 필요한 정보로 구체적으로 작성할 것.
    """).strip()

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
    client = OpenAI(api_key=API_KEY)  # 클라이언트 초기화를 함수 시작 부분으로 이동

    today = dt.date.today().isoformat()
    index_lines = []

    for idx, spec in enumerate(DOC_SPECS, start=1):
        category, title = spec["category"], spec["title"]
        user_prompt = make_user_prompt(category, title, today)

        try:
            # 표준 채팅 완성 API 호출 (올바른 형식)
            completion = client.chat.completions.create(
                model=MODEL,  # 환경변수에서 가져온 모델 사용
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS
            )

            # 응답 내용 추출 (올바른 방법)
            content = completion.choices[0].message.content.strip()

            if not content:
                raise ValueError(f"빈 응답이 반환되었습니다. 제목: {title}")

            print(f"[성공] 문서 생성 완료: {title}")

        except Exception as e:
            print(f"[오류] 문서 생성 실패: {title} - {str(e)}")
            continue

        # 파일 생성
        prefix = f"{idx:02d}"
        filename = f"{prefix}_{safe_slug(category)}__{safe_slug(title)}.txt"
        out_path = DOCS_DIR / filename

        header = f"===== {category} | {title} =====\n작성일: {today}\n회사: M-Core | 대상: 부장(고위 관리자)\n{'-' * 70}\n"
        out_path.write_text(header + content + "\n", encoding="utf-8")

        index_lines.append(f"{prefix}. {category} - {title} -> {filename}")

    # 인덱스 파일 작성
    (DOCS_DIR / "INDEX.txt").write_text(
        "M-Core 사내문서(부장용) — 생성 결과 목록\n" +
        "\n".join(index_lines) + "\n",
        encoding="utf-8"
    )

    print(f"[완료] docs/ 폴더에 {len(DOC_SPECS)}개 문서를 저장했습니다.")
    print("목록: docs/INDEX.txt 를 확인하세요.")


if __name__ == "__main__":
    generate_and_write_docs()