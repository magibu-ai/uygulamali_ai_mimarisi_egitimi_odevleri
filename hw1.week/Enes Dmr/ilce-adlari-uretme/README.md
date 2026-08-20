# İlçe Adı Üretme — BPE Tokenizer + Mini Transformer

- Veri: Türkiye ilçe adları (data/ilceler.txt)
- Tokenizer: Sıfırdan yazılmış BPE (bpe_tokenizer.py), vocab_size=300
- Model: single_letter_transformers reposundaki TinyQwen mimarisi
- Eğitim: python train.py
- Üretim: python generate.py 20

## Örnek üretimler

Sarıyer, Tut, Sultanbeyli, Kuluca, Keşap, ...
