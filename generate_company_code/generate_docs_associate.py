import os
import datetime as dt
from pathlib import Path
from textwrap import dedent
from typing import List, Dict

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DOCS_DIR = Path("docs")
DOCS_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

TEMPERATURE = 0.5
MAX_TOKENS = 1100  # A4 한 장 분량 목표치

# -------- 문서 스펙(10개) --------
product_manuals = [
    ("제품/서비스 매뉴얼", "M-Core LMS 웹 포털 사용자 매뉴얼 (직원용)"),
    ("제품/서비스 매뉴얼", "M-Core 모바일 학습 앱 운영 매뉴얼 (직원용)"),
    ("제품/서비스 매뉴얼", "M-Core 콘텐츠 업로더 & 저작도구 사용 매뉴얼 (직원용)"),
]
it_guides = [
    ("사내 IT 시스템 사용 가이드", "사내 계정/SSO(Okta) & 비밀번호 정책 가이드"),
    ("사내 IT 시스템 사용 가이드", "MDM/디바이스 보안 & VPN 접속 가이드"),
    ("사내 IT 시스템 사용 가이드", "헬프데스크(Helpdesk) 티켓 발행/처리 가이드"),
]
weekly_plans = [
    ("주간 업무 계획", "콘텐츠팀 주간 업무 계획"),
    ("주간 업무 계획", "영업지원팀 주간 업무 계획"),
    ("주간 업무 계획", "고객지원팀 주간 업무 계획"),
]
project_task = [
    ("프로젝트별 Task 분배표", "M-Core Microlearning 2.0 론칭 프로젝트 Task 분배표"),
]

DOC_SPECS: List[Dict] = [
    *[{"category": c, "title": t} for c, t in product_manuals],
    *[{"category": c, "title": t} for c, t in it_guides],
    *[{"category": c, "title": t} for c, t in weekly_plans],
    *[{"category": c, "title": t} for c, t in project_task],
]

# -------- 프롬프트 --------
SYSTEM_PROMPT = dedent(
    """
    너는 디지털 교육회사 M-Core의 내부 문서 저자이다.
    독자: '사원(일반 직원)'.
    금지: 회사 전략/재무·민감 수치/계약 조건/미공개 로드맵/고객 식별정보/개인정보/내부 비공개 URL.
    문서는 바로 실행 가능한 단계/체크리스트 중심으로, 평문 텍스트로만 작성한다.
"""
).strip()


def make_user_prompt(category: str, title: str, today: str) -> str:
    base = f"""{title}
(분류: {category}) | 회사: M-Core | 버전: v1.0 | 작성일: {today}
{"-"*70}
작성 지침:
- 언어: 한국어, 평문 텍스트(마크다운/표 금지)
- 분량: A4 1장(약 550~750단어) 내외
- 사원 수준에서 필요한 정보만 포함, 민감/전략/고객 식별정보 제외
- 실행 단계/체크리스트/검증 포인트 포함
- 문서 끝에 '다음 개정 제안' 2~3줄
"""
    if category == "제품/서비스 매뉴얼":
        body = dedent(
            """
            포함 섹션:
            1) 개요(주요 시나리오 3개)
            2) 접근/권한(최소권한 원칙, 계정 요청 방법)
            3) 기본 사용 절차(단계별 + 검증 포인트)
            4) 운영 체크리스트(일일/주간)
            5) 문제 해결 FAQ(5~7개)
            6) 보안/컴플라이언스(직원 관점)
            7) 변경 이력(v1.0 — 오늘)
        """
        ).strip()
    elif category == "사내 IT 시스템 사용 가이드":
        body = dedent(
            """
            포함 섹션:
            1) 적용 대상/요구사항
            2) 시작하기(SSO/MFA, VPN 등)
            3) 표준 사용 절차(스텝/검증 포인트)
            4) 보안 모범사례(Do/Don't)
            5) 문제 해결 & 지원 채널
            6) 데이터/프라이버시
            7) 개정 이력(v1.0 — 오늘)
        """
        ).strip()
    elif category == "주간 업무 계획":
        body = dedent(
            f"""
            이번 주차 기준 계획을 작성.
            포함 섹션:
            1) 이번 주 최우선 과제(Top 3: 목표/성공기준/담당/마감)
            2) 팀원별 주요 작업(3~5개, 의존성/리스크 포함)
            3) 회의/마일스톤
            4) 협업/의존성
            5) 리스크/차질 대비
            6) 마감 후 점검(완료 기준/산출물 위치)
        """
        ).strip()
    else:  # 프로젝트별 Task 분배표
        body = dedent(
            """
            포함 섹션:
            1) 역할과 책임(요약)
            2) 주요 작업 분배(에픽/담당/완료기준/의존성/마일스톤)
            3) 커뮤니케이션/의사결정 규칙
            4) 품질/보안/준법 체크
            5) 산출물/보관 위치
            6) 리스크 & 완화
            7) 개정 이력(v1.0 — 오늘)
        """
        ).strip()

    footer = dedent(
        """
        주의:
        - 민감 지표/내부 링크/고객 실명/재무 수치/전략 비공개 정보는 쓰지 말 것.
        - 직원이 당장 실행할 수 있게 단계/체크리스트를 구체적으로 작성할 것.
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

        header = f"===== {category} | {title} =====\n작성일: {today}\n회사: M-Core | 대상: 사원(일반 직원)\n{'-'*70}\n"
        out_path.write_text(header + content + "\n", encoding="utf-8")

        index_lines.append(f"{prefix}. {category} - {title} -> {filename}")

    # 인덱스 파일 작성
    (DOCS_DIR / "INDEX.txt").write_text(
        "M-Core 사내문서(사원용) — 생성 결과 목록\n" + "\n".join(index_lines) + "\n",
        encoding="utf-8",
    )

    print(f"[완료] docs/ 폴더에 {len(DOC_SPECS)}개 문서를 저장했습니다.")
    print("목록: docs/INDEX.txt 를 확인하세요.")


if __name__ == "__main__":
    generate_and_write_docs()
