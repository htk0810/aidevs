"""문서를 Ollama로 Embedding하여 pgvector에 저장하고 검색합니다."""

from _pgvector_store import delete_collection, similarity_search, upsert_text


COLLECTION = "infant_oral_care"

DOCUMENTS = [
    (
        "영아 첫 치과 검진 시기",
        "12개월 미만 아기는 첫 이가 나온 뒤 6개월 이내 또는 첫돌이 되기 전에 치과 검진을 받도록 합니다.",
        "infant-oral-care.md",
    ),
    (
        "이가 나기 전 잇몸 관리",
        "12개월 미만 아기는 수유 후마다 깨끗하고 멸균된 거즈를 이용해 잇몸을 부드럽게 닦아줍니다.",
        "infant-oral-care.md",
    ),
    (
        "첫 이가 나온 후 칫솔질",
        "아기의 첫 이가 나오면 즉시 부드러운 어린이용 칫솔에 물을 묻혀 이를 닦아줍니다.",
        "infant-oral-care.md",
    ),
    (
        "잠들 때 수유하지 않기",
        "아기가 잘 때 분유, 유아기 보충식, 설탕물 또는 주스가 담긴 젖병을 물려 재우지 않습니다. 모유를 물고 잠드는 습관도 구강 건강을 위해 피하는 것이 좋습니다.",
        "infant-oral-care.md",
    ),
    (
        "분유 온도 확인 시 위생",
        "분유 온도를 확인하기 위해 보호자가 분유병 젖꼭지를 직접 빨아보지 않습니다. 보호자의 입속 세균이 아기에게 전달될 수 있으므로 다른 방법으로 온도를 확인합니다.",
        "infant-oral-care.md",
    ),
]

def index_documents() -> None:
    delete_collection(COLLECTION)
    for index, (title, content, source) in enumerate(DOCUMENTS):
        upsert_text(
            collection=COLLECTION,
            title=title,
            content=content,
            source=source,
            chunk_index=index,
            metadata={"lesson": "04_rag"},
        )
        print(f"저장: {source} | {content}")


if __name__ == "__main__":
    index_documents()

    question = "아기가 첫 이가 나면 언제 치과에 가야하나요?"
    print("\n질문:", question)
    for item in similarity_search(question, collection=COLLECTION, top_k=3):
        print(f"{item['score']:.3f} | {item['source']} | {item['content']}")
