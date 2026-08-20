"""Uçtan uca akış testi.

Varsayılan olarak yerel backend'i (Ollama + projenin kendi chat_template.jinja
dosyası) kullanır. Groq ile denemek için:  python test_akis.py groq
"""

import sys

from koc.ajan import Koc, kaydi_bicimlendir


def backend_sec(ad: str):
    if ad == "groq":
        from koc.llm.groq_backend import GroqBackend

        return GroqBackend()
    from koc.llm.ollama_backend import OllamaBackend

    return OllamaBackend()


SENARYOLAR = [
    ("Mayoz nedir?", "terim_ara çağırmalı, sayfa numarasıyla cevaplamalı"),
    ("Kuantum fotosentezi nedir?", "HALÜSİNASYON TESTİ: uydurmamalı"),
    ("Bana mayoz konusundan bir soru sor", "quiz_getir çağırmalı"),
    ("C", "cevap_kaydet çağırmalı (VERİTABANINA YAZMA)"),
]


if __name__ == "__main__":
    backend = backend_sec(sys.argv[1] if len(sys.argv) > 1 else "ollama")
    print(f"Backend: {backend.ad}")
    print(f"Kendi chat_template kullanılıyor mu: {backend.kendi_sablonu_kullanir}")

    koc = Koc(backend, ogrenci_id="test_ogrenci")

    for mesaj, beklenen in SENARYOLAR:
        print("\n" + "=" * 72)
        print(f"KULLANICI: {mesaj}")
        print(f"BEKLENEN : {beklenen}")
        print("-" * 72)

        cevap, kayit = koc.sor(mesaj)

        araclar_kaydi = [a for a in kayit if a.get("tip") != "model"]
        for adim in araclar_kaydi:
            print(f"  [TOOL] {adim['arac']}({adim['girdi']})")
            ozet = str(adim["cikti"])
            print(f"         -> {ozet[:150]}{'...' if len(ozet) > 150 else ''}")

        if not araclar_kaydi:
            print("  [TOOL] (hiçbir araç çağrılmadı)")

        print(f"\nASİSTAN: {cevap}")
