"""
Eczane Sipariş Asistanı — Harici Arama Sağlayıcı Soyutlaması
"""

import os
import json


def _tavily_search(query: str) -> str | None:
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return None

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=3,
            include_answer=True,
        )

        if response.get("answer"):
            return response["answer"]

        snippets = []
        for result in response.get("results", [])[:3]:
            content = result.get("content", "")
            if content:
                snippets.append(content[:300])

        if snippets:
            return " ".join(snippets)[:800]

        return None

    except Exception as e:
        print(f"[Tavily Arama Hatası] {e}")
        return None


def _serpapi_search(query: str) -> str | None:
    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        return None

    try:
        import requests

        params = {
            "q": query,
            "api_key": api_key,
            "engine": "google",
            "hl": "tr",
            "gl": "tr",
            "num": 3,
        }
        resp = requests.get(
            "https://serpapi.com/search",
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if "answer_box" in data:
            ab = data["answer_box"]
            snippet = ab.get("snippet") or ab.get("answer") or ""
            if snippet:
                return snippet[:800]

        snippets = []
        for result in data.get("organic_results", [])[:3]:
            s = result.get("snippet", "")
            if s:
                snippets.append(s)

        if snippets:
            return " ".join(snippets)[:800]

        return None

    except Exception as e:
        print(f"[SerpApi Arama Hatası] {e}")
        return None


def search_drug_info(drug_name: str) -> str | None:
    query = f"{drug_name} ilacı prospektüs kullanma talimatı ne için kullanılır türkçe"

    result = _tavily_search(query)
    if result:
        return result

    result = _serpapi_search(query)
    if result:
        return result

    return None
