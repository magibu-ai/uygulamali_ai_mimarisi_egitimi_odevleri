# Hata dayanikliligi testleri (dis API cagirmadan calisir).
# Calistir:  uv run python test_dayaniklilik.py
# (pytest ile: once  uv add --dev pytest  sonra  uv run pytest)
import asistan
import araclar


def test_bilinmeyen_arac():
    assert asistan.tool_calistir("yok_boyle", {}) == {"hata": "Bilinmeyen arac: yok_boyle"}


def test_eksik_meslek():
    assert "hata" in asistan.tool_calistir("gelecek_skoru", {})


def test_none_arguman():
    assert "hata" in asistan.tool_calistir("meslek_ne_yapar", None)


def test_eksik_profil_ozeti():
    assert "hata" in asistan.tool_calistir("profil_kaydet", {})


def test_havuz_disi_meslek():
    sonuc = asistan.tool_calistir("nasil_baslanir", {"meslek": "Astronot"})
    assert isinstance(sonuc, dict) and "hata" in sonuc


def test_havuzda_var():
    assert araclar.havuzda_var("Grafik Tasarımcı") is True
    assert araclar.havuzda_var("Astronot") is False


def test_holland_yanlis_cevap_sayisi():
    assert "hata" in araclar.holland_analiz([1, 2, 3])


def test_uyum_kod_uzunlugundan_bagimsiz():
    # Maksimum sosyal profilde tek harfli "S" meslekler (Ogretmen) ust siralarda kalmali.
    sonuc = araclar.holland_analiz([1, 1, 1, 5, 1, 1] * 3)
    assert "Öğretmen" in [m["ad"] for m in sonuc["birincil"]]


def test_baskin_duz_profilde_bos():
    # Tum cevaplar esitse gercek baskin yoktur; uydurma tip cikmamali.
    sonuc = araclar.holland_analiz([3] * 18)
    assert sonuc["baskin_tipler"] == []


def test_baskin_maksimum_sosyalde_tek():
    sonuc = araclar.holland_analiz([1, 1, 1, 5, 1, 1] * 3)
    assert sonuc["baskin_tipler"] == ["S"]


if __name__ == "__main__":
    testler = [f for ad, f in sorted(globals().items()) if ad.startswith("test_")]
    for t in testler:
        t()
        print("OK -", t.__name__)
    print(f"\n{len(testler)} test gecti.")
