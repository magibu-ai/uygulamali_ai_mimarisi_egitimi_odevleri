"""
04_train_tokenizer.py

corpus.txt uzerinde kendi tokenizer'inizi egitir (Hugging Face `tokenizers`
kutuphanesi ile hizli BPE). Turkce gibi eklemeli (agglutinative) diller icin
SentencePiece Unigram modeli de iyi sonuc verir; asagida her iki secenek de
var, VOCAB_ALGO ile secilebilir.

Cikti: tokenizer/tokenizer.json  (+ PreTrainedTokenizerFast olarak da kaydedilir)

Not (README'de de var): bu tokenizer'i dogrudan Gemma agirliklariyla
degistirip fine-tune etmek embedding katmanini yeniden egitmeyi gerektirir.
Once "Gemma tokenizer'ina kiyasla token verimliligi" analizi icin,
fine-tune'da ise Gemma'nin kendi tokenizer'i ile devam etmeniz onerilir
(README > "Tokenizer + Gemma hakkinda pratik bir uyari" bolumune bakin).
"""
import os

from tokenizers import Tokenizer, models, pre_tokenizers, trainers, decoders, normalizers

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = HERE
CORPUS_PATH = os.path.join(ROOT, "corpus.txt")
OUT_DIR = os.path.join(ROOT, "tokenizer")

VOCAB_SIZE = 8000
VOCAB_ALGO = "bpe"  # "bpe" ya da "unigram"

SPECIAL_TOKENS = ["<unk>", "<pad>", "<bos>", "<eos>"]


def train_bpe():
    tokenizer = Tokenizer(models.BPE(unk_token="<unk>"))
    tokenizer.normalizer = normalizers.NFKC()
    tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tokenizer.decoder = decoders.ByteLevel()

    trainer = trainers.BpeTrainer(
        vocab_size=VOCAB_SIZE,
        special_tokens=SPECIAL_TOKENS,
        min_frequency=2,
    )
    tokenizer.train([CORPUS_PATH], trainer)
    return tokenizer


def train_unigram():
    tokenizer = Tokenizer(models.Unigram())
    tokenizer.normalizer = normalizers.NFKC()
    tokenizer.pre_tokenizer = pre_tokenizers.Metaspace()
    tokenizer.decoder = decoders.Metaspace()

    trainer = trainers.UnigramTrainer(
        vocab_size=VOCAB_SIZE,
        special_tokens=SPECIAL_TOKENS,
        unk_token="<unk>",
    )
    tokenizer.train([CORPUS_PATH], trainer)
    return tokenizer


def main():
    if not os.path.exists(CORPUS_PATH):
        print(f"{CORPUS_PATH} bulunamadi. Once 03_build_tokenizer_corpus.py calistirin.")
        return

    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"Tokenizer egitiliyor (algo={VOCAB_ALGO}, vocab_size={VOCAB_SIZE})...")
    tokenizer = train_bpe() if VOCAB_ALGO == "bpe" else train_unigram()

    tok_json_path = os.path.join(OUT_DIR, "tokenizer.json")
    tokenizer.save(tok_json_path)
    print(f"Kaydedildi -> {tok_json_path}")

    # Transformers ile uyumlu PreTrainedTokenizerFast olarak da kaydet
    try:
        from transformers import PreTrainedTokenizerFast
        fast_tok = PreTrainedTokenizerFast(
            tokenizer_object=tokenizer,
            unk_token="<unk>",
            pad_token="<pad>",
            bos_token="<bos>",
            eos_token="<eos>",
        )
        fast_tok.save_pretrained(OUT_DIR)
        print(f"transformers formatinda da kaydedildi -> {OUT_DIR}")
    except ImportError:
        print("`transformers` kurulu degil, sadece tokenizer.json kaydedildi. "
              "(pip install transformers ile transformers formatini da alabilirsiniz.)")

    # Hizli bir ornek: birkac cumleyi tokenlere ayirip goster
    samples = [
        "Bu ilaç aç karnına alınmamalıdır ve günde iki kez kullanılmalıdır.",
        "Hastaya reçete edilen antibiyotik tedavisi on gün sürmelidir.",
        "Bitki ekstresinin antioksidan aktivitesi HPLC yöntemiyle belirlenmiştir.",
        "Formülasyon çalışmasında mukoadeziv bukkal yamalar geliştirilmiştir.",
        "Diyabetik hastalarda insülin direnci ile ilgili yeni bulgular elde edilmiştir.",
        "Antikanser etkinliği in vitro ve in vivo modellerde değerlendirilmiştir.",
        "Eczacılar, ilaç etkileşimlerini hastalarla paylaşmalıdır.",
        "Nanopartiküllerin sitotoksisitesi hücre kültüründe test edilmiştir.",
        "Yaşlı hastalarda polifarmasi önemli bir sağlık sorunudur.",
        "Yeni geliştirilen analitik yöntem, ilacın kandaki konsantrasyonunu ölçmektedir.",
    ]
    for sample in samples:
        encoding = tokenizer.encode(sample)
        print(f"\nOrnek cumle: {sample}")
        print(f"Token sayisi: {len(encoding.tokens)}")
        print(f"Tokenlar: {encoding.tokens}")


if __name__ == "__main__":
    main()
