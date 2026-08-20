"""Bisiklet Gezi Planlayici — arac cagirabilen yerel LLM asistani (komut satiri).

Dongu:
    kullanici sorar -> model ya cevap verir ya da arac cagirir
                    -> araci biz calistiririz, sonucu modele geri veririz
                    -> model nihai cevabi yazar

Kullanim:
    python3 chat.py
    python3 chat.py --model llama3.1:8b
    python3 chat.py --think              # modelin dusunme adimlarini ac (yavaslar)
    python3 chat.py --tek "Kas'tan Demre'ye yarin gravel ile gitsem?"
"""

import argparse
import inspect
from datetime import date

import ollama_client
import tools

MAX_TOOL_ROUNDS = 5  # sonsuz arac dongusune karsi emniyet freni

# --------------------------------------------------------------------------
# SISTEM ISTEMI
#
# Yerel 8B modellerde uzunluk dogrudan itaati dusuruyor: prompt 60 satiri
# gectiginde model ortadaki kurallari atliyor (olculen ornek: takip sorusunda
# kullanicinin verdigi 78 kg / gravel degerlerini birakip varsayilanlara donmesi).
# Bu yuzden istem bilerek kisa tutuldu; her madde tek satir, oncelik sirasina gore.
#
# En kritik kural "SAYI UYDURMA": model mesafeyi hafizasindan yazmaya cok
# meyillidir ("Kas-Demre yaklasik 45 km" gibi) ve arac ciktisiyla celisen tek
# bir sayi plani kullanilmaz hale getirir.
# --------------------------------------------------------------------------
SYSTEM_PROMPT = f"""Sen "Pedal", Turkce bir bisiklet gezi planlayicisisin. Bugun: {date.today().isoformat()}.

ARAC SECIMI:
- Iki yer adi gecen plan sorusu -> tur_planla (tek cagri; rota+hava+efor+ekipman)
- Mesafeyi kullanici veriyor -> efor_hesapla | Sadece hava sorusu -> hava_durumu
- Sadece "ne goturmeliyim" -> ekipman_listesi | "kaydet" -> tur_kaydet | "turlarim" -> turlarim
- Kamp alani, etkinlik, servis, yol durumu -> internet_arama

KURALLAR (onem sirasiyla):
1. Sayilari SADECE arac ciktisindan al. Ciktida olmayan sayiyi yazma, yuvarlama.
2. Takip sorusunda onceki cagrinin degerlerini AYNEN tasi (gun_sonra, baslangic,
   bitis, bisiklet_tipi, surucu_kg). Sadece kullanicinin degistirdigini degistir.
   Aktif gezi bilgisi sana "AKTIF GEZI" notu olarak verilir; oradaki degerleri kullan.
3. Kullanicinin soylemedigi opsiyonel alani (sicaklik_c, karsi_ruzgar_kmh) gonderme.
4. Ekipman/giyim/hava maddeleri sadece arac ciktisindan gelir; en fazla 5 madde say.
   Arac ciktisinda o bilgi yoksa o satiri hic yazma ("bilgi yok" satiri da yazma.)
5. Arac ciktisini kopyalamadan, kendi kisa cumlelerinle ozetle. Ayni plani iki kez yazma.
6. internet_arama sonucunu yeniden yazma: 2-3 sonucu "- baslik - link" satiriyla
   aktar. Sonuclarda gecmeyen tesis adi, sehir ya da ozellik yazmak yasak.
7. Tibbi tavsiye YASAK. Agri, sakatlik, ilac, kalp/tansiyon gecerse SADECE su iki
   cumleyi kur, baska bir sey ekleme (liste, oneri, egzersiz, teshis yok):
   "Bu bir saglik sorusu, degerlendirmesi hekime ait. Istersen daha kisa ve duz
   bir rota planlayabilirim." Sonra kullanicinin cevabini bekle.
8. Zorluk "cok zor" ise ya da yagis %60 ustundeyse kisa uyari ekle. Kask listeden cikmaz.
9. Arac hata dondurduyse gizleme; ne yapilmasi gerektigini soyle, rota uydurma.
10. Varsayim satirina SADECE kullanicinin sana soylemedigi alanlari yaz; kullanicinin
   verdigi degeri (kilo, kondisyon, bisiklet) varsayim gibi gosterme. Yoksa satiri atla.

BICIM: Turkce, kisa cumleler, sade markdown. Once tek satir ozet
(mesafe, tirmanis, sure, zorluk), sonra hava/ruzgar, yakit (su + kalori), ekipman.
"""
# Not: burada bir zamanlar "emoji yok" ve "suslu unicode yok" kurallari da vardi.
# Model bunlara hicbir kosulda uymadi; uyulmayan kural, uyulan kurallarin dikkatini
# seyrelttigi icin cikarildi. Bicimsel tercihleri modele yalvarmak yerine (gerekirse)
# cikti tarafinda temizlemek daha dogru.


def _argumanlari_temizle(fonksiyon, argumanlar: dict) -> tuple[dict, list[str]]:
    """Fonksiyonun imzasinda olmayan anahtarlari atar.

    Kucuk modeller zaman zaman semada bulunmayan bir alan uydurur (gozlemlenen
    ornek: kondisyon yerine baska dilde bir anahtar). Bu cagriyi TypeError ile
    dusurmek yerine fazla alani atip devam etmek daha saglam: zorunlu alanlar
    zaten yerinde oldugu icin arac dogru sonucu uretir.
    """
    gecerli = set(inspect.signature(fonksiyon).parameters)
    temiz = {k: v for k, v in argumanlar.items() if k in gecerli}
    atilan = [k for k in argumanlar if k not in gecerli]
    return temiz, atilan


