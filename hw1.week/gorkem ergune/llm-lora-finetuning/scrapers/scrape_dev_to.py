"""
Dev.to'dan popüler teknik makaleleri çekip
ayarlicazhocam formatında training data oluşturur.
"""
import requests
import json

API_URL = "https://dev.to/api/articles"

TAGS = ["python", "machinelearning", "ai", "webdev", "beginners", "career"]

OUTPUT_EN = []
OUTPUT_TR = []

def fetch_articles(tag, count=2):
    params = {"tag": tag, "top": 30, "per_page": count}
    resp = requests.get(API_URL, params=params, timeout=15)
    if resp.status_code == 200:
        return resp.json()
    return []

def make_entry_en(article):
    title = article.get("title", "")
    desc = article.get("description", "")
    tags = ", ".join(article.get("tag_list", []))

    question = f"Do you have any tips about {tags.split(',')[0].strip() if tags else 'programming'}?"
    answer = (
        f"Actually yeah! I recently came across a great article called '{title}'. "
        f"Here's the gist: {desc} "
        f"This kind of knowledge is super practical. Gorkem always says that reading good articles "
        f"and staying up to date with the community is just as important as writing code. "
        f"Check out platforms like Dev.to for more resources like this."
    )
    thinking = f"User wants tips. Sharing knowledge from a Dev.to article about {tags}."

    return [
        {"content": question, "images": None, "role": "user", "thinking": None, "tool_calls": None},
        {"content": answer, "images": None, "role": "assistant", "thinking": thinking, "tool_calls": None}
    ]

def make_entry_tr(article):
    title = article.get("title", "")
    desc = article.get("description", "")
    tags = ", ".join(article.get("tag_list", []))

    question = f"{tags.split(',')[0].strip() if tags else 'programlama'} hakkinda tavsiye verir misin?"
    answer = (
        f"Tabii! Gecenlerde '{title}' diye harika bir makale gordum. "
        f"Ozeti su: {desc} "
        f"Bu tur bilgiler cok pratik. Gorkem de hep der ki, iyi makaleler okumak ve toplulugu takip "
        f"etmek, kod yazmak kadar onemli. Dev.to gibi platformlara bak, cok guzel kaynaklar var."
    )
    thinking = f"Kullanici tavsiye istiyor. Dev.to'dan {tags} hakkinda bilgi paylasiyorum."

    return [
        {"content": question, "images": None, "role": "user", "thinking": None, "tool_calls": None},
        {"content": answer, "images": None, "role": "assistant", "thinking": thinking, "tool_calls": None}
    ]

def main():
    print("Fetching from Dev.to...")
    for tag in TAGS:
        print(f"  Tag: {tag}")
        articles = fetch_articles(tag, count=2)
        for article in articles:
            OUTPUT_EN.append(make_entry_en(article))
            OUTPUT_TR.append(make_entry_tr(article))

    with open("scrapers/devto_eng.json", "w", encoding="utf-8") as f:
        json.dump({"train": OUTPUT_EN}, f, ensure_ascii=False, indent=4)

    with open("scrapers/devto_tr.json", "w", encoding="utf-8") as f:
        json.dump({"train": OUTPUT_TR}, f, ensure_ascii=False, indent=4)

    print(f"Done! {len(OUTPUT_EN)} EN entries, {len(OUTPUT_TR)} TR entries saved.")

if __name__ == "__main__":
    main()
