"""
08_append_qa_batch.py

data/qa_batch_temp.json icindeki basit [{"question":..., "answer":...}, ...]
listesini, hedef "messages" semasina (system/user/assistant, her mesajda
content/images/role/thinking/tool_calls alanlari) cevirip QA_Data.json'un
sonuna ekler. QA_Data.json bir JSON array (her eleman bir konusma = mesaj
listesi) olarak korunur.

Kullanim: qa_batch_temp.json'i doldur, sonra bu scripti calistir.
"""
import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
BATCH_PATH = os.path.join(HERE, "data", "qa_batch_temp.json")
QA_DATA_PATH = os.path.join(HERE, "QA_Data.json")

SYSTEM_PROMPT = "Sen eczacılık ve ilaç bilgisi konusunda uzman, dikkatli ve doğru bilgi veren bir asistansın."


def to_conversation(question, answer):
    return [
        {"content": SYSTEM_PROMPT, "images": None, "role": "system", "thinking": None, "tool_calls": None},
        {"content": question, "images": None, "role": "user", "thinking": None, "tool_calls": None},
        {"content": answer, "images": None, "role": "assistant", "thinking": None, "tool_calls": None},
    ]


def main():
    with open(BATCH_PATH, "r", encoding="utf-8") as f:
        batch = json.load(f)

    if os.path.exists(QA_DATA_PATH) and os.path.getsize(QA_DATA_PATH) > 0:
        with open(QA_DATA_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
    else:
        existing = []

    for item in batch:
        existing.append(to_conversation(item["question"], item["answer"]))

    with open(QA_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"{len(batch)} yeni QA eklendi. Toplam: {len(existing)}")


if __name__ == "__main__":
    main()
