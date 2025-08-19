import os
import datetime as dt
from pathlib import Path
from textwrap import dedent
from typing import List, Dict

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DOCS_DIR = Path("manager(과장)")
DOCS_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

TEMPERATURE = 0.5
MAX_TOKENS = 1100  # A4 한 장 분량 목표치

# -------- 문서 스펙(5개) --------
strategic_docs = [
    ("전사 전략 문서", "회사 중장기 전략 계획"),
    ("전사 전략 문서", "경영진 회의 자료"),
]

finance_docs = [
    ("재무 관련 문서", "연간 예산안/결산 보고서"),
    ("재무 관련 문서", "투자 검토 자료"),
]

confidential_docs = [
    ("고위 기밀 문서", "신규 사업 추진 기획서"),
]

DOC_SPECS: List[Dict] = [
    *[{"category": c, "title": t} for c, t in strategic_docs],
    *[{"category": c, "title": t} for c, t in finance_docs],
    *[{"category": c, "title": t} for c, t in confidential_docs],
]

# -------- 프롬프트 --------
SYSTEM_PROMPT = dedent("""
    너는 디지털 교육회사 M-Core의 내부 문서 저자이다.
    독자: '과장' (고위 관리자).
    문서는 회사의 전략적 의사결정과 재무, 인사 등 민감도가 높은 자료를 포함하는 보고서 형태로 작성한다.
    출력은 평문 텍스트로만 한다.
""").strip()

def make_user_prompt(category: str, title: str, today: str) -> str:
    base = f"""{title}
(분류: {category}) | 회사: M-Core | 버전: v1.0 | 작성일: {today}
{"-"*70}
작성 지침:
- 언어: 한국어, 평문 텍스트(마크다운/표 금지)
- 분량: A4 1장(약 550~750단어) 내외
- 고위 관리자 수준에서 필요한 정보만 포함 (전략, 재무, 기밀 내용 등)
- 고위 관리자의 의사결정을 돕기 위한 핵심 인사이트와 제안을 포함
- 문서 끝에 '다음 개정 제안' 2~3줄
"""
    if category == "전사 전략 문서":
        body = dedent("""
            포함 섹션:
            1) 개요 (문서 목적, 범위)
            2) 전략 비전 및 미션 (재확인 또는 업데이트)
            3) 중장기 로드맵 (3~5년 계획 및 주요 마일스톤)
            4) SWOT 분석 (회사의 내부/외부 요인)
            5) 핵심 전략 과제 (신규 프로젝트, 시장 진출 등)
            6) 자원 배분 계획 (고수준의 예산 및 인적 자원 전략)
            7) 리더십 의사결정 포인트 및 요청 사항
            8) 개정 이력 (v1.0 — 오늘)
        """).strip()
    elif category == "재무 관련 문서":
        body = dedent("""
            포함 섹션:
            1) 개요 (보고서 목적, 보고 기간)
            2) 요약 (핵심 재무 하이라이트, 주요 변동 사항)
            3) 상세 재무제표 요약 (손익계산서, 대차대조표, 현금흐름표)
            4) 예산 대 실적 분석 (계획 대비 성과, 원인 설명)
            5) 핵심 재무 지표 및 비율 (ROI, 수익성 분석, 유동성)
            6) 투자/지출 검토 (주요 지출에 대한 분석)
            7) 재무적 리스크 및 대응 전략
            8) 리더십 제안 및 필요 의사결정 사항
            9) 개정 이력 (v1.0 — 오늘)
        """).strip()
    else:  # 고위 기밀 문서
        body = dedent("""
            포함 섹션:
            1) 요약 (프로젝트 목적, 시장 기회, 핵심 목표)
            2) 프로젝트 개념 및 범위 (상세 비즈니스 모델, 목표 시장)
            3) 시장 및 경쟁 분석 (시장 규모, 경쟁사 현황)
            4) 재무 예상 (수익 예측, 비용 분석, ROI)
            5) 실행 로드맵 (단계별 계획, 주요 마일스톤)
            6) 필요 자원 (투자 필요액, 인력, 기술)
            7) 리스크 평가 및 비상 계획 (운영, 재무 리스크)
            8) 진행/중단 결정 포인트
            9) 개정 이력 (v1.0 — 오늘)
        """).strip()

    footer = dedent("""
        주의:
        - 문서는 고위 관리자의 의사결정을 돕기 위한 전략적이고 고수준의 내용으로 작성해야 합니다.
        - 운영 실무 수준의 세부 내용은 포함하지 않습니다.
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

        header = (
            f"===== {category} | {title} =====\n"
            f"작성일: {today}\n"
            f"회사: M-Core | 대상: 과장(고위 관리자)\n"
            f"{'-'*70}\n"
        )
        out_path.write_text(header + content + "\n", encoding="utf-8")

        index_lines.append(f"{prefix}. {category} - {title} -> {filename}")

    # 인덱스 파일 작성
    (DOCS_DIR / "INDEX.txt").write_text(
        "M-Core 사내문서(과장용) — 생성 결과 목록\n" +
        "\n".join(index_lines) + "\n",
        encoding="utf-8"
    )

    print(f"[완료] docs/ 폴더에 {len(DOC_SPECS)}개 문서를 저장했습니다.")
    print("목록: docs/INDEX.txt 를 확인하세요.")

if __name__ == "__main__":
    generate_and_write_docs()