def araclari_calistir(tool_calls: list[dict], sessiz: bool = False) -> list[dict]:
    """Modelin istedigi araclari calistirir, sonuclari mesaj formatinda dondurur."""
    mesajlar = []
    for cagri in tool_calls:
        ad = cagri["function"]["name"]
        argumanlar = cagri["function"].get("arguments") or {}
        if not sessiz:
            print(f"  🔧 {ad}({argumanlar})")

        fonksiyon = tools.TOOLS.get(ad)
        if fonksiyon is None:
            cikti = f"'{ad}' adinda bir arac yok. Kullanilabilir araclar: {', '.join(tools.TOOLS)}"
        else:
            temiz, atilan = _argumanlari_temizle(fonksiyon, argumanlar)
            if atilan and not sessiz:
                print(f"     (semada olmayan alanlar atlandi: {', '.join(atilan)})")
            try:
                cikti = fonksiyon(**temiz)
            except TypeError as exc:  # zorunlu alan eksik: modele duzeltme sansi ver
                cikti = f"Arac argumanlari hatali ({exc}). Sema'daki alan adlarini kullan."
            except Exception as exc:  # arac hatasi sohbeti bitirmesin
                cikti = f"Arac calistirilamadi: {exc}"

        mesajlar.append({"role": "tool", "tool_name": ad, "content": cikti})

        # Aktif gezi notu: modelin takip sorusunda parametreleri kaybetmesine karsi.
        # Sadece istem yazmak yetmedi (olculdu: "78 kg / gravel" ikinci soruda
        # varsayilanlara donuyordu). Basarili bir tur_planla'dan sonra kullanilan
        # argumanlari sistem notu olarak geri enjekte etmek bunu kapatiyor: deger
        # artik uzun sohbet gecmisinin icinde degil, son mesajin hemen yaninda.
        if ad == "tur_planla" and not cikti.startswith("Plan yapilamadi"):
            ozet = ", ".join(f"{k}={v}" for k, v in sorted(temiz.items()))
            mesajlar.append({
                "role": "system",
                "content": f"AKTIF GEZI: {ozet}. Takip sorularinda bu degerleri koru, "
                           f"sadece kullanicinin acikca degistirdigini degistir.",
            })
    return mesajlar


def yanitla(mesajlar: list[dict], model: str, think: bool, sessiz: bool = False) -> str:
    """Arac dongusunu doner ve modelin nihai metnini uretir."""
    mesaj = {}
    for _ in range(MAX_TOOL_ROUNDS):
        mesaj = ollama_client.chat(mesajlar, model=model, tools=tools.TOOL_SCHEMAS, think=think)
        mesajlar.append(mesaj)
        tool_calls = mesaj.get("tool_calls")
        if not tool_calls:
            break
        mesajlar.extend(araclari_calistir(tool_calls, sessiz=sessiz))
    else:
        return "Arac dongusu uzadi, kisa bir soru ile tekrar deneyin."

    metin = (mesaj.get("content") or "").strip()
    if not metin:
        # Gozlenen davranis: model bazen ne arac cagirir ne de metin uretir, bos
        # mesaj doner ve kullanici bos ekran gorur. Tek seferlik bir durtme,
        # sohbeti yeniden baslatmadan cevabi geri getiriyor.
        mesajlar.append({"role": "system", "content": "Bos cevap verdin. Kullanicinin son "
                                                      "sorusunu araclari kullanarak yanitla."})
        mesaj = ollama_client.chat(mesajlar, model=model, tools=tools.TOOL_SCHEMAS, think=think)
        mesajlar.append(mesaj)
        if mesaj.get("tool_calls"):
            mesajlar.extend(araclari_calistir(mesaj["tool_calls"], sessiz=sessiz))
            mesaj = ollama_client.chat(mesajlar, model=model, tools=tools.TOOL_SCHEMAS, think=think)
            mesajlar.append(mesaj)
        metin = (mesaj.get("content") or "").strip()
    return metin or "Cevap uretemedim, soruyu kisaltip tekrar dener misin?"


def main() -> None:
    ayristirici = argparse.ArgumentParser(description="Bisiklet gezi planlayici asistan.")
    ayristirici.add_argument("--model", default=ollama_client.CHAT_MODEL, help="Ollama sohbet modeli")
    ayristirici.add_argument("--think", action="store_true", help="Modelin dusunme adimlarini ac")
    ayristirici.add_argument("--tek", help="Tek soru sor, cevabi yaz ve cik (test icin)")
    args = ayristirici.parse_args()

    mesajlar = [{"role": "system", "content": SYSTEM_PROMPT}]

    if args.tek:
        mesajlar.append({"role": "user", "content": args.tek})
        print(f"Siz > {args.tek}")
        try:
            print(f"\nPedal > {yanitla(mesajlar, args.model, args.think)}\n")
        except RuntimeError as exc:
            print(f"\nHata: {exc}\n")
        return

    print("🚲 Pedal — Bisiklet Gezi Planlayici")
    print(f"  model: {args.model}")
    print("  ornek: 'Kas'tan Demre'ye yarin gravel ile gitsem nasil olur?'")
    print("  cikmak icin: cik\n")

    while True:
        try:
            soru = input("Siz > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not soru:
            continue
        if soru.lower() in {"cik", "çık", "exit", "quit"}:
            break

        mesajlar.append({"role": "user", "content": soru})
        try:
            print(f"\nPedal > {yanitla(mesajlar, args.model, args.think)}\n")
        except RuntimeError as exc:
            print(f"\nHata: {exc}\n")


if __name__ == "__main__":
    main()
