"""Eğitilmiş checkpoint'lerden gerçek sonuç raporu üret -> SONUCLAR_LOG.md.

Kullanım:  python sonuclar_uret.py

Elle yazılmış SONUCLAR.md'nin aksine bu dosya, checkpoints/*.pt içindeki gerçek
metrikleri (parametre, son kayıp, taban kayıp) okur ve her modelden canlı örnek
üretir. Böylece sonuçlar tekrar üretilebilir ve doğrulanabilir.
"""

import os
import sys
import subprocess
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
CKPT_DIR = os.path.join(HERE, "checkpoints")
REPO = os.path.join(HERE, "..", "single_letter_transformers")
KEYS = ["qwen3", "qwen3_5", "gemma4", "deepseek3"]
OUT = os.path.join(HERE, "SONUCLAR_LOG.md")


def load_meta(key: str) -> dict:
    """Checkpoint metadata'sını oku. cfg pickle'ı config modülünü ister ->
    modelin klasörünü path'e koy, önceki config/model cache'ini temizle."""
    for m in ("config", "model"):
        sys.modules.pop(m, None)
    sys.path.insert(0, os.path.abspath(os.path.join(REPO, key)))
    return torch.load(os.path.join(CKPT_DIR, f"{key}.pt"), map_location="cpu", weights_only=False)


def samples(key: str, n: int, temp: float) -> list[str]:
    r = subprocess.run([sys.executable, os.path.join(HERE, "generate_model.py"), key, str(n), str(temp)],
                       capture_output=True, text=True, check=True)
    return [l for l in r.stdout.splitlines() if l.strip()]


def main():
    rows = []
    for key in KEYS:
        c = load_meta(key)
        rows.append((key, c["class_name"], c["n_params"], c["base_loss"], c["final_loss"]))
    rows.sort(key=lambda r: r[4])   # son kayıba göre

    lines = ["# Sonuç Logu (checkpoint'lerden otomatik üretildi)", ""]
    lines.append("`python sonuclar_uret.py` ile üretilir. Metrikler eğitilmiş modellerin")
    lines.append("gerçek değerleridir; örnekler her çalıştırmada canlı üretilir.")
    lines.append("")
    lines.append("## Metrikler (son kayıba göre sıralı)")
    lines.append("")
    lines.append("| Sıra | Model | Sınıf | Parametre | Taban kayıp | Son kayıp | İyileşme |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for i, (key, cls, n, base, final) in enumerate(rows, 1):
        lines.append(f"| {i} | {key} | {cls} | {n:,} | {base:.2f} | {final:.4f} | {base/final:.1f}× |")
    lines.append("")

    for temp in (0.8, 1.1):
        lines.append(f"## Üretilen mineral adları (T={temp})")
        lines.append("")
        for key, *_ in rows:
            names = ", ".join(samples(key, 10, temp))
            lines.append(f"- **{key}:** {names}")
        lines.append("")

    open(OUT, "w", encoding="utf-8").write("\n".join(lines))
    print(f"yazıldı -> {OUT}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
