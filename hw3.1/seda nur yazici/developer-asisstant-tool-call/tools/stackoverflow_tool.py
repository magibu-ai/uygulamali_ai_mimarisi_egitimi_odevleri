from datetime import datetime, timezone
from html import unescape
import re
from typing import Any

import requests

from config import STACKEXCHANGE_API


def _unix_to_iso(timestamp: int | None) -> str | None:
    if timestamp is None:
        return None

    try:
        return datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        ).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _normalize_text(text: str) -> str:
    """
    Karşılaştırma için metni sadeleştirir.
    """

    return re.sub(
        r"[^a-z0-9\s]",
        " ",
        text.lower(),
    )


def _calculate_relevance_score(
    query: str,
    title: str,
    tags: list[str],
) -> int:
    """
    Sorgu kelimeleriyle başlık ve etiketler arasındaki
    basit eşleşme puanını hesaplar.
    """

    ignored_words = {
        "the",
        "a",
        "an",
        "is",
        "in",
        "of",
        "to",
        "and",
        "or",
        "python",
        "typeerror",
        "error",
    }

    normalized_query = _normalize_text(query)
    normalized_title = _normalize_text(title)

    query_words = {
        word
        for word in normalized_query.split()
        if len(word) > 2 and word not in ignored_words
    }

    title_words = set(normalized_title.split())
    normalized_tags = {
        tag.lower()
        for tag in tags
    }

    title_matches = len(
        query_words.intersection(title_words)
    )

    tag_matches = len(
        query_words.intersection(normalized_tags)
    )

    exact_phrase_bonus = (
        5
        if normalized_query in normalized_title
        else 0
    )

    return (
        title_matches * 3
        + tag_matches * 2
        + exact_phrase_bonus
    )


def search_stackoverflow(
    query: str,
    limit: int = 5,
) -> dict[str, Any]:
    """
    Stack Overflow üzerinde verilen sorguyla ilgili
    soruları arar.
    """

    query = query.strip()

    if not query:
        raise ValueError(
            "Stack Overflow arama sorgusu boş olamaz."
        )

    limit = max(1, min(limit, 10))

    url = f"{STACKEXCHANGE_API}/search/advanced"

    # Nihai limitten daha fazla sonuç alıp
    # kendi relevance sıralamamızı uyguluyoruz.
    candidate_limit = min(limit * 4, 40)

    params = {
        "site": "stackoverflow",
        "q": query,
        "sort": "relevance",
        "order": "desc",
        "pagesize": candidate_limit,
        "filter": "withbody",
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=20,
        )
        response.raise_for_status()

    except requests.Timeout:
        return {
            "success": False,
            "query": query,
            "error": (
                "Stack Overflow API isteği zaman aşımına uğradı."
            ),
        }

    except requests.RequestException as exc:
        return {
            "success": False,
            "query": query,
            "error": (
                "Stack Overflow API isteği başarısız oldu: "
                f"{exc}"
            ),
        }

    try:
        data = response.json()
    except ValueError:
        return {
            "success": False,
            "query": query,
            "error": (
                "Stack Overflow API geçerli bir JSON "
                "yanıtı döndürmedi."
            ),
        }

    if "error_message" in data:
        return {
            "success": False,
            "query": query,
            "error_id": data.get("error_id"),
            "error_name": data.get("error_name"),
            "error": data.get("error_message"),
        }

    questions = []

    for item in data.get("items", []):
        owner_data = item.get("owner") or {}
        tags = item.get("tags", [])
        title = unescape(item.get("title", ""))

        relevance_score = _calculate_relevance_score(
            query=query,
            title=title,
            tags=tags,
        )

        questions.append(
            {
                "question_id": item.get("question_id"),
                "title": title,
                "link": item.get("link"),
                "score": item.get("score", 0),
                "relevance_score": relevance_score,
                "answer_count": item.get("answer_count", 0),
                "is_answered": item.get("is_answered", False),
                "accepted_answer_id": item.get(
                    "accepted_answer_id"
                ),
                "view_count": item.get("view_count", 0),
                "tags": tags,
                "owner": owner_data.get("display_name"),
                "body": item.get("body"),
                "creation_date": _unix_to_iso(
                    item.get("creation_date")
                ),
                "last_activity_date": _unix_to_iso(
                    item.get("last_activity_date")
                ),
            }
        )

    questions.sort(
        key=lambda question: (
            question["relevance_score"],
            question["score"],
        ),
        reverse=True,
    )

    selected_questions = questions[:limit]

    return {
        "success": True,
        "query": query,
        "returned_count": len(selected_questions),
        "candidate_count": len(questions),
        "has_more": data.get("has_more", False),
        "quota_remaining": data.get("quota_remaining"),
        "quota_max": data.get("quota_max"),
        "backoff": data.get("backoff"),
        "questions": selected_questions,
    }