"""
Yonlendirme (routing) katmani.
- Birincil: Groq LLM ile gercek tool calling (OpenAI-uyumlu API).
- Yedek: LLM cagrilamazsa (kota/hata) devreye giren basit kural tabanli router.
Her iki yolda da tool'lar gercek veriyle calisir; cevaplar uydurma icermez.
"""
import os
import re
import json
from tools import TOOLS, TOOL_FUNCS

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = (
    "Sen bir kutuphane asistanisin. Gorevin okuyuculara kitap bulmak, oneri yapmak, "
    "odunc verme ve iade islemlerinde yardimci olmaktir. "
    "\n\n!!! EN ONEMLI KURAL: Bu kutuphanenin SADECE veritabaninda kayitli kitaplari vardir. "
    "Sen bir kitabin var oldugunu bilsen bile (orn. Foundation, Solaris gibi), eger arac "
    "(tool) bunu dondurmedi ise O KITABI ASLA ONERME ya da bahsetme. Yanitindaki HER kitap "
    "adi, bir tool'un sana dondurdugu sonuclardan gelmelidir. Kendi genel bilginden kitap "
    "adi UYDURMAK en buyuk hatadir. Bir tool cagirdiginda, SADECE onun dondurdugu kitaplari "
    "kullan; sonuca kendi bildigin baska kitaplari EKLEME. !!!\n\n"
    "Kurallar:\n"
    "- Kitap bilgisi, durumu, oneri ve konu gibi her sey icin MUTLAKA ilgili araci (tool) cagir. "
    "Asla veritabaninda olmayan bir kitabi ya da bilgiyi uydurma.\n"
    "- ODUNC ALMA cok onemli kurallara tabidir:\n"
    "  1) Sadece kullanici ACIKCA odunc almak istedigini soylerse (orn. 'odunc alabilir miyim', "
    "'bu kitabi alayim') kitap_odunc_al cagir. Kullanici sadece 'bosta mi', 'musait mi', 'var mi' "
    "diye SORARSA bu bir bilgi sorusudur; SADECE durumu bildir, KESINLIKLE odunc alma islemi yapma.\n"
    "  2) Odunc almak icin okuyucunun ADI gerekir. Kullanici adini soylememisse ONCE 'Kitabi kimin "
    "adina odunc alalim?' diye sor. Okuyucu adini ASLA kendin uydurma (Ahmet, Ayse gibi isimler atama).\n"
    "  3) Once kitap_ara ile kitabin id'sini bul, sonra (ad varsa) kitap_odunc_al cagir.\n"
    "- Kitap onerisi yaparken ASLA kendi bilginden kitap onerme. Oneri icin MUTLAKA "
    "kitap_oner aracini cagir ve SADECE bu araci dondugu kitaplari oner. Aractan donmeyen "
    "hicbir kitabi (baska yazar, baska baslik) yanitina ekleme; kutuphanede olmayan kitap onermek yasaktir.\n"
    "- Okuyucu bir tur soylediginde (orn. 'polisiye severim'), istersen once kalinlik "
    "(ince/kalin) veya koken (yerli/yabanci) tercihini sorabilirsin; sonra kitap_oner ile filtrele. "
    "Tercih belirtmezse dogrudan kitap_oner ile o turden oneri getir.\n"
    "- Bir kitabin konusu sorulursa kitap_konusu aracini SADECE BIR KEZ cagir. "
    "Sonuc bulunamazsa ('bulundu': false) tekrar deneme; kullaniciya konu bilgisinin "
    "su an alinamadigini kibarca soyle.\n"
    "- Ayni araci ayni parametrelerle asla ikinci kez cagirma.\n"
    "- Kitaplarin id numarasi teknik bir detaydir; onu kendi islemlerinde (odunc/iade) "
    "kullan ama kullaniciya soyleme. Kullaniciya kitabi adiyla anlat.\n"
    "- Oneri sunarken sicak ve arkadasca ol. Kitaplari maddeler halinde, her biri icin "
    "baslik, yazar ve sayfa sayisiyla listele. 'X adet kitap bulundu', 'sayfa ve koken bilgisi "
    "veriliyor' gibi teknik/rapor dili kullanma; sanki bir kutuphaneciyle sohbet ediyormus gibi anlat. "
    "Ornek ton: 'Polisiye seviyorsan sunlara bayilirsin:' gibi. Sonunda kisa bir kapanis cumlesi ekle.\n"
    "- Yanitlarini Turkce ve samimi ver."
)


# =========================================================
# BIRINCIL: Groq LLM ile tool calling
# =========================================================
def _groq_client():
    from groq import Groq
    return Groq(api_key=GROQ_API_KEY)


