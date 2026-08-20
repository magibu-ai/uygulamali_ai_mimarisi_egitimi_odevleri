import os
import sys
import torch

# 1. Üst klasördeki kendi tokenizer.py'mizi görebilmesi için yolu ekliyoruz
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from config import ModelConfig
from model import TinyQwen
from bpe_tokenizer import encode, decode, vocab_size # İŞTE BİZİM BEYİN!
# 2. Veri seti yolunu kendi ilçe listemize göre ayarlıyoruz
DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "dataset.txt")
BATCH_SIZE = 64
BLOCK_SIZE = 16        # Eğitim sırasındaki bağlam uzunluğu
STEPS = 3000
LEARNING_RATE = 3e-3
EVAL_EVERY = 200
SEED = 1337

device = "cuda" if torch.cuda.is_available() else "cpu"
torch.manual_seed(SEED)

# 3. Veriyi BPE Tokenizer'ımız ile okuyup sayılara (tensor) çeviriyoruz
text = open(DATA_FILE, encoding="utf-8").read()
data = torch.tensor(encode(text), dtype=torch.long)

def get_batch():
    ix = torch.randint(len(data) - BLOCK_SIZE - 1, (BATCH_SIZE,))
    x = torch.stack([data[i:i + BLOCK_SIZE] for i in ix])
    y = torch.stack([data[i + 1:i + 1 + BLOCK_SIZE] for i in ix])
    return x.to(device), y.to(device)

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
cfg = ModelConfig(vocab_size=vocab_size)
model = TinyQwen(cfg).to(device)
n_params = sum(p.numel() for p in model.parameters())
print(f"device={device}  vocab_size={vocab_size}  parameters={n_params:,}")

optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)

# ---------------------------------------------------------------------------
# İsim Üretme (Sampling)
# ---------------------------------------------------------------------------
def sample_names(n: int = 10, max_new_tokens: int = 20):
    model.eval()
    # Bizim BPE sisteminde 'Enter' (yeni satır) karakterinin byte ID'si 10'dur.
    start = torch.full((n, 1), 10, dtype=torch.long, device=device)
    out = model.generate(start, max_new_tokens=max_new_tokens, temperature=1.0,
                         top_k=None, eos_id=10)
    model.train()
    names = []
    for row in out.tolist():
        s = decode(row[1:])
        names.append(s.split("\n")[0])
    return names

# ---------------------------------------------------------------------------
# Eğitim Döngüsü
# ---------------------------------------------------------------------------
for step in range(1, STEPS + 1):
    x, y = get_batch()
    _, loss = model(x, y)

    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    if step % EVAL_EVERY == 0 or step == 1:
        print(f"Adım {step:5d}  |  Kayıp (Loss): {loss.item():.4f}")

print("\nÖğrenme tamamlandı! İşte modelin uydurduğu yepyeni ilçe isimleri:")
print("-" * 50)
for name in sample_names(10):
    print("📍", name)

# Sadece modeli ve ayarlarını kaydediyoruz (hata vermemesi için chars silindi)
torch.save({"model": model.state_dict(), "cfg": cfg}, "tiny_qwen.pt")
print("\nModel başarıyla 'tiny_qwen.pt' olarak kaydedildi.")