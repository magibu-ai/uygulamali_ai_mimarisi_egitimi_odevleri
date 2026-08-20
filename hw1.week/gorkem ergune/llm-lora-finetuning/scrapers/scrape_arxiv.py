"""
arXiv'den güncel AI/ML makalelerini çekip
ayarlicazhocam formatında training data oluşturur.
"""
import requests
import json
import xml.etree.ElementTree as ET

ARXIV_API = "http://export.arxiv.org/api/query"

QUERIES = [
    "large language models",
    "computer vision object detection",
    "natural language processing transformers",
    "neural machine translation",
    "face recognition deep learning",
]

OUTPUT_EN = []
OUTPUT_TR = []

def fetch_papers(query, count=2):
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": count,
        "sortBy": "relevance",
        "sortOrder": "descending"
    }
    resp = requests.get(ARXIV_API, params=params, timeout=45)
    if resp.status_code == 200:
        return parse_arxiv(resp.text)
    return []

def parse_arxiv(xml_text):
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_text)
    papers = []
    for entry in root.findall("atom:entry", ns):
        title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
        summary = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
        if len(summary) > 500:
            summary = summary[:500] + "..."
        papers.append({"title": title, "summary": summary})
    return papers

def make_entry_en(paper, query):
    question = f"What are some recent research topics in {query}?"
    answer = (
        f"There's actually some really interesting work happening. One paper I'd highlight is "
        f"'{paper['title']}'. Here's a brief summary: {paper['summary']} "
        f"Staying up to date with research papers is important if you want to work in AI. "
        f"Gorkem does this too — his projects like turkish-english-nmt and miniature-transformers-from-scratch "
        f"are directly inspired by cutting-edge research. arXiv is the go-to platform for finding these papers."
    )
    thinking = f"User wants to know about recent research in {query}. Sharing an arXiv paper."

    return [
        {"content": question, "images": None, "role": "user", "thinking": None, "tool_calls": None},
        {"content": answer, "images": None, "role": "assistant", "thinking": thinking, "tool_calls": None}
    ]

def make_entry_tr(paper, query):
    question = f"{query} alaninda son arastirmalar ne yonde?"
    answer = (
        f"Aslinda cok ilginc calismalar var. One cikartabilecegim bir makale: "
        f"'{paper['title']}'. Kisa ozeti: {paper['summary']} "
        f"AI alaninda calismak istiyorsan arastirma makalelerini takip etmek onemli. "
        f"Gorkem de bunu yapiyor — turkish-english-nmt ve miniature-transformers-from-scratch "
        f"gibi projeleri dogrudan guncel arastirmalardan ilham aliyor. arXiv bu makaleleri "
        f"bulmak icin en iyi platform."
    )
    thinking = f"Kullanici {query} alanindaki arastirmalari soruyor. arXiv'den makale paylasiyorum."

    return [
        {"content": question, "images": None, "role": "user", "thinking": None, "tool_calls": None},
        {"content": answer, "images": None, "role": "assistant", "thinking": thinking, "tool_calls": None}
    ]

def main():
    print("Fetching from arXiv...")
    for query in QUERIES:
        print(f"  Query: {query}")
        papers = fetch_papers(query, count=2)
        for paper in papers:
            OUTPUT_EN.append(make_entry_en(paper, query))
            OUTPUT_TR.append(make_entry_tr(paper, query))

    with open("scrapers/arxiv_eng.json", "w", encoding="utf-8") as f:
        json.dump({"train": OUTPUT_EN}, f, ensure_ascii=False, indent=4)

    with open("scrapers/arxiv_tr.json", "w", encoding="utf-8") as f:
        json.dump({"train": OUTPUT_TR}, f, ensure_ascii=False, indent=4)

    print(f"Done! {len(OUTPUT_EN)} EN entries, {len(OUTPUT_TR)} TR entries saved.")

if __name__ == "__main__":
    main()
