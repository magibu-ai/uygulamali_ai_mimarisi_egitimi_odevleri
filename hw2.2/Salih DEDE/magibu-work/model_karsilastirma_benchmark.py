# Gerekli paketler:
#   pip install pandas httpx sentence-transformers torch transformers peft huggingface_hub
#
# Kullanım:
#   python3 model_karsilastirma_benchmark.py
#
# 5 modeli SIRAYLA (birbiri ardına) test eder:
#   - 2 HuggingFace modeli (fine-tuned + taban) lokalde transformers/peft ile senkron çalışır.
#   - 3 OpenRouter modeli API üzerinden, kendi içinde (soru bazında) async/paralel çağrılarla
#     çalışır, ama modellerin kendisi yine sırayla işlenir.
#
# Her model için model_cevabi + doğru/yanlış işaretlemesi dahil tüm sonuçlar
# "<model_adi>_benchmark_sonuc.json" dosyasına yazılır; ilerleme hem konsola hem de
# "model_karsilastirma.log" dosyasına loglanır. Bir model daha önce tamamlanmışsa
# (çıktı dosyası varsa) tekrar çalıştırılmaz.

import asyncio
import gc
import json
import logging
import os
import sys
import time

ENV_DOSYASI = "../Ders2/DataCollection-Scrapping/.env"
BENCHMARK_REPO_ID = "SalihHub/trendyol-marangoz-satici-benchmark"
LOG_DOSYASI = "model_karsilastirma.log"

MODELLER = [
    ("hf", "SalihHub/trendyol-marangoz-finetuned-gemma-4-E4B-it"),
    ("hf", "google/gemma-4-E4B-it"),
    ("openrouter", "google/gemma-4-26b-a4b-it"),
    ("openrouter", "qwen/qwen3.5-flash-02-23"),
    ("openrouter", "deepseek/deepseek-v4-flash"),
]

MAX_ESZAMANLI_ISTEK = 8  # OpenRouter modelleri için soru bazında eşzamanlılık


