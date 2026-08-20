# -*- coding: utf-8 -*-
# Konum: C:\Magibu\ODEV-1.py
# Çalıştır: python ODEV-1.py
#
# Türkiye ilçe adlarını karakter seviyesinde üretmeyi öğrenen 4 mimari:
# Qwen3, Qwen3.5, Gemma, DeepSeek-V3 — aynı veri, aynı CharTokenizer.

import os, sys, json, importlib, urllib.request
import torch

# ============================ YOLLAR ============================
BURASI = os.path.dirname(os.path.abspath(__file__))          # C:\Magibu
REPO   = os.path.join(BURASI, "single_letter_transformers")  # C:\Magibu\single_letter_transformers
os.chdir(REPO)

# ============================ AYARLAR ============================
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DATA_PATH = "data/ilce.txt"

STEPS = 5000
BLOCK = 16
BATCH = 64
LR    = 3e-3

# Mimariler arasında SADECE bu üç alan değişir
ARCHS = [
    {"folder": "qwen3",     "cls": "TinyQwen",     "ckpt": "qwen3/tiny_qwen.pt"},
    {"folder": "qwen3_5",   "cls": "TinyQwen35",   "ckpt": "qwen3_5/tiny_qwen35.pt"},
    {"folder": "gemma4",    "cls": "TinyGemma",    "ckpt": "gemma4/tiny_gemma.pt"},
    {"folder": "deepseek3", "cls": "TinyDeepSeek", "ckpt": "deepseek3/tiny_deepseek.pt"},
]

# ============================ VERİ ============================
ILCE_URL = "https://raw.githubusercontent.com/volkansenturk/turkiye-iller-ilceler/master/ilce.json"
TR_HARF  = set("abcçdefgğhıijklmnoöprsştuüvyz")


def turkce_kucuk(s):
    """Python'un .lower()'ı I -> i yapar, Türkçede yanlış. Önce elle düzelt."""
    return (s.replace("I", "ı").replace("İ", "i")
             .replace("Ç", "ç").replace("Ş", "ş").replace("Ğ", "ğ")
             .replace("Ü", "ü").replace("Ö", "ö").lower())


def ilce_indir():
    print("[veri] ilçe listesi indiriliyor...")
    with urllib.request.urlopen(ILCE_URL, timeout=30) as r:
        veri = json.loads(r.read().decode("utf-8"))

    # PHPMyAdmin export formatı: type=="table" olan blokta "data" listesi var
    kayitlar = []
    for blok in veri:
        if blok.get("type") == "table" and "data" in blok:
            kayitlar = blok["data"]
            break
    ham = [k["name"] for k in kayitlar]
    print(f"[veri] ham kayıt: {len(ham)}")

    temiz = set()
    atilan_merkez = 0
    atilan_gecersiz = 0
    for ad in ham:
        w = turkce_kucuk(ad).strip()
        if w == "merkez":                    # idari etiket, gerçek yer adı değil
            atilan_merkez += 1
            continue
        if not w or not set(w) <= TR_HARF:   # "19 mayıs" gibi rakam/boşluk içerenler
            atilan_gecersiz += 1
            continue
        temiz.add(w)                         # set: iller arası tekrarları eler

    print(f"[veri] elenen: merkez={atilan_merkez}, geçersiz={atilan_gecersiz}, "
          f"tekrar={len(ham) - atilan_merkez - atilan_gecersiz - len(temiz)}")
    return sorted(temiz)


def veri_setini_yaz():
    os.makedirs("data", exist_ok=True)
    if os.path.exists(DATA_PATH):
        print(f"[veri] {DATA_PATH} zaten var, dokunmuyorum.")
        return
    kelimeler = ilce_indir()
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(kelimeler) + "\n")
    print(f"[veri] {DATA_PATH} yazıldı — {len(kelimeler)} ilçe.")


# ==================== MİMARİ YÜKLEME ====================
# Dört klasör de model.py / config.py / tokenizer.py isimlerini paylaşıyor.
# Python modülleri cache'lediği için her mimariden sonra sys.modules temizlenmeli,
# yoksa ikinci mimari birincinin dosyalarını kullanır.

def _import_et(folder):
    once = set(sys.modules)
    sys.path.insert(0, os.path.join(REPO, folder))
    cfg_mod   = importlib.import_module("config")
    model_mod = importlib.import_module("model")
    tok_mod   = importlib.import_module("tokenizer")
    return cfg_mod, model_mod, tok_mod, set(sys.modules) - once


