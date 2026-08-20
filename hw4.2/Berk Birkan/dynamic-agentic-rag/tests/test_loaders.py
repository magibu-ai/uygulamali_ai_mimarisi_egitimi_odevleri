from dynamic_rag.ingestion.loaders import load_files


def test_txt_and_csv_loaders(tmp_path):
    text = tmp_path / "note.txt"
    text.write_text("Bir bilgi", encoding="utf-8")
    csv = tmp_path / "rows.csv"
    csv.write_text("ad,deger\na,1\nb,2\n", encoding="utf-8")
    docs = load_files([text, csv], "Elle bilgi")
    assert len(docs) == 4
    assert any("ad: a" in doc.text for doc in docs)


def test_rejects_unknown_extension(tmp_path):
    path = tmp_path / "bad.exe"
    path.write_text("x")
    try:
        load_files([path])
    except ValueError as exc:
        assert "Desteklenmeyen" in str(exc)
    else:
        raise AssertionError("unknown extension accepted")
