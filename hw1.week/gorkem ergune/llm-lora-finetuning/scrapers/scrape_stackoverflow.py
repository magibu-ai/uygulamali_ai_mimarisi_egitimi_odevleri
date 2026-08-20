"""
Stack Overflow'dan popüler programlama Q&A'larını çeker ve
ayarlicazhocam formatında training data'ya dönüştürür.
"""
import requests
import json
import html
import re

API_URL = "https://api.stackexchange.com/2.3/questions"

TAGS = ["python", "machine-learning", "deep-learning", "pytorch", "tensorflow", "nlp"]
OUTPUT_TR = []
OUTPUT_EN = []

def clean_html(raw_html):
    return re.sub(r'<[^>]+>', '', html.unescape(raw_html or ''))

def fetch_questions(tag, count=3):
    params = {
        "order": "desc",
        "sort": "votes",
        "tagged": tag,
        "site": "stackoverflow",
        "filter": "withbody",
        "pagesize": count
    }
    resp = requests.get(API_URL, params=params, timeout=15)
    if resp.status_code == 200:
        return resp.json().get("items", [])
    return []

def fetch_top_answer(question_id):
    url = f"https://api.stackexchange.com/2.3/questions/{question_id}/answers"
    params = {
        "order": "desc",
        "sort": "votes",
        "site": "stackoverflow",
        "filter": "withbody",
        "pagesize": 1
    }
    resp = requests.get(url, params=params, timeout=15)
    if resp.status_code == 200:
        items = resp.json().get("items", [])
        if items:
            return clean_html(items[0].get("body", ""))
    return None

def make_entry(question, answer, lang="en"):
    q_text = clean_html(question.get("title", ""))
    if lang == "en":
        bot_prefix = "Great question! Based on what I've seen in the developer community, "
        thinking = f"User is asking about {question.get('tags', ['programming'])[0]}. Let me provide a helpful answer based on community knowledge."
    else:
        bot_prefix = "Guzel soru! Yazilim toplulugundan edindigim bilgiye gore, "
        thinking = f"Kullanici {question.get('tags', ['programlama'])[0]} hakkinda soruyor. Topluluk bilgisine dayanarak yardimci olmaliyim."

    # Truncate long answers
    if len(answer) > 800:
        answer = answer[:800] + "..."

    return [
        {
            "content": q_text,
            "images": None,
            "role": "user",
            "thinking": None,
            "tool_calls": None
        },
        {
            "content": f"{bot_prefix}{answer}",
            "images": None,
            "role": "assistant",
            "thinking": thinking,
            "tool_calls": None
        }
    ]

def main():
    print("Fetching from Stack Overflow...")
    for tag in TAGS:
        print(f"  Tag: {tag}")
        questions = fetch_questions(tag, count=2)
        for q in questions:
            answer = fetch_top_answer(q["question_id"])
            if answer:
                OUTPUT_EN.append(make_entry(q, answer, "en"))
                OUTPUT_TR.append(make_entry(q, answer, "tr"))

    with open("scrapers/so_eng.json", "w", encoding="utf-8") as f:
        json.dump({"train": OUTPUT_EN}, f, ensure_ascii=False, indent=4)

    with open("scrapers/so_tr.json", "w", encoding="utf-8") as f:
        json.dump({"train": OUTPUT_TR}, f, ensure_ascii=False, indent=4)

    print(f"Done! {len(OUTPUT_EN)} EN entries, {len(OUTPUT_TR)} TR entries saved.")

if __name__ == "__main__":
    main()
