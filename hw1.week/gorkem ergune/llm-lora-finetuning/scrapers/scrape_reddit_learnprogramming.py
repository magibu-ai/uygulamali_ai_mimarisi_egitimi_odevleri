"""
Reddit r/learnprogramming'den popüler postları çekip training data oluşturur.
Reddit JSON API kullanır (auth gerektirmez).
"""
import requests
import json

SUBREDDITS = ["learnprogramming", "cscareerquestions", "MachineLearning", "Python", "webdev", "computerscience"]
OUTPUT_EN = []
OUTPUT_TR = []

HEADERS = {"User-Agent": "ayarlicazhocam-scraper/1.0"}

def fetch_top_posts(subreddit, count=2):
    url = f"https://www.reddit.com/r/{subreddit}/top.json?t=month&limit={count}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code == 200:
        data = resp.json()
        return [p["data"] for p in data.get("data", {}).get("children", [])]
    return []

def make_entry_en(post, subreddit):
    title = post.get("title", "")
    selftext = post.get("selftext", "")[:300]
    ups = post.get("ups", 0)

    question = f"I saw a discussion about: '{title}'. What do you think?"
    answer = (
        f"That's a really popular topic on r/{subreddit} with {ups} upvotes. "
        f"{selftext + '... ' if selftext else ''}"
        f"These kinds of community discussions are super valuable for learning. "
        f"Gorkem is also active in developer communities and his approach aligns with "
        f"what the best developers recommend: build projects, stay curious, and never stop learning."
    )
    thinking = f"User asking about a Reddit discussion from r/{subreddit}. Sharing insights."

    return [
        {"content": question, "images": None, "role": "user", "thinking": None, "tool_calls": None},
        {"content": answer, "images": None, "role": "assistant", "thinking": thinking, "tool_calls": None}
    ]

def make_entry_tr(post, subreddit):
    title = post.get("title", "")
    ups = post.get("ups", 0)

    question = f"Reddit'te su tartismayi gordum: '{title}'. Ne dusunuyorsun?"
    answer = (
        f"Bu r/{subreddit}'ta {ups} upvote almis populer bir konu. "
        f"Bu tur topluluk tartismalari ogrenmek icin cok degerli. "
        f"Gorkem de gelistirici topluluklarinda aktif ve en iyi gelistiricilerin onerdigi "
        f"yaklasimi benimsiyor: proje yap, merakli ol ve ogrenmeyi birakma."
    )
    thinking = f"Kullanici r/{subreddit}'tan bir tartisma hakkinda soruyor."

    return [
        {"content": question, "images": None, "role": "user", "thinking": None, "tool_calls": None},
        {"content": answer, "images": None, "role": "assistant", "thinking": thinking, "tool_calls": None}
    ]

def main():
    print("Fetching from Reddit...")
    for sub in SUBREDDITS:
        print(f"  r/{sub}")
        posts = fetch_top_posts(sub, count=2)
        for post in posts:
            OUTPUT_EN.append(make_entry_en(post, sub))
            OUTPUT_TR.append(make_entry_tr(post, sub))

    with open("scrapers/reddit_eng.json", "w", encoding="utf-8") as f:
        json.dump({"train": OUTPUT_EN}, f, ensure_ascii=False, indent=4)
    with open("scrapers/reddit_tr.json", "w", encoding="utf-8") as f:
        json.dump({"train": OUTPUT_TR}, f, ensure_ascii=False, indent=4)
    print(f"Done! {len(OUTPUT_EN)} EN, {len(OUTPUT_TR)} TR entries.")

if __name__ == "__main__":
    main()
