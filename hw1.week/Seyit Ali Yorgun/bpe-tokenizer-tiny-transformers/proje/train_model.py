"""Tek bir repo modelini KARAKTER token'ları ile eğit — mineral/taş adı üretme.

Kullanım:  python train_model.py <model_key>
  model_key: qwen3 | qwen3_5 | gemma4 | deepseek3

Her model single_letter_transformers/<key>/ altındaki mimariyi ve o klasörün
kendi CharTokenizer'ını (tokenizer.py) AYNEN kullanır: her token tek karakter,
"\n" hem ad ayıracı hem EOS. Modeller aynı arayüzü paylaşır:
ModelConfig(vocab_size=), forward(x,y)->(logits,loss),
generate(idx,max_new_tokens,temperature,top_k,eos_id).

Bu betiğin BPE ile ilgisi yoktur — BPE ayrı bir ödevdir (bkz. hf_bpe.py).
Girdi, data/mineraller.txt'in ham karakterleridir.

Import izolasyonu: her modelin dosya adları aynı (config.py, model.py,
tokenizer.py...), bu yüzden her model ayrı bir subprocess'te, kendi klasörü
sys.path[0]'da olacak şekilde eğitilir (bkz. train_all.py).
"""

import os
import sys
import torch

REPO = os.path.join(os.path.dirname(__file__), "..", "single_letter_transformers")
# Eğitim verisi kendi seçtiğimiz metindir: mineral/taş adları korpusu.
DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "mineraller.txt")

# key -> (klasör, model sınıfı adı)
MODELS = {
    "qwen3":     ("qwen3",     "TinyQwen"),
    "qwen3_5":   ("qwen3_5",   "TinyQwen35"),
    "gemma4":    ("gemma4",    "TinyGemma"),
    "deepseek3": ("deepseek3", "TinyDeepSeek"),
}

# ---------------------------------------------------------------- ayarlar
BATCH_SIZE = 64
BLOCK_SIZE = 16
STEPS = 3000
LEARNING_RATE = 3e-3
EVAL_EVERY = 500
SEED = 1337


def main():
    key = sys.argv[1]
    subdir, class_name = MODELS[key]

    # Modelin kendi klasörünü import yoluna EN BAŞA koy (config/model buradan gelsin).
    model_dir = os.path.abspath(os.path.join(REPO, subdir))
    sys.path.insert(0, model_dir)

    from config import ModelConfig
    import model as model_mod
    from tokenizer import CharTokenizer      # modelin kendi karakter tokenizer'ı
    ModelClass = getattr(model_mod, class_name)

    torch.manual_seed(SEED)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # Karakter sözlüğü doğrudan veriden kurulur (29 Türkçe harf + "\n").
    tokenizer = CharTokenizer.from_file(DATA_FILE)
    vocab_size = tokenizer.vocab_size
    # Veri zaten "\n" ile ayrılmış isimlerden oluşuyor; ham metni olduğu gibi
    # kodluyoruz, "\n" ayıraç/EOS görevini kendiliğinden görüyor.
    text = open(DATA_FILE, encoding="utf-8").read()
    data = torch.tensor(tokenizer.encode(text), dtype=torch.long)

    def get_batch():
        ix = torch.randint(len(data) - BLOCK_SIZE - 1, (BATCH_SIZE,))
        x = torch.stack([data[i:i + BLOCK_SIZE] for i in ix])
        y = torch.stack([data[i + 1:i + 1 + BLOCK_SIZE] for i in ix])
        return x.to(device), y.to(device)

    cfg = ModelConfig(vocab_size=vocab_size)
    model = ModelClass(cfg).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"[{key}] class={class_name}  vocab={vocab_size}  params={n_params:,}  device={device}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)

    final_loss = None
    for step in range(1, STEPS + 1):
        x, y = get_batch()
        _, loss = model(x, y)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        final_loss = loss.item()
        if step % EVAL_EVERY == 0 or step == 1:
            print(f"[{key}] step {step:5d}  loss {loss.item():.4f}")

    base = float(torch.log(torch.tensor(float(vocab_size))))
    print(f"[{key}] son kayıp={final_loss:.4f}  taban(rastgele)={base:.4f}")

    # Örnek üret.
    model.eval()
    n = 12
    start = torch.full((n, 1), tokenizer.newline_id, dtype=torch.long, device=device)
    with torch.no_grad():
        out = model.generate(start, max_new_tokens=cfg.max_seq_len, temperature=0.8,
                             top_k=None, eos_id=tokenizer.eos_id)
    print(f"[{key}] örnek mineral adları (T=0.8):")
    for row in out.tolist():
        name = tokenizer.decode(row[1:]).split("\n")[0]
        if name:
            print("   ", name)

    ckpt_dir = os.path.join(os.path.dirname(__file__), "checkpoints")
    os.makedirs(ckpt_dir, exist_ok=True)
    ckpt_path = os.path.join(ckpt_dir, f"{key}.pt")
    torch.save({"model": model.state_dict(), "cfg": cfg, "key": key,
                "class_name": class_name, "final_loss": final_loss,
                "n_params": n_params, "base_loss": base}, ckpt_path)
    print(f"[{key}] checkpoint -> {ckpt_path}")


if __name__ == "__main__":
    main()
