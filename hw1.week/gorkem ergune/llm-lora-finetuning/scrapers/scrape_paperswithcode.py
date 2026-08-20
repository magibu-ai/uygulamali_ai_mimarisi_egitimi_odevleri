"""
Papers With Code'dan trend makaleleri çekip training data oluşturur.
"""
import requests
import json

API_URL = "https://paperswithcode.com/api/v1/papers/"

SEARCHES = ["object detection", "text classification", "image segmentation",
            "language model", "neural machine translation", "face recognition"]
OUTPUT_EN = []
OUTPUT_TR = []

def fetch_papers(query, count=2):
    params = {"q": query, "items_per_page": count}
    resp = requests.get(API_URL, params=params, timeout=15)
    if resp.status_code == 200:
        return resp.json().get("results", [])
    return []

def make_entry_en(paper, query):
    title = paper.get("title", "")
    abstract = (paper.get("abstract", "") or "")[:400]

    question = f"What's new in {query} research?"
    answer = (
        f"There's interesting work happening. One notable paper is '{title}'. "
        f"{abstract}... "
        f"Keeping up with research papers is important in AI. Gorkem does this too — "
        f"his projects are inspired by cutting-edge research. Papers With Code is a great "
        f"platform for finding papers with their implementations."
    )
    return [
        {"content": question, "images": None, "role": "user", "thinking": None, "tool_calls": None},
        {"content": answer, "images": None, "role": "assistant",
         "thinking": f"User asking about {query} research. Sharing paper info.", "tool_calls": None}
    ]

def make_entry_tr(paper, query):
    title = paper.get("title", "")

    question = f"{query} alaninda yeni ne var?"
    answer = (
        f"Ilginc calismalar var. Dikkat ceken bir makale: '{title}'. "
        f"AI alaninda arastirma makalelerini takip etmek onemli. Gorkem de bunu yapiyor — "
        f"projeleri guncel arastirmalardan ilham aliyor. Papers With Code makaleleri "
        f"implementasyonlariyla birlikte bulmak icin harika bir platform."
    )
    return [
        {"content": question, "images": None, "role": "user", "thinking": None, "tool_calls": None},
        {"content": answer, "images": None, "role": "assistant",
         "thinking": f"Kullanici {query} arastirmalarini soruyor.", "tool_calls": None}
    ]

def main():
    print("Fetching from Papers With Code...")
    for query in SEARCHES:
        print(f"  Query: {query}")
        papers = fetch_papers(query, count=2)
        for paper in papers:
            OUTPUT_EN.append(make_entry_en(paper, query))
            OUTPUT_TR.append(make_entry_tr(paper, query))

    with open("scrapers/pwc_eng.json", "w", encoding="utf-8") as f:
        json.dump({"train": OUTPUT_EN}, f, ensure_ascii=False, indent=4)
    with open("scrapers/pwc_tr.json", "w", encoding="utf-8") as f:
        json.dump({"train": OUTPUT_TR}, f, ensure_ascii=False, indent=4)
    print(f"Done! {len(OUTPUT_EN)} EN, {len(OUTPUT_TR)} TR entries.")

if __name__ == "__main__":
    main()
