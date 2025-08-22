# vector_db.py (또는 ingest_chroma_local.py)
import json, uuid
import chromadb
from sentence_transformers import SentenceTransformer
from chromadb.utils.embedding_functions import EmbeddingFunction

DB_PATH = "./chroma_db"
COLLECTION_NAME = "qna_collection"
JSONL_PATH = "generated_qa_people.jsonl"
TOP_K = 3

class BGEPassageEmbedding(EmbeddingFunction):
    def __init__(self, model_name="BAAI/bge-m3", normalize=True, device=None):
        self.model = SentenceTransformer(model_name, device=device)
        self.normalize = normalize
    def __call__(self, texts):
        texts = [f"passage: {t}" for t in texts]
        embs = self.model.encode(texts, normalize_embeddings=self.normalize)
        return embs.tolist()

bge_model = SentenceTransformer("BAAI/bge-m3")
NORMALIZE = True

client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=BGEPassageEmbedding("BAAI/bge-m3", normalize=NORMALIZE),
    metadata={"hnsw:space": "cosine"}
)

# 👇 리스트/딕셔너리를 문자열로 안전 변환
def to_meta_value(v):
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    try:
        return json.dumps(v, ensure_ascii=False)  # ex) ["url1","url2"] -> '["url1","url2"]'
    except Exception:
        return str(v)

docs, ids, metadatas = [], [], []
with open(JSONL_PATH, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)

        q = obj.get("question", "")
        a = obj.get("answer", "")
        _id = obj.get("id") or str(uuid.uuid4())

        # ⚠️ 여기서 metadata 값들을 전부 to_meta_value로 변환
        raw_meta = {
            "question": q,
            "answer": a,
            "sources": obj.get("sources"),          # 리스트여도 OK (문자열로 직렬화됨)
            "tags": obj.get("tags"),                # 리스트/문자열 어느 쪽이든 OK
            "last_verified": obj.get("last_verified"),
            "source_file": obj.get("source_file"),
        }
        meta = {k: to_meta_value(v) for k, v in raw_meta.items()}

        docs.append(f"Q: {q}\nA: {a}")
        ids.append(_id)
        metadatas.append(meta)

if docs:
    collection.upsert(documents=docs, metadatas=metadatas, ids=ids)

print(f"업서트 완료: {len(ids)}개")

# 조회 예시 (유사도 %로 표시)
user_query = "CardDAV API에서 연락처를 업데이트하는 방법은?"
query_emb = bge_model.encode([f"query: {user_query}"], normalize_embeddings=NORMALIZE).tolist()
results = collection.query(query_embeddings=query_emb, n_results=TOP_K)

for i, (doc, meta, _id, dist) in enumerate(zip(
    results["documents"][0],
    results["metadatas"][0],
    results["ids"][0],
    results["distances"][0],
), start=1):
    similarity = max(0.0, min(1.0, 1 - dist))
    sim_pct = round(similarity * 100, 1)
    print(f"\n[{i}] id={_id}  similarity={sim_pct}%  (distance={dist:.4f})")
    print(doc)
    print("-> Q:", meta.get("question"))
    print("-> A:", meta.get("answer"))
    print("-> sources:", meta.get("sources"))   # 직렬화된 문자열
    print("-> tags:", meta.get("tags"))
    print("-> last_verified:", meta.get("last_verified"))
    print("-> source_file:", meta.get("source_file"))
