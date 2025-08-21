import os
import re
import json
import time
import hashlib
import datetime
from openai import OpenAI
import tiktoken
from dotenv import load_dotenv

load_dotenv()

# =========================
# 설정
# =========================
ROOT_DIR = "./people_docs_crawled"   # 재귀 순회할 최상위 폴더
OUT_JSONL = "./people_qa_dataset3.jsonl"         # 결과를 저장할 JSONL 파일
MODEL = "gpt-4o-mini"
PAIR_MAX_QA = 5                          # 페어(또는 단일 청크)당 최대 Q&A 개수
CHUNK_TOKENS = 900                       # 청크 크기(토큰 기준)
CHUNK_OVERLAP_TOKENS = 150                # 청크 오버랩(토큰 기준)
PAIR_WINDOW = 2                          # 연속 청크 페어 크기
MAX_CONTEXT_TOKENS = 4096                # 모델 컨텍스트 상한
MAX_RETRY = 4                            # API 재시도 횟수

client = OpenAI()                         # OPENAI_API_KEY 필요
enc = tiktoken.get_encoding("cl100k_base")

# =========================
# 유틸
# =========================
def parse_source_meta(text):
    """문서 상단에서 Source URL 추출."""
    head = text[:2000]  # 문서 상단에서 첫 2000자만 처리
    m_url = re.search(r'(?i)^Source\s*URL\s*:\s*(\S+)', head, flags=re.M)
    return m_url.group(1).strip() if m_url else None

def smart_split(text):
    """토큰 기반 청킹 + 오버랩."""
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []
    toks = enc.encode(text)  # tiktoken으로 텍스트를 토큰으로 변환
    chunks = []
    step = max(1, CHUNK_TOKENS - CHUNK_OVERLAP_TOKENS)
    for i in range(0, len(toks), step):
        block = toks[i:i + CHUNK_TOKENS]  # 청크 크기만큼 자르기
        if not block: break
        chunk_text = enc.decode(block).strip()
        if chunk_text:
            chunks.append(chunk_text)
    return chunks

def make_pairs(chunks, window=PAIR_WINDOW):
    """연속 청크 페어 목록 생성: (0,[0,1]), (1,[1,2]), …"""
    if window < 2 or len(chunks) < 2:
        return []
    return [(i, chunks[i:i+window]) for i in range(len(chunks) - (window - 1))]

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
        h.update((p or "").encode("utf-8")); h.update(b"|")
    return h.hexdigest()[:32]

def json_loads_strict_or_strip_codefence(s):
    """
    response_format=json_object 덕분에 보통은 바로 json.loads로 충분.
    혹시 모를 코드펜스(```json ... ```)만 제거하는 얇은 래퍼.
    """
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.I|re.S)
    return json.loads(s)

