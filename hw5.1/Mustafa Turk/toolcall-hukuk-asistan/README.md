# İcra & İflas Hukuku Asistanı

Yerelde çalışan bir dil modeli (Ollama) üzerinde, **Yargı MCP** ile Türk içtihat veritabanlarına bağlanan hukuk araştırma asistanı. Terminal ve web arayüzü olmak üzere iki kullanım biçimi sunar.

Proje, [`malibayram/single_letter_transformers/ollama_asistan`](https://github.com/malibayram/single_letter_transformers/tree/main/ollama_asistan) dizini temel alınarak geliştirilmiştir. Devralınan ve değiştirilen kısımlar bölüm 4'te verilmiştir.

**Ana bulgu:** Yargı MCP'nin 31 aracını modele olduğu gibi vermek yerine 3 sarmalayıcı araca indirgemek, araç seçim isabetini **%45'ten %80'e** çıkardı.

---

## 1. Senaryo

İcra takibi yürüten bir avukatın masasındaki üç işi tek arayüzde toplar: emsal karar bulmak, kanun maddesine ulaşmak, işlemiş faizi hesaplamak.

| İhtiyaç | Araç | Kaynak |
|---|---|---|
| Emsal karar | `ictihat_ara` | Yargı MCP → `search_bedesten_unified` |
| Kararın tam metni | `karar_metni_getir` | Yargı MCP → `get_bedesten_document_markdown` |
| Kanun maddesi | `mevzuat_ara` | Web araması + sayfa indirme (bkz. 5.2) |
| İşlemiş faiz, toplam alacak | `faiz_hesapla` | Yerel hesaplama (projeye özel araç) |
| Güncel duyuru / oran | `internet_search` | DuckDuckGo |

---

## 2. Kurulum

```bash
# 1. Model
ollama pull qwen3:4b-q4_K_M

# 2. Bağımlılıklar
pip install -r requirements.txt

# 3. uv (Yargı MCP'yi yerelde çalıştırmak için)
# Windows:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# macOS / Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh

# 4. MCP sunucusundaki araç adlarını doğrula
python yargi_mcp.py --list

# 5. Çalıştır
python chat.py --log        # terminal
python arayuz.py            # web arayüzü → http://127.0.0.1:7860
```

Yargı MCP varsayılan olarak `stdio` ile yerelde çalışır, kimlik doğrulama gerektirmez. Uzak sunucuya geçmek için `yargi_mcp.py` içinde `MOD = "http"` yapılır (OAuth ister).

---

## 3. Dosya Yapısı

```
kullanıcı (terminal / tarayıcı)
        │
    chat.py · arayuz.py ── sohbet döngüsü, MAX_TOOL_ROUNDS emniyet freni
        │
        ├── ollama_client.py ──▶ Ollama (qwen3:4b)
        │
        ├── tools.py ──▶ faiz_hesapla · mevzuat_ara · internet_search
        │
        └── yargi_mcp.py ──facade──▶ Yargı MCP (31 araç)
```

| Dosya | Görevi | Baz repodaki karşılığı |
|---|---|---|
| `chat.py` | Terminal sohbet döngüsü | `chat.py` |
| `arayuz.py` | Gradio web arayüzü | — (yeni) |
| `ollama_client.py` | Ollama HTTP sarmalayıcı | `ollama_client.py` |
| `tools.py` | Araç fonksiyonları ve şemaları | `tools.py` |
| `yargi_mcp.py` | MCP köprüsü + facade katmanı | `medical_rag.py` |
| `prompt.py` | Sistem istemi | (`chat.py` içindeydi) |
| `olcum_arac_secimi.py` | Araç seçimi doğruluk ölçümü | `olcum_karsilastirma.py` |

---

## 4. Baz Repodan Ne Devralındı, Ne Değişti

**Aynen korunanlar**

- `ollama_client._post` / `chat` — `requests` ile ham HTTP; `ollama` kütüphanesi kullanılmıyor.
- `chat.py`'deki döngü mantığı, `MAX_TOOL_ROUNDS` emniyet freni, `run_tool_calls`, `🔧` log biçimi.
- Araçların **string** döndürme kuralı ve `TOOLS` + `TOOL_SCHEMAS` ikilisi.
- `internet_search` ve Wikipedia yedeği.
- `olcum_karsilastirma.py`'nin "hissederek değil ölçerek karar ver" yaklaşımı.

**Değişenler**

- `ollama_client.py`'deki embedding bölümü çıkarıldı; bu projede RAG yerine MCP var. `num_ctx` parametresi eklendi.
- `medical_rag.py`'nin "iki kapı" fikri MCP'ye uyarlandı: *arama kapısı* → **seçim kapısı**, *üretim kapısı* → **bağlam kapısı**.
- Sistem istemi `prompt.py`'ye taşındı; ölçüm betiği import ediyor, `chat.py` içinde kalsaydı import anında sohbet döngüsü çalışırdı.
- 4 genel amaçlı araç yerine 5 icra hukuku aracı.
- Gradio arayüzü eklendi.

---

## 5. Optimizasyon Çalışması

### 5.1 Facade katmanı — 31 araçtan 3 araca

`python yargi_mcp.py --list` çıktısına göre Yargı MCP sunucusunda **28 araç** var (yerel araçlarla birlikte modele sunulan toplam 31):

```
search_emsal_detailed_decisions   search_bedesten_unified
search_uyusmazlik_decisions       search_anayasa_unified
search_kik_v2_decisions           search_rekabet_kurumu_decisions
search_sayistay_unified           search_kvkk_decisions
search_bddk_decisions             search_btk_decisions
search_gib_ozelge                 search_sigorta_tahkim_decisions
... ve her biri için ayrı bir get_*_document_markdown aracı
```

Tamamını modele vermek iki nedenle çalışmıyor:

1. **Seçim sorunu.** Hepsi "hukuk araması" gibi görünür. Ölçümde 4B model, itirazın iptali sorusuna `search_btk_decisions` (Bilgi Teknolojileri Kurumu), icra dairesi sorusuna `search_sayistay_unified` çağırdı.
2. **Bağlam sorunu.** 31 araç şeması bağlam penceresinin önemli bir kısmını yiyor. Ölçümde model, HAM kurulumda kendi yerel `faiz_hesapla` aracını **hiç çağıramadı** (bkz. 7.2).

`yargi_mcp.py` içindeki `ROTALAR` tablosu modele yalnızca 2 MCP aracı gösterir, arkada doğru sunucu aracına yönlendirir:

```python
ROTALAR = {
    "ictihat_ara":       {"arac": "search_bedesten_unified",
                          "esleme": {"konu": "phrase"}},
    "karar_metni_getir": {"arac": "get_bedesten_document_markdown",
                          "esleme": {"belge_id": "documentId"}},
}
```

Yerel araçlarla birlikte model toplam **5 araç** görür.

### 5.2 Eksik araç tespiti ve üç aşamalı telafi

Araç listesi incelenirken kritik bir bulgu çıktı: **28 aracın hiçbiri mevzuat araması yapmıyor.** Sunucu içtihat ve düzenleyici kurum kararlarına odaklanmış, mevzuat.gov.tr entegrasyonu yok. İlk denemede `mevzuat_ara` çağrısı `Unknown tool` hatası verdi. Model bu boşluğu kendiliğinden `internet_search`'e kaçarak doldurmaya çalıştı — kural ihlali değil, seçenek yokluğuydu.

Telafi üç adımda oturdu:

| Deneme | Sonuç |
|---|---|
| `site:mevzuat.gov.tr <konu>` | Boş döndü — `site:` operatörü DuckDuckGo lite arayüzünde desteklenmiyor |
| Alan adı düz metin olarak sorguya eklendi | Bağlantılar geldi, ama model "madde metnini bulamadım" dedi — arama yalnızca başlık ve özet döndürüyor |
| Sayfa indirme + madde kesme eklendi | Madde metni bağlamın içine girdi |

Son hâli, RAG'ın en basit biçimi: **ara → getir → kes.**

```python
def mevzuat_ara(konu: str) -> str:
    sonuc = internet_search(f"{konu} mevzuat kanun madde", max_results=6)
    adresler = re.findall(r"https?://\S+", sonuc)
    madde_no = (re.search(r"\b(\d{1,3})\b", konu) or [None, ""])[1]
    for url in adresler[:4]:
        metin = _sayfa_metni(url)          # indir, HTML etiketlerini temizle
        parca = _madde_kes(metin, madde_no)  # "MADDE 89" başlığını bul, çevresini kes
        if parca:
            return f"Kaynak: {url}\n\n{parca}"
    return "Madde metni sayfalardan cikarilamadi. Bulunan kaynaklar:\n" + sonuc
```

### 5.3 Senaryoya özel araç: faiz hesaplayıcı

Faiz oranları dönemsel olarak değişir (yasal faiz %9 → %24, avans faizi %15,75 → %48). Bir alacak birden fazla oran dönemini kapsıyorsa tek oranla çarpmak ciddi hata üretir.

`faiz_hesapla` dönemi oran değişimlerine göre parçalara böler:

```
2023-03-15 - 2024-01-01 |  292 gün | %15,75 |      18.900,00 TL
2024-01-01 - 2026-08-12 |  954 gün | %48,00 |     188.186,30 TL
```

Bir aracın modelden neden daha güvenilir olduğunun somut örneği: model tahmin eder, kod hesaplar.

Oran tablosu `tools.FAIZ_ORANLARI` içinde tutulur ve manuel güncellenir; kodda `<-- dogrula` ile işaretlenmiştir.

### 5.4 Bağlam kırpma

MCP arama sonuçları 20–50 KB dönebiliyor. `yargi_mcp._kirp()` sonuç listesini `MAX_SONUC` kadarına indirir, `MAX_KARAKTER` sınırında keser. Bu olmadan iki araç çağrısından sonra sistem istemi bağlamdan düşüyor ve model kurallarını unutuyordu.

Donanım kısıtı nedeniyle sınırlar `MAX_SONUC = 3`, `MAX_KARAKTER = 1500` olarak belirlendi. Detay kaybı yok — kullanıcı bir kararın tamamını isterse `karar_metni_getir` zinciri devreye giriyor.

### 5.5 Sistem istemi kararları

| Karar | Gerekçe |
|---|---|
| Araç seçim tablosu isteme başa alındı | Düz metin açıklamadan daha isabetli seçim |
| "Sorguyu hukuki terimle kur" kuralı | Kullanıcı "borçlu itiraz etti" der; arama "itirazın iptali davası" olmalı, yoksa sonuç boş döner |
| Zincir kuralı (arama → id → tam metin) | Model tam metni doğrudan istemeye çalışıyordu |
| Uydurma yasağı, emir kipinde ve kısa | Uzun nazik cümleler küçük modelde göz ardı ediliyor |
| `temperature = 0.1` | Yükseltince araç seçimi bozuluyor |
| `think: False` | Reasoning modu tool call biçimini bozabiliyor |

---

## 6. Donanım Kısıtı ve Model Seçimi

**Test donanımı:** NVIDIA GeForce GTX 1660, 6 GB VRAM (ekran çıkışı da aynı kartta).

| Model | VRAM dağılımı | Sonuç |
|---|---|---|
| `qwen3:8b`, num_ctx 16384 | %46 CPU / %54 GPU | İstekler 600 sn'de zaman aşımına uğradı |
| `qwen3:4b`, num_ctx 8192 | %30 CPU / %70 GPU | Çalışıyor, yavaş |
| `qwen3:4b-q4_K_M`, num_ctx 4096 | Ağırlıklı GPU | Kullanılabilir |

Bu kısıt, facade katmanının ikinci gerekçesi oldu: 4B'lik bir modele 31 araç şeması vermek hem bağlam bütçesi hem seçim isabeti açısından mümkün değildi. Araç sayısını düşürmek yalnızca bir doğruluk optimizasyonu değil, bu donanımda çalışabilmenin ön koşuluydu.

---

## 7. Ölçüm

```bash
python olcum_arac_secimi.py
```

20 test sorusu (6 içtihat, 4 mevzuat, 4 faiz, 2 internet, 4 araç çağrılmaması gereken) iki kurulumda çalıştırılır:

- **HAM** — 2 yerel araç + sunucudaki 28 MCP aracının tamamı (31 araç)
- **FACADE** — 2 yerel araç + 3 sarmalayıcı (5 araç)

Ölçüm adil kurulmuştur: HAM kurulumunda beklenen araç olarak sunucunun **gerçek** araç adları (`search_bedesten_unified`, `search_emsal_detailed_decisions`) kabul edilmiştir. Mevzuat sorularında HAM kurulumun mevzuat aracı bulunmadığı için tek makul seçenek olan `internet_search` doğru sayılmıştır.

### 7.1 Sonuç

| Kurulum | Araç sayısı | İsabet |
|---|---|---|
| HAM | 31 | 9/20 (%45) |
| FACADE | 5 | 16/20 (%80) |
| **Fark** | | **+35 puan** |

### 7.2 Kategori kırılımı

| Soru tipi | HAM | FACADE |
|---|---|---|
| İçtihat (6) | 5/6 | 5/6 |
| Mevzuat (4) | 0/4 | 3/4 |
| **Faiz (4)** | **0/4** | **4/4** |
| Güncel bilgi (2) | 0/2 | 0/2 |
| Araç çağrılmamalı (4) | 4/4 | 4/4 |

**En çarpıcı satır faiz hesabı.** `faiz_hesapla` her iki kurulumda da aynı araç, aynı şema, aynı model. Tek fark yanındaki 28 MCP aracı. HAM kurulumda model kendi yerel aracını dört sorunun hiçbirinde çağıramadı. Araç kalabalığının bağlam maliyeti burada doğrudan görülüyor.

### 7.3 Hata tipi farkı

İki kurulumda hatalar **farklı türden**:

- **HAM:** yanlış araç seçiliyor — `search_btk_decisions` (Bilgi Teknolojileri Kurumu), `search_sayistay_unified` (Sayıştay). İkisi de icra hukukuyla ilgisiz.
- **FACADE:** yanlış araç hiç seçilmiyor; model bazı sorularda araç çağırmadan cevap veriyor.

Yani facade katmanı **ayrım problemini tamamen çözdü**, geriye **tetikleme problemi** kaldı. Bu ikincisi 4B modelin sınırıdır; prompt düzeyinde çözülemedi (bkz. 7.4).

### 7.4 Başarısız deneme: prompt ile tetikleme düzeltmesi

Araç çağırmama hatalarını azaltmak için sistem istemine ek kurallar denendi:

| Sistem istemi | FACADE isabeti |
|---|---|
| Orijinal | 16/20 (%80) |
| + "Güncel bilgi sorulunca MUTLAKA internet_search çağır" (madde 7-8) | 15/20 (%75) |
| + Kural araç seçim tablosunun içine taşındı | 14/20 (%70) |

İyileşme olmadı, aksine küçük bir düşüş görüldü. Değerlendirme: 20 soruluk bir sette 1-2 soruluk oynamalar ölçüm gürültüsü bandındadır, dolayısıyla bu değişikliklerin etkisi **bu ölçekte ayırt edilemez**. Buna karşılık facade katmanının +35 puanlık farkı gürültü bandının çok üzerindedir.

Çıkarım: küçük modellerde kural sayısı arttıkça her kuralın ağırlığı düşüyor. Kural eklemek yerine seçenek azaltmak daha etkili bir kaldıraç.

---

## 8. Örnek Konuşmalar

> `python chat.py --log` çıktısından alınmıştır.

### 8.1 Terim dönüştürme — `ictihat_ara`

```
Siz > Borçlu ödeme emrine itiraz etti ama kötü niyetli olduğunu düşünüyorum.
      Tazminat isteyebilir miyim?

  🔧 ictihat_ara({'konu': 'itirazın iptali kötü niyet tazminatı'})

Asistan > ...
```

Kullanıcı günlük dille sordu, model aramayı hukuki terimle kurdu — sistem istemindeki 2. kuralın çıktısı.

### 8.2 Zincirleme çağrı — `karar_metni_getir`

```
Siz > Bulduğun ilk kararın tam metnini getir.

  🔧 karar_metni_getir({'belge_id': '...'})

Asistan > ...
```

### 8.3 Hesaplama — `faiz_hesapla`

```
Siz > 150.000 TL alacağım var, 15 Mart 2023'ten beri ticari avans faizi
      işliyor. 2.500 TL takip masrafı, 18.000 TL vekalet ücreti var.
      Bugün itibarıyla toplam ne kadar?

  🔧 faiz_hesapla({'asil_alacak': 150000, 'faiz_baslangic': '2023-03-15',
                   'faiz_turu': 'avans', 'takip_masrafi': 2500,
                   'vekalet_ucreti': 18000})
```

Araç çıktısı:

```
FAIZ HESABI (avans faiz, basit faiz, 365 gun esasi)
  Asil alacak      :     150,000.00 TL
  Faiz donemi      : 2023-03-15 - 2026-08-12 (1246 gun)

Donem detayi:
  2023-03-15 - 2024-01-01 |  292 gun | %15.75  |      18,900.00 TL
  2024-01-01 - 2026-08-12 |  954 gun | %48.0   |     188,186.30 TL

  Islemis faiz     :     207,086.30 TL
  Takip masrafi    :       2,500.00 TL
  Vekalet ucreti   :      18,000.00 TL
  TOPLAM ALACAK    :     377,586.30 TL
```

### 8.4 Mevzuat — `mevzuat_ara`

```
Siz > İİK 89 birinci haciz ihbarnamesi ile ilgili kanun metnini getir.

  🔧 mevzuat_ara({'konu': 'İİK 89 birinci haciz ihbarnamesi'})

Asistan > ...
```

### 8.5 Güncel bilgi — `internet_search`

```
Siz > 2026 yılı avukatlık asgari ücret tarifesi yayımlandı mı?

  🔧 internet_search({'query': '2026 avukatlık asgari ücret tarifesi'})

Asistan > ...
```

### 8.6 Sınır testi — araç çağrılmamalı

```
Siz > Bana bir şiir yaz.

Asistan > Bu benim uzmanlık alanım dışında. İcra ve iflas hukuku
          konularında yardımcı olabilirim.
```

---

## 9. Web Arayüzü

```bash
python arayuz.py
```

Gradio tabanlı arayüz `chat.py` ile **aynı** döngüyü kullanır; sistem istemi, facade katmanı ve araç kümesi değişmez. Araç çağrıları cevabın üstünde görünür, böylece hangi kaynağın kullanıldığı izlenebilir.

Open WebUI tercih edilmedi: doğrudan Ollama'ya bağlandığı için araç katmanı, facade ve MCP köprüsü devre dışı kalırdı.

_(Ekran görüntüsü buraya)_

---

## 10. Bilinen Sınırlar ve Sonraki Adımlar

**Sınırlar**

- `tools.FAIZ_ORANLARI` tablosundaki oranlar manuel güncellenir; resmî hesaplama öncesi Resmî Gazete / TCMB oranlarıyla doğrulanmalıdır.
- Faiz hesabı basit faiz ve 365 gün esasına göredir; bileşik faiz kapsam dışıdır.
- Yargı MCP'de mevzuat aracı bulunmadığı için kanun metinleri web araması ve sayfa indirme üzerinden gelir; tam metin garantisi yoktur.
- 4B model, güncel bilgi sorularında araç çağırmayı tetiklemekte zayıf (7.2).
- Ölçüm tek çalıştırmaya dayanıyor; 20 soruluk sette ±%10 bandında oynama beklenmelidir.
- MCP araç adları sunucu sürümüyle değişebilir; `python yargi_mcp.py --list` ile doğrulanmalıdır.
- Asistanın çıktısı hukuki tavsiye değildir.

**Sonraki adımlar**

- Mevzuat için mevzuat.gov.tr'nin arka uç servisine doğrudan bağlanmak (belgelenmemiş, kırılgan).
- Ölçümü 3 tekrarlı çalıştırıp ortalama ve standart sapma raporlamak.
- Daha büyük VRAM'de 8B/12B modellerle aynı ölçümü tekrarlamak.