def _dogrula(metin):
    """Yanit dogrulama: DB'de olmayan bir kitap uydurulmus mu diye bilgi notu.
    Kesin halusinasyon tespiti zor oldugu icin, bu katman ek bir guvenlik agidir;
    asil koruma system prompt + tool zorunlulugudur."""
    return metin  # şu an pasif; system prompt asil korumayi sagliyor


def llm_ile_yanit(user_msg, history, adim_log):
    """
    Groq LLM ile cok turlu tool-calling. adim_log listesine arka plan adimlarini yazar.
    Basarisizsa exception firlatir (app yedege duser).
    """
    client = _groq_client()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for rol, icerik in history:
        if rol and icerik:
            messages.append({"role": rol, "content": icerik})
    messages.append({"role": "user", "content": user_msg})

    from db import kitap_ara_db
    for turn in range(1, 6):
        resp = client.chat.completions.create(
            model=GROQ_MODEL, messages=messages,
            tools=TOOLS, tool_choice="auto", temperature=0.2, max_tokens=800,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return _dogrula(msg.content or "")

        messages.append({
            "role": "assistant", "content": msg.content or "",
            "tool_calls": [{"id": tc.id, "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                           for tc in msg.tool_calls],
        })
        adim_log.append(f"[Turn {turn}] Arac Cagrilari:")
        for tc in msg.tool_calls:
            fname = tc.function.name
            try:
                fargs = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
            except Exception:
                fargs = {}
            arg_str = ", ".join(f"{k}={v!r}" for k, v in fargs.items())
            adim_log.append(f"   -> {fname}({arg_str})")
            func = TOOL_FUNCS.get(fname)
            result = func(**fargs) if func else {"error": f"bilinmeyen arac: {fname}"}
            adim_log.append(f"   <- {json.dumps(result, ensure_ascii=False)}")
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "name": fname, "content": json.dumps(result, ensure_ascii=False)})
        adim_log.append("")
    return "Islem cok fazla adim gerektirdi, lutfen sadelestirin."


# =========================================================
# YEDEK: kural tabanli router (LLM yoksa/hata verirse)
# =========================================================
def kural_ile_yanit(user_msg, history, adim_log):
    """Anahtar-kelime + desen tabanli niyet cozumleme. LLM yedegi.
    Amac: LLM yokken bile kullanicinin cogu istegini dogru tool'a yonlendirmek."""
    msg = user_msg.lower()
    msg = msg.replace("i̇", "i")  # Turkce buyuk I sorunu

    def cagir(fname, **kw):
        adim_log.append("[Yedek Router] Arac Cagrisi:")
        arg_str = ", ".join(f"{k}={v!r}" for k, v in kw.items())
        adim_log.append(f"   -> {fname}({arg_str})")
        result = TOOL_FUNCS[fname](**kw)
        adim_log.append(f"   <- {json.dumps(result, ensure_ascii=False)}")
        return result

    # --- tur tespiti (once daha spesifik turler; 'roman' en sona) ---
    # 'polisiye roman' -> polisiye olmali, o yuzden roman en dusuk oncelikli
    tur_haritasi = [
        ("polisiye", ["polisiye", "dedektif", "cinayet", "gizem", "suç roman"]),
        ("korku", ["korku", "gerilim"]),
        ("bilim kurgu", ["bilim kurgu", "bilimkurgu", "distopya", "uzay"]),
        ("fantastik", ["fantastik", "fantezi", "büyü", "ejderha"]),
        ("klasik", ["klasik", "dünya klasik"]),
        ("cocuk", ["çocuk", "cocuk"]),
        ("bilim", ["bilim kitab", "popüler bilim", "bilimsel"]),
        ("roman", ["roman", "aşk roman", "dram"]),  # en genel, en sonda
    ]
    secilen_tur = None
    for tur, anahtarlar in tur_haritasi:
        if any(a in msg for a in anahtarlar):
            secilen_tur = "polisiye" if tur == "korku" else tur
            break

    # YAZAR adindan tur cikarimi: mesajda bir yazar geciyorsa onun turu daha guveniliar.
    # ("roman" gibi genel bir kelime yakalanmis olsa bile yazar turu tercih edilir.)
    if secilen_tur is None or secilen_tur == "roman":
        from db import _conn
        conn = _conn()
        yazarlar = conn.execute("SELECT DISTINCT yazar, tur FROM kitaplar").fetchall()
        conn.close()
        for row in yazarlar:
            parcalar = [p for p in row["yazar"].lower().split() if len(p) > 3]
            if any(p in msg for p in parcalar):
                secilen_tur = row["tur"]
                adim_log.append(f"[Yedek Router] '{row['yazar']}' yazarindan tur cikarildi: {row['tur']}")
                break

    # --- niyet: oneri mi? ---
    oneri_kelimeleri = ["oner", "öner", "tavsiye", "sever", "seviyorum", "istiyorum",
                        "okumak", "bakabilir", "ne okusam", "bir kitap", "kitap arıyorum",
                        "benzer", "begendi", "beğendi", "gibi kitap", "benzeri"]
    oneri_niyeti = any(w in msg for w in oneri_kelimeleri)

    # --- niyet: konu mu? ---
    if any(w in msg for w in ["konu", "ne anlatıyor", "ne hakkında", "özet", "hakkında bilgi"]):
        kitap = _kitap_adi_cikar(user_msg)
        if kitap:
            r = cagir("kitap_konusu", baslik=kitap)
            return r.get("konu") or r.get("mesaj")

    # --- niyet: durum/musaitlik mi? (oneri niyeti + tur yoksa) ---
    durum_niyeti = any(w in msg for w in ["müsait", "musait", "boşta", "bosta", "durum", "mevcut"])
    # "var mı" tek basina durum sayilir AMA oneri/benzer niyeti varsa oneriye birak
    if ("var mı" in msg or "var mi" in msg) and not (oneri_niyeti or secilen_tur):
        durum_niyeti = True
    if durum_niyeti and not (oneri_niyeti and secilen_tur):
        kitap = _kitap_adi_cikar(user_msg)
        if kitap:
            return cagir("odunc_durumu", sorgu=kitap)["mesaj"]

    # --- niyet: oneri (tur biliniyorsa) ---
    if secilen_tur and (oneri_niyeti or True):  # tur belirtilmisse oneri kabul et
        koken = "yerli" if "yerli" in msg else ("yabanci" if ("yabanci" in msg or "yabancı" in msg) else None)
        max_s = 300 if any(w in msg for w in ["ince", "kısa", "kisa", "kolay"]) else None
        min_s = 500 if any(w in msg for w in ["kalın", "kalin", "uzun"]) else None
        r = cagir("kitap_oner", tur=secilen_tur, koken=koken, max_sayfa=max_s, min_sayfa=min_s)
        if r["bulundu"]:
            sat = "\n".join(f"- {o['baslik']} / {o['yazar']} ({o['sayfa']} sayfa)" for o in r["oneriler"])
            return f"Polisiye seviyorsan sunlara bayilirsin:\n{sat}\nKeyifli okumalar!" if secilen_tur=="polisiye" else f"Sana su kitaplari onerebilirim:\n{sat}\nKeyifli okumalar!"
        return r["mesaj"]

    # --- arama (baslik/yazar) ---
    kitap = _kitap_adi_cikar(user_msg)
    if kitap:
        r = cagir("kitap_ara", sorgu=kitap)
        if r["bulundu"]:
            sat = "\n".join(f"- {k['baslik']} / {k['yazar']} ({k['durum']})" for k in r["kitaplar"])
            return "Bulduklarim:\n" + sat
        return r["mesaj"]

    return ("Kutuphane asistaniyim. Kitap arayabilir, tur bazli oneri isteyebilir "
            "(orn. 'polisiye onerir misin'), odunc/iade islemi yapabilirsiniz.")


def _kitap_adi_cikar(text):
    """Tirnak icindeki ya da bilinen baslik parcasini kabaca cikarir."""
    m = re.search(r'["\'“]([^"\'”]+)["\'”]', text)
    if m:
        return m.group(1)
    # tirnak yoksa: DB'de gecen bir baslikla eslesme ara
    from db import kitap_ara_db
    kelimeler = [w for w in re.findall(r'\w+', text) if len(w) > 3]
    for boy in range(len(kelimeler), 0, -1):
        for i in range(len(kelimeler) - boy + 1):
            aday = " ".join(kelimeler[i:i+boy])
            if kitap_ara_db(aday):
                return aday
    return None


# =========================================================
# ANA GIRIS
# =========================================================
def yanit_uret(user_msg, history):
    """
    Once LLM dener; kota/hata olursa kural tabanli yedege duser.
    Doner: (yanit_metni, arka_plan_adimlari, kullanilan_katman)
    """
    adim_log = []
    if GROQ_API_KEY:
        try:
            cevap = llm_ile_yanit(user_msg, history, adim_log)
            return cevap, adim_log, "LLM (Groq)"
        except Exception as e:
            adim_log.append(f"[Bilgi] LLM kullanilamadi ({type(e).__name__}), yedek router devrede.")
    cevap = kural_ile_yanit(user_msg, history, adim_log)
    return cevap, adim_log, "Kural tabanli yedek"