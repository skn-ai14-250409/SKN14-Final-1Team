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

# -------- 문서 스펙(사장 전용, 10개) --------
# 변수명/틀은 유지하고, 내용만 CEO용으로 교체
product_manuals = [
    ("전사 경영 전략", "전사 중장기 전략 로드맵 (2025–2030)"),
    ("M&A/투자", "M&A 전략 및 실사(Due Diligence) 플레이북"),
    ("글로벌 진출", "글로벌 진출 및 해외 법인 설립 계획"),
]
it_guides = [
    ("재무 패키지", "전사 기밀 재무 패키지 (손익/현금흐름/세그먼트)"),
    ("자금조달/IR", "자금조달 및 투자유치 마스터플랜"),
    ("임원 인사·보상·승계", "임원 인사·보상·승계 정책"),
]
weekly_plans = [
    ("핵심 인재", "핵심 인재 유지 및 스카우트 전략"),
    ("법률/규제 대응", "법률 및 규제기관 대응 브리프"),
    ("파트너십/NDA", "대외 파트너십 NDA 및 계약 전략"),
]
project_task = [
    ("위기 대응/비상 경영", "위기 대응 및 비상 경영 매뉴얼"),
]

DOC_SPECS: List[Dict] = [
    *[{"category": c, "title": t} for c, t in product_manuals],
    *[{"category": c, "title": t} for c, t in it_guides],
    *[{"category": c, "title": t} for c, t in weekly_plans],
    *[{"category": c, "title": t} for c, t in project_task],
]

# -------- 프롬프트(사장 전용으로 변경) --------
SYSTEM_PROMPT = dedent("""
    너는 디지털 교육회사 M-Core의 '최고 경영진 전용' 내부 문서 저자이다.
    독자: '사장(CEO/임원)'.
    허용: 전략/재무/법률/위기 대응 등 고급 의사결정 정보를 포함하되, 실제 수치·실명·계약 세부는 사용하지 말고
          '범위형(예: 45~55억)' 또는 'XX/YY' 더미 표기만 사용한다.
    금지: 고객/직원 실명, 식별 가능한 개인정보, 내부 비공개 URL, API 키/비밀번호 등 비밀 토큰.
    어조: 합쇼체(사내 공문체, 정중·명료), 실행 가능한 결정/원칙/체크리스트 중심.
    출력: 평문 텍스트만 사용(마크다운/표 금지).
""").strip()