def _temizle_modul(folder, eklenen):
    for ad in eklenen:
        sys.modules.pop(ad, None)
    yol = os.path.join(REPO, folder)
    if yol in sys.path:
        sys.path.remove(yol)


# ==================== EĞİTİM / ÜRETİM ====================
@torch.no_grad()
def ornek_uret(model, tok, cfg, adet=8, sicaklik=0.8):
    model.eval()
    start = torch.full((adet, 1), tok.eos_id, dtype=torch.long, device=DEVICE)
    out = model.generate(start, max_new_tokens=cfg.max_seq_len,
                         temperature=sicaklik, eos_id=tok.eos_id)
    kelimeler = []
    for row in out.tolist():
        w = tok.decode(row[1:]).split("\n")[0].strip()
        if w:
            kelimeler.append(w)
    return kelimeler


def bir_mimari_egit(arch, data_ids, chars, mevcut_ilceler):
    cfg_mod, model_mod, tok_mod, eklenen = _import_et(arch["folder"])
    ModelConfig = cfg_mod.ModelConfig
    ModelClass  = getattr(model_mod, arch["cls"])
    tok = tok_mod.CharTokenizer(chars)

    cfg   = ModelConfig(vocab_size=len(chars))
    model = ModelClass(cfg).to(DEVICE)
    opt   = torch.optim.AdamW(model.parameters(), lr=LR)

    n = data_ids.numel()
    model.train()
    son_loss = None
    for step in range(1, STEPS + 1):
        ix = torch.randint(0, n - BLOCK - 1, (BATCH,)).tolist()
        x = torch.stack([data_ids[i:i + BLOCK]         for i in ix])
        y = torch.stack([data_ids[i + 1:i + 1 + BLOCK] for i in ix])
        _, loss = model(x, y)
        opt.zero_grad(); loss.backward(); opt.step()
        son_loss = loss.item()
        if step % 500 == 0:
            print(f"  [{arch['folder']:<9}] step {step:>4}  loss {son_loss:.3f}")

    torch.save({"model": model.state_dict(), "chars": chars, "cfg": cfg}, arch["ckpt"])

    # 30 örnek üret, kaçı gerçekten yeni ölç
    ornekler = ornek_uret(model, tok, cfg, adet=30)
    yeni = [w for w in ornekler if w not in mevcut_ilceler]
    nparam = sum(p.numel() for p in model.parameters())

    _temizle_modul(arch["folder"], eklenen)
    return son_loss, nparam, ornekler, yeni


def main():
    print(f"[yol] repo = {REPO}")
    veri_setini_yaz()

    # Tokenizer'ı bir kez kur; aynı chars tüm mimarilere verilir (adil karşılaştırma)
    cfg_mod, model_mod, tok_mod, eklenen = _import_et(ARCHS[0]["folder"])
    base_tok = tok_mod.CharTokenizer.from_file(DATA_PATH)
    chars = base_tok.chars
    metin = open(DATA_PATH, encoding="utf-8").read()
    data_ids = torch.tensor(base_tok.encode(metin), dtype=torch.long, device=DEVICE)
    _temizle_modul(ARCHS[0]["folder"], eklenen)

    mevcut_ilceler = set(metin.split())
    print(f"[tokenizer] vocab={len(chars)}  toplam_token={data_ids.numel()}\n")

    sonuclar = []
    for arch in ARCHS:
        print(f"=== {arch['folder']} ({arch['cls']}) eğitiliyor ===")
        loss, nparam, ornekler, yeni = bir_mimari_egit(arch, data_ids, chars, mevcut_ilceler)
        sonuclar.append((arch, loss, nparam, ornekler, yeni))
        print(f"  kaydedildi -> {arch['ckpt']}\n")

    print("==================== SONUÇ TABLOSU ====================")
    for arch, loss, nparam, ornekler, yeni in sonuclar:
        oran = 100 * len(yeni) / max(len(ornekler), 1)
        print(f"\n{arch['cls']:<14} params~{nparam:>8,}  final_loss {loss:.3f}  "
              f"yeni %{oran:.0f} ({len(yeni)}/{len(ornekler)})")
        print(f"   gerçek : {', '.join(w for w in ornekler if w in mevcut_ilceler)[:80]}")
        print(f"   uydurma: {', '.join(yeni)[:80]}")


if __name__ == "__main__":
    main()