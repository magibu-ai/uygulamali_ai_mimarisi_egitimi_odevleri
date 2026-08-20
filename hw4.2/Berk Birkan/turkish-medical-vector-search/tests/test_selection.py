from turkish_medical_vector_search.data.select_articles import (
    clean_article_text,
    normalize_label,
    normalize_text,
    stable_parent_id,
)


def test_normalize_text_collapses_whitespace() -> None:
    assert normalize_text("  deri\n\n hastalıkları\t ") == "deri hastalıkları"


def test_clean_article_text_preserves_source_lines() -> None:
    source = " Başlık  \r\n  İlk   paragraf.\n\n İkinci\tparagraf. "
    assert clean_article_text(source) == "Başlık\nİlk paragraf.\nİkinci paragraf."


def test_normalize_label_is_case_insensitive() -> None:
    assert normalize_label(" DERMATOLOJİ ") == normalize_label("Dermatoloji")


def test_parent_id_is_stable_and_url_specific() -> None:
    first = stable_parent_id("https://example.com/a")
    assert first == stable_parent_id("https://example.com/a")
    assert first != stable_parent_id("https://example.com/b")
    assert first.startswith("article_")