def make_user_prompt(category: str, title: str, today: str) -> str:
    base = f"""{title}
(분류: {category}) | 회사: M-Core | 버전: v1.0 | 작성일: {today}
{"-"*70}
작성 지침:
- 언어: 한국어, 평문 텍스트(마크다운/표 금지)
- 분량: A4 1장(약 550~750단어) 내외
- 독자: 사장(CEO). 전략/재무/법률/위기 의사결정 관점으로 작성
- 모든 수치·고유명사는 범위형 또는 더미 표기로 표기(예: XX억, YY% 등)
- 결론 중심의 결정 항목, 책임 주체, 검증 포인트를 포함
- 문서 끝에 '다음 개정 제안' 2~3줄
"""

    if category == "전사 경영 전략":
        body = dedent("""
            포함 섹션:
            1) 경영 요약(핵심 목표 3~5개, 우선순위/투자원칙)
            2) 전략 축(제품/시장/수익화/조직)과 자본 배분 원칙
            3) 분기 운영 프레임(OKR 상한/하한, 피벗 규칙)
            4) 주요 리스크/가정과 선제 대응
            5) 승인 라인/거버넌스(CEO/이사회/BU장 역할)
            6) 커뮤니케이션 원칙(대내/대외 메시지)
        """).strip()

    elif category == "M&A/투자":
        body = dedent("""
            포함 섹션:
            1) 투자 논제(전략 적합성, 시너지 가설)
            2) 타깃 평가 프레임(시장/제품/기술/HR/보안)
            3) 실사 체크리스트 요약(재무/법무/세무/기술/HR)
            4) 거래 구조 옵션(에쿼티/부채/전환, 이연·언아웃)
            5) Day-1/100일 PMI 로드맵(제품/고객/조직/브랜드)
            6) 킬 스위치/리스크 트리거
        """).strip()

    elif category == "글로벌 진출":
        body = dedent("""
            포함 섹션:
            1) 우선 시장 선정 논리(규모/성장/규제/인재)
            2) 진입 전략(직판/리셀러/합작)과 기준
            3) 법인 설립/세무·규제 대응 절차(요약)
            4) 현지화 원칙(제품/가격/지원/브랜드)
            5) 핵심 인력/채용·리텐션 방안
            6) 중단·피벗 기준과 보고 주기
        """).strip()

    elif category == "재무 패키지":
        body = dedent("""
            포함 섹션:
            1) 손익 요약(매출/원가/판관비/EBITDA 추이, 범위형 수치)
            2) 현금흐름 요약(영업/투자/재무, 런웨이)
            3) 세그먼트 분석(제품/지역/고객군 수익성)
            4) 경보 임계치(비용/현금/성장)와 조정 레버
            5) 보고/검토/승인 사이클(월간/분기)
        """).strip()

    elif category == "자금조달/IR":
        body = dedent("""
            포함 섹션:
            1) 자금 수요 시나리오(Base/Up/Down)와 전제
            2) 조달 옵션 매트릭스(지분/부채/전환, 장단점)
            3) 희석/지배구조 가이드(한계·완화책)
            4) 핵심 IR 메시지(지표/스토리라인/증빙)
            5) 딜 실행 타임라인과 승인 체크포인트
        """).strip()

    elif category == "임원 인사·보상·승계":
        body = dedent("""
            포함 섹션:
            1) 임원 역할/요건(역량/가치 기준)
            2) 평가/보상 체계(OKR, 현금+LTI, 더미 수치)
            3) 승계 플랜(섀도우/백업/인수인계 규칙)
            4) 리텐션/갈등 관리(투명성/벤치마크)
            5) 보안/윤리 준수 및 제재 기준
        """).strip()

    elif category == "핵심 인재":
        body = dedent("""
            포함 섹션:
            1) 핵심 인재 정의와 스코어링(성과/영향/대체난이도)
            2) 리텐션 패키지(보상/성장/보직, 더미 표기)
            3) 스카우트 플레이북(타깃/접점/레퍼런스)
            4) 온보딩/코칭/조기 경보 시그널
            5) 리스크 시나리오와 대응
        """).strip()

    elif category == "법률/규제 대응":
        body = dedent("""
            포함 섹션:
            1) 주요 이슈 현황판(우선순위/영향/시한)
            2) 전략 옵션(합의/소송/정책 대응)
            3) 메시지 라인(내부 공지/대외 공문)
            4) 외부 자문/로펌 운용 원칙(성과 연동)
            5) 보고 체계와 기록 보존
        """).strip()

    elif category == "파트너십/NDA":
        body = dedent("""
            포함 섹션:
            1) 파트너 분류(기술/유통/재무/공공)
            2) 계약 구조(단계적 PoC→본 계약, KPI 연동)
            3) 보상/벌칙 및 조정권(더미)
            4) SLA/품질/보안 기준과 감사 권한
            5) 해지/전환·탈출 조건
        """).strip()

    elif category == "위기 대응/비상 경영":
        body = dedent("""
            포함 섹션:
            1) 위기 유형(사이버/데이터유출/사회적 이슈/재난)
            2) 단계 절차(탐지→격리→소통→복구→사후 개선)
            3) CMT(위기관리위) 구성/권한/보고 라인
            4) 내부/외부 커뮤니케이션 승인 규칙
            5) 훈련/DR 전환 기준과 일정
        """).strip()

    else:
        body = dedent("""
            포함 섹션:
            1) 경영 요약 및 의사결정 포인트
            2) 실행 프레임/책임 주체/검증 포인트
            3) 리스크/가정/트리거 및 대응
            4) 승인/보고/변경 관리
        """).strip()

    footer = dedent("""
        주의:
        - 실명/식별정보/내부 링크/비밀 토큰 금지.
        - 수치는 모두 범위형 또는 더미(XX/YY)로 표기.
        - CEO 관점에서 결론과 책임 주체가 분명해야 하며, 실행·검증 포인트를 구체화할 것.
        - 문서 끝에 '다음 개정 제안' 2~3줄 포함.
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

        # 헤더의 대상만 사장(CEO)로 변경. 나머지 출력 형식은 동일 유지.
        header = f"===== {category} | {title} =====\n작성일: {today}\n회사: M-Core | 대상: 사장(CEO)\n{'-'*70}\n"
        out_path.write_text(header + content + "\n", encoding="utf-8")

        index_lines.append(f"{prefix}. {category} - {title} -> {filename}")

    # 인덱스 파일 작성(틀 유지)
    (DOCS_DIR / "INDEX.txt").write_text(
        "M-Core 내부문서(사장 전용) — 생성 결과 목록\n" +
        "\n".join(index_lines) + "\n",
        encoding="utf-8"
    )

    print(f"[완료] docs/ 폴더에 {len(DOC_SPECS)}개 문서를 저장했습니다.")
    print("목록: docs/INDEX.txt 를 확인하세요.")

if __name__ == "__main__":
    generate_and_write_docs()
