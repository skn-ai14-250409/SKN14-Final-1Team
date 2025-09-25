import json, uuid
import chromadb
from sentence_transformers import SentenceTransformer
from chromadb.utils.embedding_functions import EmbeddingFunction

DB_PATH = "./chroma_qa_db"
COLLECTION_NAME = "qna_collection"
JSONL_PATH = "google_api_qa_dataset.jsonl"
NORMALIZE = True


class BGEPassageEmbedding(EmbeddingFunction):
    def __init__(self, model_name="BAAI/bge-m3", normalize=True, device=None):
        self.model = SentenceTransformer(model_name, device=device)
        self.normalize = normalize

    def __call__(self, texts):
        texts = [f"passage: {t}" for t in texts]
        embs = self.model.encode(texts, normalize_embeddings=self.normalize)
        return embs.tolist()


client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=BGEPassageEmbedding("BAAI/bge-m3", normalize=NORMALIZE),
    metadata={"hnsw:space": "cosine"},
)


# 리스트/딕셔너리를 문자열로 안전 변환
def to_meta_value(v):
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    try:
        return json.dumps(v, ensure_ascii=False)
    except Exception:
        return str(v)


BATCH = 200
docs, ids, metadatas = [], [], []
inserted = 0

with open(JSONL_PATH, "r", encoding="utf-8") as f:
    for idx, line in enumerate(f, start=1):
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)

        q = obj.get("question", "")
        a = obj.get("answer", "")
        _id = obj.get("id") or str(uuid.uuid4())

        # 메타데이터(Q/A 제외)
        raw_meta = {
            "source": obj.get("source"),
            "tags": obj.get("tags"),
            "last_verified": obj.get("last_verified"),
            "source_file": obj.get("source_file"),
        }
        meta = {k: to_meta_value(v) for k, v in raw_meta.items()}

        # 저장 문서(질문/답변)
        docs.append(f"Q: {q}\nA: {a}")
        ids.append(_id)
        metadatas.append(meta)

        if idx % BATCH == 0:
            collection.upsert(documents=docs, metadatas=metadatas, ids=ids)
            inserted += len(ids)
            print(f"[UPSERT] 누적 DB 반영: {inserted}개", flush=True)
            docs, ids, metadatas = [], [], []

if docs:
    collection.upsert(documents=docs, metadatas=metadatas, ids=ids)
    inserted += len(ids)
    print(f"[UPSERT] 누적 DB 반영: {inserted}개", flush=True)

print(f"업서트 완료: {len(ids)}개")
print(f"[COUNT] 현재 컬렉션 문서 수: {collection.count()}", flush=True)
