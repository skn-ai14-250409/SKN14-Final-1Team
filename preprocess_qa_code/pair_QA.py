import os
import re
import json
import time
import hashlib
from openai import OpenAI
import tiktoken
from dotenv import load_dotenv

load_dotenv()

# =========================
# 설정
# =========================
ROOT_DIR = "../GOOGLE_API_DATA"
OUT_JSONL = "./google_api_qa_dataset.jsonl"  
MODEL = "gpt-4o-mini"
PAIR_MAX_QA = 5  # 페어(또는 단일 청크)당 최대 Q&A 개수
CHUNK_TOKENS = 900  # 청크 크기(토큰 기준)
CHUNK_OVERLAP_TOKENS = 150  # 청크 오버랩(토큰 기준)
PAIR_WINDOW = 2  # 연속 청크 페어 크기
MAX_CONTEXT_TOKENS = 4096  # 모델 컨텍스트 상한
MAX_RETRY = 4  # API 재시도 횟수8
client = OpenAI()  # OPENAI_API_KEY 필요

enc = tiktoken.get_encoding("cl100k_base")


# =========================
# 유틸
# =========================

def parse_source_meta(text):
    """문서 상단에서 Source URL 추출."""
    head = text[:2000] 
    m_url = re.search(r'(?i)^Source\s*URL\s*:\s*(\S+)', head, flags=re.M)
    return m_url.group(1).strip() if m_url else None


def smart_split(text):
    """토큰 기반 청킹 + 오버랩."""
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []
    toks = enc.encode(text) 
    chunks = []
    '''
    CHUNK_TOKENS: 900 토큰
    CHUNK_OVERLAP_TOKENS: 150 토큰
    step: 900 - 150 = 750 토큰

    첫번째 청크. toks[0:900]
    두번쨰 청크. toks[750:1650]
    '''
    step = max(1, CHUNK_TOKENS - CHUNK_OVERLAP_TOKENS)
    for i in range(0, len(toks), step):
        block = toks[i:i + CHUNK_TOKENS] 
        if not block: break
        chunk_text = enc.decode(block).strip()
        if chunk_text:
            chunks.append(chunk_text)
    return chunks


def make_pairs(chunks, window=PAIR_WINDOW):
    """연속 청크 페어 목록 생성: (0,[0,1]), (1,[1,2]), …"""
    if window < 2 or len(chunks) < 2:
        return []
    return [(i, chunks[i:i + window]) for i in range(len(chunks) - (window - 1))]


def trim_to_context_limit(text):
    """컨텍스트 초과 시 텍스트를 토큰 기준으로 상한 내로 자름."""
    toks = enc.encode(text)
    if len(toks) <= MAX_CONTEXT_TOKENS:
        return text
    return enc.decode(toks[:MAX_CONTEXT_TOKENS])


def hash_id(*parts):
    """안정적 레코드 ID 생성."""
    h = hashlib.sha256()
    for p in parts:
        h.update((p or "").encode("utf-8"));
        h.update(b"|")
    return h.hexdigest()[:32]


def json_loads_strict_or_strip_codefence(s):
    """
    response_format=json_object 덕분에 보통은 바로 json.loads로 충분.
    혹시 모를 코드펜스(```json ... ```)만 제거하는 얇은 래퍼.
    """
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.I | re.S)
    return json.loads(s)

# 폴더명 추출 (_docs_crawled 잘라내기)
def get_api_tag_from_path(path: str) -> str:
    folder = os.path.basename(os.path.dirname(path))
    if folder.endswith("_docs_crawled"):
        return folder.replace("_docs_crawled", "")
    return folder

