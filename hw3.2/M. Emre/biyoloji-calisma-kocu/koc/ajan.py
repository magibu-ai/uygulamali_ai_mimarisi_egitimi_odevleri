"""Ajan döngüsü — fonksiyon yönlendirmenin kalbi.

Akış:
    kullanıcı mesajı
        -> backend'e gönder (araç şemalarıyla birlikte)
        -> model tool_call üretirse: aracı çalıştır, sonucu geçmişe ekle, tekrar sor
        -> model düz metin üretirse: cevabı döndür

Backend'den bağımsızdır. Her backend şu sözleşmeyi sağlar:
    sohbet(messages, tools) -> {"content": str | None, "tool_calls": [ ... ]}
    tool_calls öğesi: {"id": str, "name": str, "arguments": dict}
"""

from __future__ import annotations

import json

from . import araclar
from .prompt import sistem_mesaji

MAKS_TUR = 5  # sonsuz tool döngüsüne karşı emniyet


class Koc:
    def __init__(self, backend, ogrenci_id: str = "misafir"):
        self.backend = backend
        self.ogrenci_id = ogrenci_id
        self.gecmis: list[dict] = [sistem_mesaji()]

    def sifirla(self) -> None:
        self.gecmis = [sistem_mesaji()]

    def sor(self, kullanici_mesaji: str) -> tuple[str, list[dict]]:
        """Bir kullanıcı mesajını işler ve yalnızca sonucu döndürür.

        Arayüz canlı akış için sor_akisli() kullanır; bu sarmalayıcı arayüzsüz
        testler ve betikler içindir.
        """
        cevap, kayit = "", []
        for _durum, kayit, cevap_parcasi in self.sor_akisli(kullanici_mesaji):
            if cevap_parcasi is not None:
                cevap = cevap_parcasi
        return cevap, kayit

    def sor_akisli(self, kullanici_mesaji: str):
        """Adım adım ilerleyen generator.

        Her adımda (durum_metni, kayit, cevap) üretir. `cevap` None olduğu sürece
        iş devam ediyor demektir; doluysa tur bitmiştir. Böylece arayüz "model
        düşünüyor -> araç çağrıldı -> sonuç geldi -> cevap yazılıyor" zincirini
        beklemeden gösterebilir.
        """
        self.gecmis.append({"role": "user", "content": kullanici_mesaji})
        kayit: list[dict] = []

        for tur in range(MAKS_TUR):
            etiket = "Modele soruluyor" if tur == 0 else f"Modele tekrar soruluyor (tur {tur + 1})"
            yield etiket, kayit, None

            yanit = self.backend.sohbet(self.gecmis, araclar.ARAC_SEMALARI)
            cagrilar = yanit.get("tool_calls") or []

            # Modele giden ham metni ve modelin ham çıktısını kayda geçir.
            # Şeffaflık zincirinin en alt halkası: cevabın nereden geldiği
            # sadece araç çıktısıyla değil, modelin gördüğü girdiyle de denetlenir.
            if hasattr(self.backend, "son_etkilesim"):
                kayit.append({"tip": "model", "tur": tur + 1, **self.backend.son_etkilesim()})
                yield f"Model yanıtladı ({len(cagrilar)} araç çağrısı)", kayit, None

            if not cagrilar:
                cevap = yanit.get("content") or "(model boş yanıt döndürdü)"
                self.gecmis.append({"role": "assistant", "content": cevap})
                yield "Tamamlandı", kayit, cevap
                return

            # Modelin araç çağrısını geçmişe ekle
            self.gecmis.append(
                {
                    "role": "assistant",
                    "content": yanit.get("content"),
                    "tool_calls": [
                        {
                            "id": c.get("id", f"call_{tur}_{i}"),
                            "type": "function",
                            "function": {"name": c["name"], "arguments": c["arguments"]},
                        }
                        for i, c in enumerate(cagrilar)
                    ],
                }
            )

            # Araçları çalıştır ve sonuçları geçmişe ekle
            for i, cagri in enumerate(cagrilar):
                argumanlar = dict(cagri.get("arguments") or {})
                if cagri["name"] == "cevap_kaydet":
                    # Kimlik modelden GELMEZ, sunucu tarafında zorlanır. Model bu
                    # parametreyi uydurursa başka öğrencinin kaydına yazabilirdi.
                    argumanlar["ogrenci_id"] = self.ogrenci_id

                kayit.append(
                    {"tip": "arac", "arac": cagri["name"], "girdi": argumanlar, "cikti": None}
                )
                yield f"`{cagri['name']}` çağrılıyor, veritabanı sorgulanıyor", kayit, None

                sonuc = araclar.calistir(cagri["name"], argumanlar)
                kayit[-1]["cikti"] = sonuc
                yield f"`{cagri['name']}` sonuçlandı", kayit, None

                self.gecmis.append(
                    {
                        "role": "tool",
                        "name": cagri["name"],
                        "tool_call_id": cagri.get("id", f"call_{tur}_{i}"),
                        "content": sonuc,
                    }
                )

        son = "Araç döngüsü sınırına ulaşıldı, soruyu sadeleştirip tekrar dener misin?"
        self.gecmis.append({"role": "assistant", "content": son})
        yield "Sınıra ulaşıldı", kayit, son


def kaydi_bicimlendir(kayit: list[dict], durum: str = "", bitti: bool = True) -> str:
    """Tool-call kaydını arayüzde/terminalde okunur biçime çevirir.

    `durum` doluysa en üste canlı akış satırı olarak yazılır; henüz sonucu
    gelmemiş araç çağrıları bekliyor işaretiyle gösterilir.
    """
    parcalar = []

    if durum:
        isaret = "✓" if bitti else "⋯"
        parcalar.append(f"**{isaret} {durum}**")

    for adim in kayit:
        if adim.get("tip") == "model":
            parcalar.append(_model_adimi(adim))
        else:
            parcalar.append(_arac_adimi(adim))

    if not kayit and bitti:
        parcalar.append("_Bu yanıtta hiçbir araç çağrılmadı._")

    return "\n\n".join(parcalar)


def _model_adimi(adim: dict) -> str:
    """Modele giden ham metin ve modelin ham çıktısı. Uzun oldukları için
    katlanabilir <details> bloklarına konur."""
    return (
        f"#### Tur {adim['tur']} — model çağrısı\n"
        f"<details><summary>{adim['baslik']}</summary>\n\n"
        f"```{adim['dil']}\n{_kisalt(adim['istek'])}\n```\n\n</details>\n\n"
        f"<details><summary>Modelin ürettiği ham çıktı</summary>\n\n"
        f"```{adim['dil']}\n{_kisalt(adim['yanit']) or '(boş)'}\n```\n\n</details>"
    )


def _arac_adimi(adim: dict) -> str:
    girdi = json.dumps(adim["girdi"], ensure_ascii=False)
    baslik = f"#### Araç: {adim['arac']}\n**Girdi:** `{girdi}`"
    if adim["cikti"] is None:
        return f"{baslik}\n\n_veritabanı sorgulanıyor..._"
    cikti = json.dumps(adim["cikti"], ensure_ascii=False, indent=2)
    return f"{baslik}\n\n**Veritabanından dönen:**\n```json\n{cikti}\n```"


def _kisalt(metin: str, sinir: int = 4000) -> str:
    metin = metin or ""
    if len(metin) <= sinir:
        return metin
    return f"{metin[:sinir]}\n... (+{len(metin) - sinir} karakter)"
