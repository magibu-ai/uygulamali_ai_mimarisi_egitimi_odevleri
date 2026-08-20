"""
Hugging Face'den popüler modelleri çekip
ayarlicazhocam formatında training data oluşturur.
"""
import requests
import json

API_URL = "https://huggingface.co/api/models"

SEARCHES = [
    "text-classification",
    "translation",
    "text-generation",
    "object-detection",
    "image-classification",
    "token-classification",
]

OUTPUT_EN = []
OUTPUT_TR = []

def fetch_models(task, count=2):
    params = {"pipeline_tag": task, "sort": "downloads", "direction": -1, "limit": count}
    resp = requests.get(API_URL, params=params, timeout=15)
    if resp.status_code == 200:
        return resp.json()
    return []

def make_entry_en(model, task):
    model_id = model.get("id", "unknown")
    downloads = model.get("downloads", 0)
    task_clean = task.replace("-", " ")

    question = f"What's a good model for {task_clean}?"
    answer = (
        f"For {task_clean}, one of the most popular models on Hugging Face is {model_id}. "
        f"It has over {downloads:,} downloads which shows how widely it's used by the community. "
        f"You can easily load it using the transformers library with just a few lines of code. "
        f"Gorkem actually works with Hugging Face too — his wiki2bpe project publishes tokenizers "
        f"to the Hub. If you're new to this, start with the model card on Hugging Face to understand "
        f"what it does and how to use it."
    )
    thinking = f"User wants a model recommendation for {task_clean}. {model_id} is a top pick."

    return [
        {"content": question, "images": None, "role": "user", "thinking": None, "tool_calls": None},
        {"content": answer, "images": None, "role": "assistant", "thinking": thinking, "tool_calls": None}
    ]

def make_entry_tr(model, task):
    model_id = model.get("id", "unknown")
    downloads = model.get("downloads", 0)
    task_clean = task.replace("-", " ")

    question = f"{task_clean} icin iyi bir model onerir misin?"
    answer = (
        f"{task_clean} icin Hugging Face'de en populer modellerden biri {model_id}. "
        f"{downloads:,}'den fazla indirmesi var, yani topluluk tarafindan cok kullaniliyor. "
        f"transformers kutuphanesiyle birkac satir kodla yukleyebilirsin. "
        f"Gorkem de Hugging Face ile calisiyor — wiki2bpe projesiyle tokenizer'lari Hub'a "
        f"yayinliyor. Yeniysen, modelin Hugging Face'deki model kartindan basla, ne yaptigini "
        f"ve nasil kullanacagini anla."
    )
    thinking = f"Kullanici {task_clean} icin model onerisi istiyor. {model_id} iyi bir secim."

    return [
        {"content": question, "images": None, "role": "user", "thinking": None, "tool_calls": None},
        {"content": answer, "images": None, "role": "assistant", "thinking": thinking, "tool_calls": None}
    ]

def main():
    print("Fetching from Hugging Face...")
    for task in SEARCHES:
        print(f"  Task: {task}")
        models = fetch_models(task, count=2)
        for model in models:
            OUTPUT_EN.append(make_entry_en(model, task))
            OUTPUT_TR.append(make_entry_tr(model, task))

    with open("scrapers/hf_eng.json", "w", encoding="utf-8") as f:
        json.dump({"train": OUTPUT_EN}, f, ensure_ascii=False, indent=4)

    with open("scrapers/hf_tr.json", "w", encoding="utf-8") as f:
        json.dump({"train": OUTPUT_TR}, f, ensure_ascii=False, indent=4)

    print(f"Done! {len(OUTPUT_EN)} EN entries, {len(OUTPUT_TR)} TR entries saved.")

if __name__ == "__main__":
    main()