# =========================
# 모델 호출
# =========================
def ask_model(pair_text, n, source_url, prev_qs=None, tag=""):
    """
    해당 텍스트 범위에서 Q&A n개(JSON) 생성. 없으면 빈 리스트 반환.
    - 문서 범위 밖 정보 금지
    - 실무 친화적 질문/정확한 답변
    - prev_qs: 이미 만든 질문(원문 문자열) 목록 → 중복 생성 금지 유도
    """
    if n <= 0:
        return []

    prev_qs = prev_qs or []
    prev_block = ""
    if prev_qs:
        # prev_qs[:-30] : 리스트에서 마지막 30개를 제외한 앞부분 전부
        # prev_qs[-30:] : 최근 30개
        preview_prev = "\n".join(f"- {q}" for q in prev_qs[-30:])
        prev_block = f"\n\n이미 생성된(중복 금지) 질문 목록:\n{preview_prev}\n"

    system_prompt = (
        "당신은 구글 API 중 {tag} API의 공식 문서 텍스트에서만 근거를 삼아 Q&A를 만듭니다. "
        "문서에 명시된 내용만 사용하고 추측은 금지합니다. 실무자가 바로 쓰도록 자세하고 이해하기 쉽게 답변해주세요."
        "답변은 한국어로 작성하되, 핵심 용어/식별자(예: API/메서드/파라미터/enum/필드/클래스/에러코드/리소스 이름)는 "
        "원문 영문을 괄호로 함께 표기합니다. 예: a1 범위 → a1 범위(A1 notation), 그리드 범위(gridRange). "
        "코드 블록은 원문을 절대 수정/번역/재포맷하지 말고 그대로 포함합니다."
    )
    url_hint = f"\n- 참고 URL(있으면): {source_url}" if source_url else ""

    user_prompt = f"""
아래는 한 문서의 (연속) 청크 범위입니다. 이 범위에서만 Q&A {n}개를 JSON으로 만들어 주세요.

**요구사항:**
- 문서 범위를 벗어난 정보 금지
- 질문은 실무 친화적으로 구체적·명확하게
- 답변은 문서 용어/표기 준수
- 각 항목: question, answer
- 아래 '이미 생성된 질문 목록'과 **중복되지 않게** 새 질문만 생성

[언어/표기 규칙]
- **출력은 한국어**로 하되, 모든 핵심 기술 용어/식별자/상수/메서드/필드/에러명/스키마명/리소스명은 **원문 영문을 괄호로 병기**합니다.
  - 예: "일련번호(serial number)", "그리드 범위(gridRange)", "데이터셋(dataset)", "프로젝트 ID(projectId)"
  - 이미 한글로 굳어진 일반 용어(예: 날짜, 요청 본문)만 자연스러운 한국어로, **고유 식별자는 절대 번역하지 마세요**.
- 문서가 **영문**이면 내용을 **정확하게 한국어로 설명**하되, 고유 명칭은 괄호 병기 원칙을 지킵니다.
- 문서가 **한글**이면 자연스러운 한국어로 유지하고, 필요 시 핵심 용어에만 영문 괄호 병기.
- **코드 블록은 원문 그대로** 포함하며, 공백/줄바꿈/따옴표/주석/언어 표시는 **절대 수정하지 않습니다.**
  - 코드 내 식별자/주석/문자열도 번역/가공하지 않습니다.

[중요한 제약사항]
- 문서에 명시된 내용만을 기반으로 질문과 답변을 작성하세요
- 문서에 없는 내용이나 추측, 일반적인 지식을 추가하지 마세요
- 답변은 반드시 문서 내용을 직접 참조해야 합니다
- 확실하지 않은 내용은 포함하지 마세요
- 적절한 코드/사용법/오류 해결/설정 방법이 문서에 없다면 해당 항목은 **생성하지 마세요** (그 대신 다른 항목을 생성)
- 문서에 코드 예제가 있으면 answer에 해당 코드 블록을 포함하세요.
    - 언어가 여러 개면 **Python, Java, 기타** 모든 언어에 대해 각각 질문과 답변을 생성하세요.
    - 각 항목은 하나의 언어 코드만 포함해야 합니다. (예: Python 질문/답변, Java 질문/답변 별도로 생성)
    - answer의 코드 블록은 반드시 복사해 실행 가능한 최소 단위로 유지하세요.

[우선 순위 주제]
1. 코드 예시와 구현 방법
2. API 사용법, 파라미터/옵션 설명, 요청/응답 구조
3. 오류 메시지/원인/대응과 문제 해결책
4. 설정/권한/제한/쿼터 등 구성 옵션
5. 실제 사용 시나리오/주의사항과 예제

{url_hint}

{prev_block}

[원문 시작]
{pair_text}
[원문 끝]

JSON 스키마:
{{
  "items": [
    {{
      "question": "…",
      "answer": "…"
    }}
  ]
}}
""".strip()

    for attempt in range(1, MAX_RETRY + 1):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.,
                max_tokens=1100,
            )
            data = json_loads_strict_or_strip_codefence(resp.choices[0].message.content)
            items = data.get("items", []) if isinstance(data, dict) else []
            return items[:n]
        except Exception:
            if attempt == MAX_RETRY:
                return []
            time.sleep(0.8 * attempt)


