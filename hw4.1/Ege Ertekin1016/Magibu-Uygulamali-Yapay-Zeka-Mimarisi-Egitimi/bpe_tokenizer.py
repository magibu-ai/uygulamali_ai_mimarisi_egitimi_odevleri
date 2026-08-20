import os

# bpe_tokenizer.py'nin bulunduğu klasörün yolunu al
base_dir = os.path.dirname(__file__)
file_path = os.path.join(base_dir, "dataset.txt")

# Dosyayı artık mutlak yol ile okuyoruz
with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

raw_bytes = text.encode("utf-8")
tokens = list(raw_bytes)

print("Toplam token (byte) sayısı:", len(tokens))
print("İlk 20 token:", tokens[:20])

def get_stats(ids):
    counts = {}
    for pair in zip(ids, ids[1:]):
        counts[pair] = counts.get(pair, 0) + 1
    return counts

stats = get_stats(tokens)

top_pair = max(stats, key=stats.get)
print(f"En çok tekrar eden çift: {top_pair} -> Tekrar sayısı: {stats[top_pair]}")

def merge(ids, pair, idx):
    newids = []
    i = 0
    while i < len(ids):
        if i < len(ids) - 1 and ids[i] == pair[0] and ids[i+1] == pair[1]:
            newids.append(idx)
            i += 2 
        else:
            newids.append(ids[i]) # Eşleşme yoksa sayıyı aynen aktar
            i += 1
    return newids

new_tokens = merge(tokens, top_pair, 256)

print(f"Eski token uzunluğu: {len(tokens)}")
print(f"Yeni token uzunluğu: {len(new_tokens)}")


vocab_size = 306
num_merges = vocab_size - 256

tokens = list(raw_bytes) 

merges = {} 

print(f"Eğitim başlıyor... Hedef {num_merges} yeni kural (hece) öğrenmek.")

for i in range(num_merges):
    stats = get_stats(tokens)
    
    top_pair = max(stats, key=stats.get)
    
    idx = 256 + i
    
    tokens = merge(tokens, top_pair, idx)
    
    merges[top_pair] = idx
    
    print(f"Adım {i+1}: {top_pair} birleştirildi -> Yeni ID: {idx}")

print(f"\nEğitim tamamlandı! Final token uzunluğu: {len(tokens)}")



vocab = {idx: bytes([idx]) for idx in range(256)}
for (p0, p1), idx in merges.items():
    vocab[idx] = vocab[p0] + vocab[p1]

def decode(ids):
    tokens = b"".join(vocab[idx] for idx in ids)
    text = tokens.decode("utf-8", errors="replace")
    return text

def encode(text):
    tokens = list(text.encode("utf-8"))
    
    while len(tokens) >= 2:
        stats = get_stats(tokens)
        pair = min(stats, key=lambda p: merges.get(p, float("inf")))
        
        if pair not in merges:
            break
            
        idx = merges[pair]
        tokens = merge(tokens, pair, idx)
        
    return tokens

test_kelime = "adapazarı"
sifrelenmis = encode(test_kelime)
cozulmus = decode(sifrelenmis)

print(f"\n--- TEST ---")
print(f"Orijinal: {test_kelime}")
print(f"Encode Edilmiş (Tokenlar): {sifrelenmis}")
print(f"Decode Edilmiş (Metin): {cozulmus}")