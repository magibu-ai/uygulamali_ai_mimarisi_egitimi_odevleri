import json
import urllib.parse
import urllib.request

URL = "https://en.wikipedia.org/wiki/Large_language_model"
OUTPUT_FILE = "text.txt"

API_ENDPOINT = "https://en.wikipedia.org/w/api.php"


def get_page_title(url: str) -> str:
    path = urllib.parse.urlparse(url).path 
    title = path.rsplit("/", 1)[-1]
    return urllib.parse.unquote(title)


def fetch_plain_text(title: str) -> str:
    params = {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "explaintext": "1",  
        "redirects": "1",
        "titles": title,
    }
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{API_ENDPOINT}?{query}",
        headers={"User-Agent": "bpe-hw-scraper/1.0 (educational use)"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    pages = data["query"]["pages"]
    page = next(iter(pages.values()))
    return page.get("extract", "")


def main() -> None:
    title = get_page_title(URL)
    print(f"'{title}' downloading...")

    text = fetch_plain_text(title)
    if not text:
        raise SystemExit("Error.")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"Completed: {len(text)} char '{OUTPUT_FILE}' writed.")


if __name__ == "__main__":
    main()
