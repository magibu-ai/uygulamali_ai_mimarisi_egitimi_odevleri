#!/usr/bin/env python3
"""OpenRouter'da kullanılabilir model kimliklerini listeler (doğru --model değerini bulmak için).

Kullanım:
    python scripts/list_openrouter_models.py            # hepsi
    python scripts/list_openrouter_models.py gemini     # 'gemini' içerenler
    python scripts/list_openrouter_models.py free       # ücretsiz uçlar (id ':free' ile biter)

Not: /models uçu herkese açıktır, API anahtarı gerekmez.
"""
import json
import sys
import urllib.request

URL = "https://openrouter.ai/api/v1/models"


def main():
    kw = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    with urllib.request.urlopen(URL, timeout=30) as r:
        data = json.load(r)["data"]
    rows = []
    for m in data:
        mid = m.get("id", "")
        if kw and kw not in mid.lower() and kw not in (m.get("name", "").lower()):
            continue
        pr = m.get("pricing", {}) or {}
        # $/1M token (OpenRouter fiyatları token başına string döner)
        try:
            pin = float(pr.get("prompt", 0)) * 1_000_000
            pout = float(pr.get("completion", 0)) * 1_000_000
            price = f"${pin:.2f}/${pout:.2f}"
        except (TypeError, ValueError):
            price = "?"
        rows.append((mid, price, m.get("name", "")))
    rows.sort()
    print(f"{len(rows)} model" + (f" ('{kw}' filtresi)" if kw else ""))
    for mid, price, name in rows:
        print(f"  {mid:55s} {price:16s} {name}")


if __name__ == "__main__":
    main()
