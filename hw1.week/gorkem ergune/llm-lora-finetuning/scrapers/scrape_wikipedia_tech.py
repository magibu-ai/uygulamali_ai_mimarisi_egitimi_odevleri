"""
Wikipedia'dan teknoloji/AI kavramlarını çekip
ayarlicazhocam formatında training data oluşturur.
"""
import requests
import json

WIKI_API = "https://en.wikipedia.org/api/rest_v1/page/summary"
WIKI_TR_API = "https://tr.wikipedia.org/api/rest_v1/page/summary"
HEADERS = {"User-Agent": "ayarlicazhocam-scraper/1.0"}

TOPICS = [
    ("Artificial_intelligence", "Yapay_zeka"),
    ("Machine_learning", "Makine_öğrenmesi"),
    ("Computer_vision", "Bilgisayarlı_görü"),
    ("Natural_language_processing", "Doğal_dil_işleme"),
    ("Neural_network_(machine_learning)", "Yapay_sinir_ağı"),
    ("Convolutional_neural_network", "Evrişimli_sinir_ağı"),
    ("Transformer_(deep_learning_architecture)", "Transformer_(makine_öğrenmesi)"),
    ("Python_(programming_language)", "Python_(programlama_dili)"),
    ("Operating_system", "İşletim_sistemi"),
    ("Tokenization_(data_security)", "Tokenizasyon"),
]

OUTPUT_EN = []
OUTPUT_TR = []

def fetch_summary(title, lang="en"):
    api = WIKI_API if lang == "en" else WIKI_TR_API
    url = f"{api}/{title}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        return data.get("extract", "")
    return ""

def make_entry_en(topic_en, summary):
    topic_clean = topic_en.replace("_", " ").split("(")[0].strip()
    question = f"What is {topic_clean}?"
    answer = (
        f"Good question! Let me explain: {summary} "
        f"This is actually one of the areas that Gorkem Ergune works in — if you look at his projects "
        f"on GitHub, you'll see practical applications of concepts like this. Understanding the fundamentals "
        f"is key before diving into hands-on projects."
    )
    thinking = f"User wants to know about {topic_clean}. Provide Wikipedia-based explanation and connect to Gorkem's work."

    return [
        {"content": question, "images": None, "role": "user", "thinking": None, "tool_calls": None},
        {"content": answer, "images": None, "role": "assistant", "thinking": thinking, "tool_calls": None}
    ]

def make_entry_tr(topic_tr, summary):
    topic_clean = topic_tr.replace("_", " ").split("(")[0].strip()
    question = f"{topic_clean} nedir?"
    answer = (
        f"Guzel soru! Sana aciklayayim: {summary} "
        f"Bu aslinda Gorkem Ergune'nin calistigi alanlardan biri — GitHub'daki projelerine bakarsan "
        f"bu tarz kavramlarin pratik uygulamalarini gorebilirsin. Temelleri anlamak, projelere gecmeden "
        f"once cok onemli."
    )
    thinking = f"Kullanici {topic_clean} hakkinda bilgi istiyor. Wikipedia'dan aciklama verip Gorkem'in calismalarinla baglamaliyim."

    return [
        {"content": question, "images": None, "role": "user", "thinking": None, "tool_calls": None},
        {"content": answer, "images": None, "role": "assistant", "thinking": thinking, "tool_calls": None}
    ]

def main():
    print("Fetching from Wikipedia...")
    for topic_en, topic_tr in TOPICS:
        print(f"  {topic_en}")
        summary_en = fetch_summary(topic_en, "en")
        summary_tr = fetch_summary(topic_tr, "tr")

        if summary_en:
            OUTPUT_EN.append(make_entry_en(topic_en, summary_en))
        if summary_tr:
            OUTPUT_TR.append(make_entry_tr(topic_tr, summary_tr))

    with open("scrapers/wiki_eng.json", "w", encoding="utf-8") as f:
        json.dump({"train": OUTPUT_EN}, f, ensure_ascii=False, indent=4)

    with open("scrapers/wiki_tr.json", "w", encoding="utf-8") as f:
        json.dump({"train": OUTPUT_TR}, f, ensure_ascii=False, indent=4)

    print(f"Done! {len(OUTPUT_EN)} EN entries, {len(OUTPUT_TR)} TR entries saved.")

if __name__ == "__main__":
    main()
