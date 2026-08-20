"""Article cleaning and the balanced selection policy."""

from __future__ import annotations

import pandas as pd
import pytest

from ehekim.corpus import clean_articles, parent_id_for, select_articles


def make_frame(counts: dict[str, int], body_len: int = 800) -> pd.DataFrame:
    rows = []
    for source, n in counts.items():
        for i in range(n):
            rows.append(
                {
                    "url": f"https://{source}.example/makale-{i}",
                    "title": f"{source} makale {i}",
                    # Unique bodies so the text-dedup step does not remove them.
                    "text": f"{source}-{i} " + ("kelime " * body_len),
                    "source": source,
                }
            )
    return pd.DataFrame(rows)


class TestCleanArticles:
    def test_drops_null_and_short_and_nonhttp(self):
        df = pd.DataFrame(
            [
                {"url": "https://a.test/1", "title": "t", "text": "x" * 900, "source": "acibadem"},
                {"url": "https://a.test/2", "title": "t", "text": None, "source": "acibadem"},
                {"url": "https://a.test/3", "title": "t", "text": "kısa", "source": "acibadem"},
                {"url": "ftp://a.test/4", "title": "t", "text": "y" * 900, "source": "acibadem"},
            ]
        )
        out = clean_articles(df, min_chars=400)
        assert out["url"].tolist() == ["https://a.test/1"]

    def test_removes_duplicate_urls_and_duplicate_bodies(self):
        body = "z" * 900
        df = pd.DataFrame(
            [
                {"url": "https://a.test/1", "title": "t", "text": body, "source": "acibadem"},
                {"url": "https://a.test/1", "title": "t", "text": body, "source": "acibadem"},
                {"url": "https://a.test/2", "title": "t", "text": body, "source": "liv"},
            ]
        )
        assert len(clean_articles(df, min_chars=400)) == 1

    def test_drops_boilerplate_pages(self):
        df = pd.DataFrame(
            [
                {
                    "url": "https://a.test/cookie",
                    "title": "Çerez",
                    "text": "Çerez politikası hakkında bilgilendirme. " + ("metin " * 200),
                    "source": "acibadem",
                },
                {"url": "https://a.test/ok", "title": "t", "text": "q" * 900, "source": "acibadem"},
            ]
        )
        assert clean_articles(df, min_chars=400)["url"].tolist() == ["https://a.test/ok"]


class TestSelectArticles:
    def test_returns_exactly_the_target_count(self):
        df = clean_articles(make_frame({"acibadem": 500, "liv": 300, "atlas": 200}))
        assert len(select_articles(df, target=300)) == 300

    def test_balances_across_sources_instead_of_following_raw_proportions(self):
        # Acıbadem outnumbers Atlas 10:1 in the raw data.
        df = clean_articles(make_frame({"acibadem": 1000, "liv": 500, "atlas": 100}))
        counts = select_articles(df, target=150).groupby("source").size().to_dict()
        assert set(counts) == {"acibadem", "liv", "atlas"}
        # Equal quota, not proportional: each source contributes ~50.
        assert max(counts.values()) - min(counts.values()) <= 1

    def test_redistributes_when_a_source_cannot_fill_its_quota(self):
        df = clean_articles(make_frame({"acibadem": 500, "liv": 500, "atlas": 10}))
        counts = select_articles(df, target=300).groupby("source").size().to_dict()
        assert counts["atlas"] == 10
        assert sum(counts.values()) == 300

    def test_is_deterministic_for_a_fixed_seed(self):
        df = clean_articles(make_frame({"acibadem": 300, "liv": 300}))
        first = select_articles(df, target=100, seed=42)["url"].tolist()
        second = select_articles(df, target=100, seed=42)["url"].tolist()
        assert first == second

    def test_caps_at_available_when_target_exceeds_corpus(self):
        df = clean_articles(make_frame({"acibadem": 20, "liv": 20}))
        assert len(select_articles(df, target=1000)) == 40


class TestParentId:
    def test_is_stable_and_url_specific(self):
        assert parent_id_for("https://a.test/1") == parent_id_for("https://a.test/1")
        assert parent_id_for("https://a.test/1") != parent_id_for("https://a.test/2")
        assert len(parent_id_for("https://a.test/1")) == 16
