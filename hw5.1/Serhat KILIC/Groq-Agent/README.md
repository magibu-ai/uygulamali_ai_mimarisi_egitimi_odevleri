# AI Agent - Yapay Zeka Asistanı

Groq API (`openai/gpt-oss-120b`), Exa AI ve Open-Meteo entegrasyonları ile geliştirilmiş, **Araç Kullanımı (Tool/Function Calling)** yeteneğine sahip interaktif bir Python yapay zeka asistanı.

```text
 ███  ████   ███   ███      ███   ███  █████ █   ██████
█     █   █ █   █ █   █    █   █ █     █     ██  █   █
█  ██ ████  █   █ █   █    █████ █  ██ ████  █ █ █   █
█   █ █  █  █   █ █  █     █   █ █   █ █     █  ██   █
 ███  █   █  ███   ██ █    █   █  ███  █████ █   █   █
```

---

## Özellikler

Bu asistan, kullanıcının sorduğu soruları analiz ederek ihtiyaç duyduğu araçları dinamik olarak seçer ve kullanır:

- **Güncel Hava Durumu (`get_weather`)**: Open-Meteo Geocoding ve Weather API servislerini kullanarak istenen şehrin enlem/boylam bilgilerini bulur, anlık sıcaklık, nem ve rüzgar hızını getirir.
- **Canlı İnternet Araması (`internet_search`)**: Exa AI altyapısını kullanarak güncel haberler, döviz kurları ve canlı veriler için web araması gerçekleştirir.
- **Kod Üretme ve Çalıştırma (`execute_code`)**: Matematiksel hesaplamalar, algoritmalar veya veri işleme görevleri için Python kodu üretir. Üretilen kod **kullanıcı onayından sonra (E/H)** geçici bir dosyada güvenli bir şekilde çalıştırılır ve çıktısı asistana aktarılır.

---

##  Proje Yapısı

```bash
agent/
├── agent.py         # Ana ajan döngüsü, Groq API entegrasyonu ve Sistem Prompt'u
├── tools.py         # Ajanın kullandığı fonksiyonlar (Hava durumu, Web araması, Kod çalıştırma)
├── .env             # API anahtarlarının tutulduğu gizli çevre değişkenleri
└── README.md        # Proje dokümantasyonu
```

---

## Kurulum

1. **Gereksinimler:**
   - Python 3.8 veya üzeri

2. **Gerekli Kütüphanelerin Yüklenmesi:**
   Terminal veya komut istemcisinde aşağıdaki komutu çalıştırarak bağımlılıkları yükleyin:

   ```bash
   pip install groq python-dotenv requests exa-py
   ```

3. **Çevre Değişkenlerinin Yapılandırılması:**
   Proje ana dizininde bir `.env` dosyası oluşturun (veya var olanı düzenleyin) ve API anahtarlarınızı ekleyin:

   ```env
   GROQ_API_KEY="groq_api_anahtariniz"
   EXA_API_KEY="exa_api_anahtariniz"
   ```

---

## Kullanım

Asistanı başlatmak için terminalde aşağıdaki komutu çalıştırın:

```bash
python agent.py
```

### Örnek Kullanım Senaryoları:

1. **Hava Durumu Sorma:**
   > **Kullanıcı:** İstanbul'da hava bugün nasıl?
   > 
   > *(Asistan `get_weather` aracını çağırır ve anlık hava durumunu sunar.)*

2. **İnternet Araması:**
   > **Kullanıcı:** Güncel teknoloji haberlerini ara.
   > 
   > *(Asistan `internet_search` aracını çalıştırarak Exa üzerinden sonuçları derler.)*

3. **Kod Çalıştırma:**
   > **Kullanıcı:** Fibonacci dizisinin ilk 10 elemanını hesaplayan bir Python kodu yaz ve çalıştır.
   > 
   > *(Asistan kodu üretir, onayınızı ister ve onay verdiğinizde çıktıyı gösterir.)*

4. **Çıkış:**
   Sohbetten ayrılmak için `exit`, `quit`, `çıkış`, `q` veya `çık` yazabilirsiniz.

---