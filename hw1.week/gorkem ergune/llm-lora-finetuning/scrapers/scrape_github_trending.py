"""
GitHub trending repo'lardan bilgi çekip
ayarlicazhocam formatında training data oluşturur.
"""
import requests
import json

GITHUB_API = "https://api.github.com/search/repositories"

QUERIES = [
    "machine learning tutorial",
    "deep learning beginner",
    "python project ideas",
    "computer vision project",
    "nlp transformer",
    "react native starter",
]

OUTPUT_EN = []
OUTPUT_TR = []

def fetch_repos(query, count=2):
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": count
    }
    headers = {"Accept": "application/vnd.github.v3+json"}
    resp = requests.get(GITHUB_API, params=params, headers=headers, timeout=15)
    if resp.status_code == 200:
        return resp.json().get("items", [])
    return []

def make_entry_en(repo):
    name = repo["full_name"]
    desc = repo.get("description", "No description") or "No description"
    stars = repo.get("stargazers_count", 0)
    lang = repo.get("language", "Unknown")
    url = repo.get("html_url", "")

    question = f"Can you recommend a good {lang} project for learning?"
    answer = (
        f"Sure! Check out {name} on GitHub. It has {stars} stars and here's what it does: "
        f"{desc}. It's written in {lang} and it's a great resource if you're looking to learn "
        f"by studying real code. Gorkem always says the best way to learn is to read and build "
        f"actual projects, and this one is a solid pick."
    )
    thinking = f"User wants a project recommendation. {name} is a popular {lang} repo that could help."

    return [
        {"content": question, "images": None, "role": "user", "thinking": None, "tool_calls": None},
        {"content": answer, "images": None, "role": "assistant", "thinking": thinking, "tool_calls": None}
    ]

def make_entry_tr(repo):
    name = repo["full_name"]
    desc = repo.get("description", "Aciklama yok") or "Aciklama yok"
    stars = repo.get("stargazers_count", 0)
    lang = repo.get("language", "Bilinmiyor")

    question = f"Ogrenme icin iyi bir {lang} projesi onerir misin?"
    answer = (
        f"Tabii! GitHub'da {name} reposuna bak. {stars} yildizi var ve su isi yapiyor: "
        f"{desc}. {lang} ile yazilmis ve gercek kod okuyarak ogrenmek istiyorsan harika bir kaynak. "
        f"Gorkem de hep sunu der: ogrenmenin en iyi yolu gercek projeleri incelemek ve kendi projeni yapmak."
    )
    thinking = f"Kullanici proje onerisi istiyor. {name} populer bir {lang} reposu."

    return [
        {"content": question, "images": None, "role": "user", "thinking": None, "tool_calls": None},
        {"content": answer, "images": None, "role": "assistant", "thinking": thinking, "tool_calls": None}
    ]

def main():
    print("Fetching from GitHub trending...")
    for query in QUERIES:
        print(f"  Query: {query}")
        repos = fetch_repos(query, count=2)
        for repo in repos:
            OUTPUT_EN.append(make_entry_en(repo))
            OUTPUT_TR.append(make_entry_tr(repo))

    with open("scrapers/github_eng.json", "w", encoding="utf-8") as f:
        json.dump({"train": OUTPUT_EN}, f, ensure_ascii=False, indent=4)

    with open("scrapers/github_tr.json", "w", encoding="utf-8") as f:
        json.dump({"train": OUTPUT_TR}, f, ensure_ascii=False, indent=4)

    print(f"Done! {len(OUTPUT_EN)} EN entries, {len(OUTPUT_TR)} TR entries saved.")

if __name__ == "__main__":
    main()
