"""Ornek konusmalari calistirip README icin markdown ciktisi uretir.

Her senaryo temiz bir sohbet olarak calistirilir; hangi araclarin tetiklendigi
ve modelin nihai cevabi kaydedilir.

Calistirma:  python ornek_konusmalar.py
Cikti:       ornek_konusmalar.md
"""

from __future__ import annotations

from pathlib import Path

import chat
import ollama_client
import tools

SENARYOLAR = [
    ("Ders kitabindan cevap (fizik)", "Fotoelektrik olayi nedir, nasil aciklanir?"),
    ("Ders kitabindan cevap (kimya)", "Mol kavramini ve mol sayisinin nasil hesaplandigini anlatir misin?"),
    ("Ders kitabindan cevap (tarih)", "Kurtulus Savasi'nda TBMM'nin acilmasinin onemi neydi?"),
    ("Kitapta olmayan guncel bilgi -> internet", "2026 yilinda Nobel Fizik Odulu'nu kim kazandi?"),
    ("Calisma plani", "Kimyada mol konusuna 3 gunde calismak istiyorum, plan yapar misin?"),
    ("Hesaplama", "Bir cismin kutlesi 12 kg, ivmesi 9.8 m/s2. Kuvveti hesaplar misin?"),
    ("Arac gerektirmeyen sohbet", "Merhaba, bugun nasilsin?"),
]


def senaryo_calistir(soru: str, model: str) -> tuple[str, list[str]]:
    """Tek bir soruyu bastan sona calistirir. Doner: (cevap, cagrilan araclar)."""
    mesajlar = [
        {"role": "system", "content": chat.SISTEM_ISTEMI},
        {"role": "user", "content": soru},
    ]
    cagrilanlar: list[str] = []
    mesaj: dict = {}

    for _ in range(chat.MAKS_ARAC_TURU):
        mesaj = ollama_client.chat(mesajlar, model=model, tools=tools.TOOL_SCHEMAS)
        mesajlar.append(mesaj)
        arac_cagrilari = mesaj.get("tool_calls")
        if not arac_cagrilari:
            break
        for cagri in arac_cagrilari:
            ad = cagri["function"]["name"]
            argumanlar = cagri["function"].get("arguments") or {}
            cagrilanlar.append(f"{ad}({argumanlar})")
        mesajlar.extend(chat.araclari_calistir(arac_cagrilari))

    return (mesaj.get("content") or "").strip(), cagrilanlar


if __name__ == "__main__":
    model = ollama_client.CHAT_MODEL
    satirlar = [
        "# Ornek Konusmalar",
        "",
        f"Yerel model: `{model}` (Ollama) — asagidaki ciktilar dogrudan terminalden alinmistir.",
        "",
    ]

    for baslik, soru in SENARYOLAR:
        print(f"\n=== {baslik} ===\nSiz > {soru}")
        cevap, cagrilanlar = senaryo_calistir(soru, model)
        print(f"Asistan > {cevap[:200]}")

        satirlar.append(f"## {baslik}")
        satirlar.append("")
        satirlar.append("```")
        satirlar.append(f"Siz > {soru}")
        for c in cagrilanlar:
            satirlar.append(f"  [arac] {c}")
        satirlar.append("")
        satirlar.append(f"Asistan > {cevap}")
        satirlar.append("```")
        satirlar.append("")

    hedef = Path(__file__).resolve().parent / "ornek_konusmalar.md"
    hedef.write_text("\n".join(satirlar), encoding="utf-8")
    print(f"\nyazildi: {hedef}")