# =========================
# 문서 처리
# =========================
def build_record(q, a, doc_path, pair_index,
                 chunk_indices, pair_text,
                 source_url, tag):
    """RAG 친화 JSON 레코드 + 추적 정보."""
    return {
        "question": q.strip(),
        "answer": a.strip(),
        "source": [source_url or f"file://{doc_path}"],
        "tags": tag,
        "last_verified": "2025-08-19",
        "source_file": os.path.basename(doc_path),
    }


def process_one_file(file_path, out_fh):
    """
    단일 문서 처리:
    - 상단 메타(Source URL) 추출 → 토큰 청킹
    - 청크=1이면 그 1개로 최대 5개 생성
    - 청크>=2면 (연속 페어)마다 최대 5개 생성
    - 생성 없으면 스킵, 결과는 JSONL append
    """
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:  # 파일 열기
        text = f.read()  # 파일 내용 읽기
    if not text.strip():  # 비어 있는 파일은 처리하지 않음
        return 0

    source_url = parse_source_meta(text)  # Source URL 추출
    chunks = smart_split(text)  # 텍스트를 청크로 나누기
    written = 0  # 작성된 Q&A 수 초기화

    # -------추가----------------
    tag = get_api_tag_from_path(file_path)
    asked_qs_for_model = []  # 모델에 보여줄 '이미 만든 질문' 목록
    

    # (A) 청크 1개뿐
    if len(chunks) == 1:
        pair_text = trim_to_context_limit(chunks[0])
        items = ask_model(pair_text, PAIR_MAX_QA, source_url, prev_qs=asked_qs_for_model, tag=tag)
        for it in items:
            q, a = (it.get("question") or "").strip(), (it.get("answer") or "").strip()
            if not q or not a:
                continue

            asked_qs_for_model.append(q)

            rec = build_record(q, a, file_path, 0, [0], pair_text, source_url, tag)
            out_fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1
        print(f'단일페어 / 금지질문 : {asked_qs_for_model}')
        return written

    # (B) 청크 >= 2 → (1,2), (2,3) ...
    pairs = make_pairs(chunks, window=PAIR_WINDOW)
    if not pairs:
        return 0

    for (pair_idx, cg) in pairs:
        pair_text = trim_to_context_limit("\n\n---\n\n".join(cg))
        items = ask_model(pair_text, PAIR_MAX_QA, source_url, prev_qs=asked_qs_for_model, tag=tag)
        if not items:
            continue

        chunk_indices = list(range(pair_idx, pair_idx + len(cg)))
        for it in items:
            q, a = (it.get("question") or "").strip(), (it.get("answer") or "").strip()
            if not q or not a:
                continue

            asked_qs_for_model.append(q)

            rec = build_record(q, a, file_path, pair_idx, chunk_indices, pair_text, source_url, tag)
            out_fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1
        print(f'페어번호: {pair_idx} / 금지질문 : {asked_qs_for_model}')

    return written


# =========================
# 엔트리포인트
# =========================
def walk_and_generate():
    """폴더 재귀 순회 → 모든 문서를 처리 → 하나의 JSONL로 누적 저장."""
    os.makedirs(os.path.dirname(OUT_JSONL) or ".", exist_ok=True)  # 저장할 폴더 생성
    total_docs, total_qas = 0, 0  # 총 문서와 Q&A 수 초기화
    with open(OUT_JSONL, "a", encoding="utf-8") as out_fh:  # JSONL 파일 열기 (append 모드)
        for root, _, files in os.walk(ROOT_DIR):  # ROOT_DIR 내 모든 파일 재귀 순회
            for name in files:  # 각 파일에 대해
                if not name.lower().endswith(".txt"): continue  # .txt 파일만 처리
                path = os.path.join(root, name)  # 파일 경로 만들기
                print(f"[DOC] {path}")  # 파일 경로 출력
                cnt = process_one_file(path, out_fh)  # 파일 처리 후 Q&A 수 반환
                print(f"  -> {cnt} QAs")  # 처리된 Q&A 수 출력
                total_docs += 1  # 문서 수 증가
                total_qas += cnt  # Q&A 수 증가
    print(f"\n[DONE] docs={total_docs}, qas={total_qas}, out={OUT_JSONL}")  # 전체 처리 결과 출력


walk_and_generate()