def kur_loglama():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(LOG_DOSYASI, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("benchmark")


log = kur_loglama()


def benchmarki_hub_dan_yukle(repo_id):
    """Kendi yayınladığımız benchmark dataset'ini HuggingFace Hub'dan indirip
    liste (dict listesi) olarak döner; yerel bir kopyaya ihtiyaç duymaz."""
    from huggingface_hub import hf_hub_download

    log.info(f"Benchmark HuggingFace Hub'dan indiriliyor: {repo_id}")
    jsonl_yolu = hf_hub_download(repo_id, "data/train.jsonl", repo_type="dataset")

    kayitlar = []
    with open(jsonl_yolu, "r", encoding="utf-8") as f:
        for satir in f:
            satir = satir.strip()
            if satir:
                kayitlar.append(json.loads(satir))
    return kayitlar


def env_dosyasini_yukle(yol):
    if not os.path.exists(yol):
        return
    with open(yol, "r", encoding="utf-8") as f:
        for satir in f:
            satir = satir.strip()
            if not satir or satir.startswith("#") or "=" not in satir:
                continue
            anahtar, _, deger = satir.partition("=")
            os.environ.setdefault(anahtar.strip(), deger.strip().strip('"').strip("'"))


def sistem_promptu_olustur(satir):
    return (
        "Sen bir marangoz ustasısın. Aşağıdaki ürünün satıcısısın.\n"
        f"Ürün Özellikleri: {satir['urun_aciklamasi']}"
    )


def kullanici_promptu_olustur(satir):
    secenekler = satir["secenekler"]
    secenek_metni = "\n".join(f"{harf}: {metin}" for harf, metin in secenekler.items())
    return (
        "Sana bir müşteri sorusu ve olası cevap seçeneklerini veriyorum. Sadece hangi "
        "seçeneğin bu soruya en doğru VE en kibar/müşteriyi ikna edici şekilde cevap "
        "verdiğini yaz. Örneğin 'A' veya 'B' gibi. Lütfen herhangi bir açıklama yapma!\n"
        f"Soru: {satir['soru']}\n{secenek_metni}"
    )


# ---------------------------------------------------------------------------
# Cevap kontrolü: birebir harf eşleşmesi, olmazsa anlamsal benzerlik yedeği.
# ---------------------------------------------------------------------------
_anlamsal_model = None


def anlamsal_model_al():
    global _anlamsal_model
    if _anlamsal_model is None:
        from sentence_transformers import SentenceTransformer
        log.info("Anlamsal benzerlik modeli yükleniyor (paraphrase-multilingual-mpnet-base-v2)...")
        _anlamsal_model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
    return _anlamsal_model


def cevap_dogru_mu(dogru_harf, verilen_cevap, secenekler):
    harfler = list(secenekler.keys())
    metinler = [secenekler[h] for h in harfler]
    verilen_cevap = (verilen_cevap or "").strip().upper()

    if not verilen_cevap:
        return False
    elif verilen_cevap == dogru_harf:
        return True
    elif len(verilen_cevap) > 1 and verilen_cevap[1] in [" ", ":", ")", "=", "-", "."]:
        return verilen_cevap[0] == dogru_harf
    else:
        model = anlamsal_model_al()
        encoded_cevap = model.encode([verilen_cevap])
        encoded_secenekler = model.encode(metinler)
        benzerlik = model.similarity(encoded_cevap, encoded_secenekler).tolist()[0]
        en_yuksek_index = benzerlik.index(max(benzerlik))
        return harfler[en_yuksek_index] == dogru_harf


# ---------------------------------------------------------------------------
# Ortak sonuç yardımcıları
# ---------------------------------------------------------------------------
def bos_sonuc_iskeleti(model_detay):
    return {
        "model": model_detay["model"],
        "ozet": dict(model_detay),
        "kategori_sonuclari": {},
        "isaretlemeler": [],
    }


def sonucu_isle(sonuc, satir, cevap):
    dogru_harf = satir["dogru_secenek"]
    secenekler = satir["secenekler"]
    kategori = satir["kategori"]
    dogru_mu = cevap_dogru_mu(dogru_harf, cevap, secenekler)

    kat = sonuc["kategori_sonuclari"].setdefault(kategori, {"dogru": 0, "toplam": 0})
    kat["toplam"] += 1
    if dogru_mu:
        kat["dogru"] += 1

    sonuc["isaretlemeler"].append({
        "urun_id": satir["urun_id"],
        "kategori": kategori,
        "soru": satir["soru"],
        "dogru_secenek": dogru_harf,
        "model_cevabi": cevap,
        "dogru_mu": bool(dogru_mu),
    })
    return dogru_mu


def sonucu_tamamla(sonuc, baslama, toplam_soru):
    dogru_sayisi = sum(1 for isaret in sonuc["isaretlemeler"] if isaret["dogru_mu"])
    sonuc["ozet"]["dogru_cevap_sayisi"] = dogru_sayisi
    sonuc["ozet"]["basari"] = round(100 * dogru_sayisi / toplam_soru, 2)
    sonuc["ozet"]["toplam_sure"] = round(time.time() - baslama, 3)
    log.info(
        f"[{sonuc['model']}] TAMAMLANDI: {dogru_sayisi}/{toplam_soru} doğru "
        f"(%{sonuc['ozet']['basari']}), {sonuc['ozet']['toplam_sure']} sn."
    )


def sonucu_kaydet(sonuc):
    dosya_adi = f"{sonuc['model']}_benchmark_sonuc.json"
    with open(dosya_adi, "w", encoding="utf-8") as f:
        json.dump(sonuc, f, ensure_ascii=False, indent=2)
    log.info(f"[{sonuc['model']}] sonuçlar '{dosya_adi}' dosyasına kaydedildi.")


# ---------------------------------------------------------------------------
# HuggingFace backend: lokal, senkron (transformers + peft)
# ---------------------------------------------------------------------------
class HuggingFaceBackend:
    """HuggingFace Hub'dan bir modeli (düz model ya da LoRA adaptörü) indirip
    lokalde (MPS/CUDA/CPU) çalıştırır."""

    def __init__(self, model_repo):
        import torch
        from huggingface_hub import hf_hub_download
        from huggingface_hub.errors import EntryNotFoundError
        from transformers import AutoModelForCausalLM, AutoTokenizer

        adapter_config = None
        try:
            adapter_config_yolu = hf_hub_download(model_repo, "adapter_config.json")
            with open(adapter_config_yolu) as f:
                adapter_config = json.load(f)
        except EntryNotFoundError:
            adapter_config = None

        if torch.cuda.is_available():
            device = "cuda"
        elif torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"
        self.device = device
        self.dtype = torch.bfloat16 if device != "cpu" else torch.float32

        if adapter_config is not None:
            # Bu repo bir LoRA adaptörü: taban modeli indirip adaptörü üzerine bindiriyoruz.
            from peft import LoraConfig, PeftModel

            taban_model_repo = adapter_config.get("base_model_name_or_path", "")
            if "unsloth" in taban_model_repo and "bnb-4bit" in taban_model_repo:
                # Unsloth'un 4bit (bnb) taban modelleri CUDA gerektirir; Mac/CPU/MPS için
                # aynı mimarinin quantize edilmemiş halini kullanıyoruz.
                taban_model_repo = "google/gemma-4-E4B-it"

            log.info(f"Taban model indiriliyor: {taban_model_repo} (bu işlem uzun sürebilir)")
            base_model = AutoModelForCausalLM.from_pretrained(
                taban_model_repo, dtype=self.dtype, low_cpu_mem_usage=True
            )

            log.info(f"LoRA adaptörü yükleniyor: {model_repo}")
            # Bu adaptör dil modeli katmanlarının yanı sıra vision/audio kule katmanlarını
            # da hedefliyor; o katmanlardaki bazı projeksiyonlar peft'in henüz desteklemediği
            # bir sarmalayıcı kullanıyor. Benchmark salt metin tabanlı olduğundan LoRA'yı
            # yalnızca gerçek nn.Linear olan projeksiyonlara uyguluyoruz.
            proj_ekleri = ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj")
            lora_hedef_modulleri = [
                isim for isim, modul in base_model.named_modules()
                if isim.split(".")[-1] in proj_ekleri and isinstance(modul, torch.nn.Linear)
            ]
            if not lora_hedef_modulleri:
                raise RuntimeError(
                    "Taban modelde LoRA için uygun (nn.Linear) projeksiyon modülü bulunamadı."
                )

            lora_config = LoraConfig.from_pretrained(model_repo)
            lora_config.target_modules = lora_hedef_modulleri
            self.model = PeftModel.from_pretrained(base_model, model_repo, config=lora_config)
        else:
            log.info(f"Model indiriliyor: {model_repo} (bu işlem uzun sürebilir)")
            self.model = AutoModelForCausalLM.from_pretrained(
                model_repo, dtype=self.dtype, low_cpu_mem_usage=True
            )

        self.tokenizer = AutoTokenizer.from_pretrained(model_repo)
        self.model.to(device)
        self.model.eval()

        self.model_repo = model_repo
        self.model_adi = "hf_" + model_repo.split("/")[-1]

    def cevap_uret(self, sistem_prompt, kullanici_prompt):
        import torch

        mesajlar = [
            {"role": "system", "content": sistem_prompt},
            {"role": "user", "content": kullanici_prompt},
        ]
        girdi = self.tokenizer.apply_chat_template(
            mesajlar, add_generation_prompt=True, return_tensors="pt", return_dict=True
        ).to(self.device)

        pad_token_id = self.tokenizer.pad_token_id
        if pad_token_id is None:
            pad_token_id = self.tokenizer.eos_token_id

        with torch.no_grad():
            cikti = self.model.generate(
                **girdi,
                max_new_tokens=8,
                do_sample=False,
                pad_token_id=pad_token_id,
            )

        girdi_uzunlugu = girdi["input_ids"].shape[-1]
        yeni_tokenlar = cikti[0][girdi_uzunlugu:]
        return self.tokenizer.decode(yeni_tokenlar, skip_special_tokens=True)

    def model_detay(self):
        toplam_parametre = sum(p.numel() for p in self.model.parameters())
        return {
            "model": self.model_adi,
            "format": "safetensors",
            "family": getattr(self.model.config, "model_type", "bilinmiyor"),
            "parameter_size": f"{toplam_parametre / 1e9:.2f}B",
            "quantization_level": str(self.dtype).replace("torch.", ""),
        }

    def temizle(self):
        import torch

        del self.model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        elif torch.backends.mps.is_available():
            torch.mps.empty_cache()


def hf_modelini_test_et(model_repo, benchmark):
    log.info(f"===== [{model_repo}] HuggingFace modeli yükleniyor (lokal, senkron) =====")
    backend = HuggingFaceBackend(model_repo)
    model_adi = backend.model_adi
    log.info(f"[{model_adi}] model yüklendi, {len(benchmark)} soru sırayla test edilecek.")

    sonuc = bos_sonuc_iskeleti(backend.model_detay())
    baslama = time.time()

    for i, satir in enumerate(benchmark, start=1):
        sistem = sistem_promptu_olustur(satir)
        kullanici = kullanici_promptu_olustur(satir)
        cevap = backend.cevap_uret(sistem, kullanici)
        dogru_mu = sonucu_isle(sonuc, satir, cevap)
        log.info(
            f"[{model_adi}] {i}/{len(benchmark)} | soru: {satir['soru'][:60]!r} | "
            f"cevap: {cevap!r} | doğru mu: {dogru_mu}"
        )

    sonucu_tamamla(sonuc, baslama, len(benchmark))
    backend.temizle()
    return sonuc


# ---------------------------------------------------------------------------
# OpenRouter backend: API, soru bazında async/paralel
# ---------------------------------------------------------------------------
async def openrouter_cevap_uret(client, api_key, model_ismi, sistem_prompt, kullanici_prompt, max_deneme=3):
    payload = {
        "model": model_ismi,
        "messages": [
            {"role": "system", "content": sistem_prompt},
            {"role": "user", "content": kullanici_prompt},
        ],
        "max_tokens": 16,
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = "https://openrouter.ai/api/v1/chat/completions"

    son_hata = None
    for deneme in range(1, max_deneme + 1):
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"] or ""
        except Exception as e:
            son_hata = str(e)
            await asyncio.sleep(2 * deneme)
    log.warning(f"[{model_ismi}] cevap alınamadı, boş dönülüyor. Hata: {son_hata}")
    return ""


async def openrouter_modelini_test_et_async(model_ismi, benchmark, api_key, max_eszamanli=MAX_ESZAMANLI_ISTEK):
    import httpx

    model_adi = "openrouter_" + model_ismi.replace("/", "_")
    log.info(
        f"===== [{model_ismi}] OpenRouter modeli test ediliyor "
        f"({len(benchmark)} soru, eşzamanlılık: {max_eszamanli}) ====="
    )

    sonuc = bos_sonuc_iskeleti({
        "model": model_adi, "format": "api", "family": "openrouter",
        "parameter_size": "bilinmiyor", "quantization_level": "bilinmiyor",
    })
    baslama = time.time()
    sem = asyncio.Semaphore(max_eszamanli)
    kilit = asyncio.Lock()
    tamamlanan = 0

    async with httpx.AsyncClient() as client:
        async def bir_soruyu_isle(satir):
            nonlocal tamamlanan
            sistem = sistem_promptu_olustur(satir)
            kullanici = kullanici_promptu_olustur(satir)
            async with sem:
                cevap = await openrouter_cevap_uret(client, api_key, model_ismi, sistem, kullanici)
            async with kilit:
                dogru_mu = sonucu_isle(sonuc, satir, cevap)
                tamamlanan += 1
                log.info(
                    f"[{model_adi}] {tamamlanan}/{len(benchmark)} | soru: {satir['soru'][:60]!r} | "
                    f"cevap: {cevap!r} | doğru mu: {dogru_mu}"
                )

        await asyncio.gather(*(bir_soruyu_isle(satir) for satir in benchmark))

    sonucu_tamamla(sonuc, baslama, len(benchmark))
    return sonuc


def openrouter_modelini_test_et(model_ismi, benchmark, api_key):
    return asyncio.run(openrouter_modelini_test_et_async(model_ismi, benchmark, api_key))


# ---------------------------------------------------------------------------
# Ana akış: 5 modeli SIRAYLA işler
# ---------------------------------------------------------------------------
def model_adini_hesapla(tur, model_ismi):
    if tur == "hf":
        return "hf_" + model_ismi.split("/")[-1]
    return "openrouter_" + model_ismi.replace("/", "_")


def main():
    env_dosyasini_yukle(ENV_DOSYASI)
    api_key = os.environ.get("OPENROUTER_API_KEY")

    try:
        benchmark = benchmarki_hub_dan_yukle(BENCHMARK_REPO_ID)
    except Exception:
        log.exception(f"Benchmark Hub'dan indirilemedi: {BENCHMARK_REPO_ID}")
        sys.exit(1)
    log.info(f"Benchmark yüklendi: {len(benchmark)} soru.")

    tum_sonuclar = []
    for tur, model_ismi in MODELLER:
        model_adi = model_adini_hesapla(tur, model_ismi)
        cikti_dosyasi = f"{model_adi}_benchmark_sonuc.json"

        if os.path.exists(cikti_dosyasi):
            log.info(f"[{model_adi}] daha önce tamamlanmış ({cikti_dosyasi}), tekrar çalıştırılmıyor.")
            with open(cikti_dosyasi, "r", encoding="utf-8") as f:
                tum_sonuclar.append(json.load(f))
            continue

        try:
            if tur == "hf":
                sonuc = hf_modelini_test_et(model_ismi, benchmark)
            else:
                if not api_key:
                    log.error(f"[{model_adi}] OPENROUTER_API_KEY bulunamadı, atlanıyor.")
                    continue
                sonuc = openrouter_modelini_test_et(model_ismi, benchmark, api_key)
        except Exception:
            log.exception(f"[{model_adi}] test edilirken hata oluştu, atlanıyor.")
            continue

        sonucu_kaydet(sonuc)
        tum_sonuclar.append(sonuc)

    if not tum_sonuclar:
        log.warning("Hiçbir model için sonuç üretilemedi.")
        return

    ozet_satirlari = [
        {
            "model": s["model"],
            "basari (%)": s["ozet"]["basari"],
            "dogru_cevap_sayisi": s["ozet"]["dogru_cevap_sayisi"],
            "toplam_sure_sn": s["ozet"]["toplam_sure"],
        }
        for s in tum_sonuclar
    ]
    ozet_satirlari.sort(key=lambda x: x["basari (%)"], reverse=True)

    log.info("===== KARŞILAŞTIRMA ÖZETİ =====")
    for satir in ozet_satirlari:
        log.info(
            f"{satir['model']:<45} | %{satir['basari (%)']:>6.2f} | "
            f"{satir['dogru_cevap_sayisi']:>3} doğru | {satir['toplam_sure_sn']:>8.1f} sn"
        )

    with open("karsilastirma_ozeti.json", "w", encoding="utf-8") as f:
        json.dump(ozet_satirlari, f, ensure_ascii=False, indent=2)
    log.info("Karşılaştırma özeti 'karsilastirma_ozeti.json' dosyasına kaydedildi.")


if __name__ == "__main__":
    main()