# =========================
# 모델 호출
# =========================
def ask_model(pair_text, n, source_url):
    """
    해당 텍스트 범위에서 Q&A n개(JSON) 생성. 없으면 빈 리스트 반환.
    - 문서 범위 밖 정보 금지
    - 실무 친화적 질문/정확한 답변
    """
    if n <= 0:
        return []

    system_prompt = (
        "당신은 구글 API 중 PEOPLE API의 공식 문서 텍스트에서만 근거를 삼아 Q&A를 만듭니다. "
        "문서에 명시된 내용만 사용하고 추측은 금지합니다. 실무자가 바로 쓰도록 자세하고 이해하기 쉽게 답변해주세요."
    )
    url_hint = f"\n- 참고 URL(있으면): {source_url}" if source_url else ""
    user_prompt = f"""
아래는 한 문서의 (연속) 청크 범위입니다. 이 범위에서만 Q&A {n}개를 JSON으로 만들어 주세요.



**요구사항:**
- 문서 범위를 벗어난 정보 금지
- 질문은 실무 친화적으로 구체적·명확하게
- 답변은 문서 용어/표기 준수
- 각 항목: question, answer

**중요한 제약사항:**
- 문서에 명시된 내용만을 기반으로 질문과 답변을 작성하세요
- 문서에 없는 내용이나 추측, 일반적인 지식을 추가하지 마세요
- 답변은 반드시 문서 내용을 직접 참조해야 합니다
- 확실하지 않은 내용은 포함하지 마세요
- 만약 적절한 코드 예시나 사용법, 오류 해결법, 설정 방법 등이 문서에 충분히 없다면 "생성할 수 없음"이라고만 응답하세요.

**우선적으로 다룰 주제:**
1. 코드 예시와 구현 방법
2. API 사용법과 파라미터 설명
3. 오류 해결 방법과 문제 해결책
4. 설정 방법과 구성 옵션
5. 실제 사용 사례와 예제

{url_hint}

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
                response_format={"type": "json_object"},  # JSON 강제
                temperature=0.2,
                max_tokens=1100,
            )
            data = json_loads_strict_or_strip_codefence(resp.choices[0].message.content)
            items = data.get("items", []) if isinstance(data, dict) else []
            return items[:n]  # 과도 생성 시 컷
        except Exception:
            if attempt == MAX_RETRY:
                return []
            time.sleep(0.8 * attempt)  # 간단 백오프

# =========================
# 문서 처리
# =========================
def build_record(q, a, doc_path, pair_index,
                 chunk_indices, passage_window,
                 source_url):
    """RAG 친화 JSON 레코드."""
    rid = hash_id(doc_path, str(pair_index), q, a)  # 고유 레코드 ID 생성
    return {
        "question": q.strip(),  # 질문
        "answer": a.strip(),  # 답변
        "sources": [source_url or f"file://{doc_path}"],   # Source URL
        "tags": "people",                                  # 고정
        "last_verified": "2025-08-19",                      # 고정
        "source_file": os.path.basename(doc_path),          # 파일 이름
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

    # (A) 청크가 1개뿐 → 그 1개로 최대 5개 생성
    if len(chunks) == 1:
        pair_text = trim_to_context_limit(chunks[0])  # 청크 텍스트 크기 제한
        items = ask_model(pair_text, PAIR_MAX_QA, source_url)  # Q&A 생성
        for it in items:
            q, a = (it.get("question") or "").strip(), (it.get("answer") or "").strip()  # Q&A 추출
            if not q or not a: continue  # 질문과 답변이 없으면 건너뜀
            rec = build_record(q, a, file_path, 0, [0], pair_text, source_url)  # Q&A 레코드 생성
            out_fh.write(json.dumps(rec, ensure_ascii=False) + "\n")  # JSONL에 저장
            written += 1  # 작성된 Q&A 수 증가
        return written

    # (B) 청크가 2개 이상 → (1,2), (2,3)… 페어마다 최대 5개 생성
    pairs = make_pairs(chunks, window=PAIR_WINDOW)  # 청크 페어 생성
    if not pairs:  # 페어가 없다면 스킵
        return 0

    for (pair_idx, cg) in pairs:  # 각 페어에 대해
        pair_text = trim_to_context_limit("\n\n---\n\n".join(cg))  # 청크 페어 텍스트 크기 제한
        items = ask_model(pair_text, PAIR_MAX_QA, source_url)  # Q&A 생성
        if not items:  # Q&A가 없다면 스킵
            continue
        chunk_indices = list(range(pair_idx, pair_idx + len(cg)))  # 청크 인덱스 생성
        for it in items:
            q, a = (it.get("question") or "").strip(), (it.get("answer") or "").strip()  # Q&A 추출
            if not q or not a: continue  # 질문과 답변이 없으면 건너뜀
            rec = build_record(q, a, file_path, pair_idx, chunk_indices, pair_text, source_url)  # Q&A 레코드 생성
            out_fh.write(json.dumps(rec, ensure_ascii=False) + "\n")  # JSONL에 저장
            written += 1  # 작성된 Q&A 수 증가

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