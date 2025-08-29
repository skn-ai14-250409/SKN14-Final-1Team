import os
import datetime as dt
from pathlib import Path
from textwrap import dedent
from typing import List, Dict

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DOCS_DIR = Path("docs_cto")
DOCS_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

TEMPERATURE = 0.5
MAX_TOKENS = 1100  # A4 한 장 분량 


hr_org = [
    ("인사·조직 기밀", "임원 인사·보상·승계 계획 문서"),
    ("인사·조직 기밀", "핵심 인재 유지 및 스카우트 전략 보고서"),
    ("인사·조직 기밀", "주요 인사(승진·이동·해고) 관리 문서"),
    ("인사·조직 기밀", "조직 구조 개편안"),
    ("인사·조직 기밀", "핵심 인재 유출 리스크 분석 및 대응 전략"),
]

team_perf = [
    ("팀 성과 / 내부 평가", "내부 평가 피드백 문서_프론트엔드팀 근무 태도 및 기술 기여도 평가"),
    ("팀 성과 / 내부 평가", "내부 평가 피드백 문서_백엔드팀 근무 태도 및 리더십 평가"),
    ("팀 성과 / 내부 평가", "내부 평가 피드백 문서_데이터/AI팀 근무 태도 및 연구 성과 평가"),
    ("팀 성과 / 내부 평가", "팀 성과 자료_프론트엔드팀 KPI 달성률 및 성과 분석"),
    ("팀 성과 / 내부 평가", "팀 성과 자료_백엔드팀 프로젝트 성과 및 보상 연계 보고서"),
    ("팀 성과 / 내부 평가", "팀 성과 자료_데이터/AI팀 R&D 성과 및 투자 대비 효과 분석"),
]

security_risk = [
    ("보안 / 리스크 관리", "취약점 대응 전략 & 보안 사고 대응 매뉴얼"),
    ("보안 / 리스크 관리", "민감 데이터 접근 키·암호화 키 관리 문서"),
    ("보안 / 리스크 관리", "서비스 장애 대응 시나리오 (대규모 트래픽/데이터센터 장애)"),
    ("보안 / 리스크 관리", "내부자 위협 관리 가이드 (계정 유출·권한 남용 대응)"),
]

DOC_SPECS: List[Dict] = [
    *[{"category": c, "title": t} for c, t in hr_org],
    *[{"category": c, "title": t} for c, t in team_perf],
    *[{"category": c, "title": t} for c, t in security_risk],
]

SYSTEM_PROMPT = dedent(
    """
    너는 한국 AI 스타트업 '코드노바(CodeNova)'의 CTO 보좌 문서 저자이다.
    독자: 'CTO' (최고기술책임자).
    금지: 외부 공개 금지 정보(재무 수치/고객 식별정보/계약 조건/미공개 로드맵/내부 비공개 URL).
    문서는 CTO 의사결정에 도움이 되도록, 실행 계획/리스크/체크리스트 중심으로 작성한다.
    출력은 Markdown 형식으로 작성한다 (제목, 소제목, 목록, 표 사용 가능).
"""
).strip()


def make_user_prompt(category: str, title: str, today: str) -> str:
    base = f"""# {title}
(분류: {category}) | 회사: CodeNova | 버전: v1.0 | 작성일: {today}

---
**작성 지침**
- 언어: 한국어, Markdown 형식
- 분량: A4 1장(약 550~750단어) 내외
- CTO가 전략·리스크 관점에서 참고할 수 있도록 작성
- 실행 단계/체크리스트/의사결정 포인트 포함
"""
    if category == "인사·조직 기밀":
        body = dedent(
            """
            ## 포함 섹션
            1. 개요 및 목적
            2. 적용 범위/대상
            3. 실행 계획 (단계별)
            4. 리스크 및 대응 방안
            5. 검증 포인트 (CTO 관점)
            6. 기밀 유지 지침
            7. 개정 이력 (v1.0 — 오늘)
        """
        ).strip()

    elif category == "팀 성과 / 내부 평가":
        body = dedent(
            """
            ## 포함 섹션
            1. 평가 목적 및 기준
            2. 평가 대상 및 범위
            3. 주요 성과 및 태도/기여도 분석
            4. 개선 포인트 및 후속 조치 제안
            5. CTO 의사결정 참고 사항
            6. 개정 이력 (v1.0 — 오늘)
        """
        ).strip()

    elif category == "보안 / 리스크 관리":
        body = dedent(
            """
            ## 포함 섹션
            1. 개요 및 배경
            2. 위협 시나리오 및 영향
            3. 대응 전략 (단계별 실행)
            4. 검증/점검 체크리스트
            5. 리스크 한계 및 보완책
            6. CTO 보고·승인 포인트
            7. 개정 이력 (v1.0 — 오늘)
        """
        ).strip()

    footer = dedent(
        """
        ---
        주의:
        - 민감 지표/내부 링크/고객 실명/상세 재무 수치/비공개 전략은 절대 포함하지 말 것.
        - CTO 의사결정과 리스크 관리에 직결되는 내용 위주로 간결하게 작성할 것.

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
            f"작성일: {today}\n회사: CodeNova | 대상: CTO\n\n---\n"
        )
        out_path.write_text(header + content + "\n", encoding="utf-8")

        index_lines.append(f"{prefix}. {category} - {title} -> {filename}")

    (DOCS_DIR / "INDEX.txt").write_text(
        "CodeNova CTO 전용 기밀 문서\n"
        + "\n".join(index_lines)
        + "\n",
        encoding="utf-8",
    )

    print(f"[완료] docs_cto/ 폴더에 {len(DOC_SPECS)}개 문서를 저장했습니다")
    print("목록: docs_cto/INDEX.txt 를 확인하세요.")


if __name__ == "__main__":
    generate_and_write_docs()