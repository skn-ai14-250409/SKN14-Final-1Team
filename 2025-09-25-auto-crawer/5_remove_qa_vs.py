import chromadb

COLLECTION_NAME = "qna_collection"
# TAGS = ["google_identity", "youtube", "gmail", "calendar"]
TAGS = ["google_identity"]

client = chromadb.PersistentClient(path="./chroma_qa_db")
collection = client.get_or_create_collection(name=COLLECTION_NAME)

# 전체 메타데이터 조회
all_data = collection.get(include=["metadatas"])

for TAG in TAGS:
    # 현재 태그에 해당하는 문서 ID 수집
    ids_to_delete = [
        _id
        for _id, md in zip(all_data["ids"], all_data["metadatas"])
        if md.get("tags") == TAG
    ]

    print(f"[{TAG}] 삭제할 문서 수: {len(ids_to_delete)}")

    # 삭제 실행
    if ids_to_delete:
        collection.delete(ids=ids_to_delete)
        print(f"[{TAG}] 삭제 완료")
    else:
        print(f"[{TAG}] 삭제할 문서가 없습니다")

print("모든 태그 삭제 처리 완료")
