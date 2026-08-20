

# 🚀 Crypto-Agent
### Yapay Zeka Destekli Otonom Kripto Analiz ve Alım-Satım Simülatörü

Crypto-Agent, yerleşik yapay zeka entegrasyonu sayesinde kripto para piyasasını gerçek zamanlı analiz eden ve kullanıcıların sanal cüzdanlarıyla anlık fiyatlar üzerinden işlem (alım-satım) yapmasına olanak tanıyan otonom bir akıllı asistandır.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![Gradio](https://img.shields.io/badge/UI-Gradio-orange.svg)](https://gradio.app)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

**Hızlı Linkler:** [Özellikler](#-özellikler) · [Nasıl Çalışır?](#-nasıl-çalışır) · [Kurulum](#-kurulum) · [Teknoloji Yığını](#-teknoloji-yığını)

---

## ❓ Crypto-Agent Nedir?
Crypto-Agent, açık kaynaklı bir dil modelinin (Qwen 2.5 7B Instruct) dış API'ler ile doğrudan iletişim kurarak işlem yapabilmesini (Tool-Calling) sağlayan gelişmiş bir sanal portföy yönetim sistemidir. Sistem yapay zekanın halüsinasyon (olmayan veriyi uydurma) sorunlarını engellemek adına doğrudan Binance.US üzerinden canlı fiyat verileri alır ve işlemleri anında yerel bir SQLite veritabanına yansıtır.

## ✨ Özellikler
| Özellik | Açıklama |
|---------|-------------|
| 🤖 **Otonom Araç Kullanımı (Tool Calling)** | Yapay zeka kullanıcının isteğini analiz edip hangi fonksiyonu çağıracağına kendi karar verir (Fiyat çekme, Portföy görüntüleme, Alım-Satım). |
| 📊 **Gerçek Zamanlı Fiyatlandırma** | Binance.US API entegrasyonu sayesinde her zaman anlık ve gerçeğe uygun fiyatlar üzerinden işlem yapılır. |
| 💼 **Sanal Cüzdan & Veritabanı** | SQLite tabanlı veritabanı ile kullanıcının sanal cüzdanı ve geçmişi güvenle tutulur (Başlangıç bakiyesi 10.000$). |
| ⚡ **Matematik Hatalarını Önleme** | Dil modellerinin (LLM) matematiksel hatalar yapmasını önlemek için "Dolarlık alım" işlemleri doğrudan arka uçta (Python ile) kusursuz hesaplanır. |
| 🎨 **Temiz & Minimal Arayüz** | Kullanıcı deneyimi odaklı, göz yormayan, son derece sade ve anlaşılır bir Gradio Chat arayüzü sunar. |

## 🧠 Nasıl Çalışır?
Sistem, kullanıcının girdiği metni alır, yapılandırılmış sistem kurallarına göre analiz eder ve otonom bir eyleme dönüştürür.
- **Girdi (Input):** Kullanıcı işlemi belirtir (Örn: "1000 dolarlık BTC al").
- **Analiz (Analysis):** Model cümleyi yorumlar ve `execute_trade` aracını kullanması gerektiğini anlar.
- **Veri Çekme (Data Retrieval):** Model, işlemi onaylamadan önce arka planda Binance'ten anlık BTC fiyatını çeker.
- **Yürütme (Execution):** Kripto miktarı arka planda hatasız hesaplanarak sanal veritabanına işlenir.
- **Sentez (Synthesis):** Model işlemi tamamladığına dair formatlı ve kullanıcı dostu bir özet yanıt oluşturarak kullanıcıya döner.

## 🛠️ Kurulum
Projeyi yerel makinenizde çalıştırmak için aşağıdaki adımları izleyebilirsiniz.

### 1. Depoyu Klonlayın
```bash
git clone https://github.com/MertAlii/Crypto-Agent.git
cd Crypto-Agent
```

### 2. Gerekli Kütüphaneleri Yükleyin
> ⚠️ **Not:** Uygulamanın içerisinde Hugging Face platformuna özel `spaces` modülü kullanılmaktadır. Projeyi yerelde (kendi bilgisayarınızda) çalıştırırken ilgili `spaces` import satırlarını veya `@spaces.GPU` dekoratörlerini yorum satırına almanız gerekebilir.

```bash
pip install -r requirements.txt
```

### 3. Uygulamayı Başlatın
```bash
python app.py
```
Arayüz genellikle `http://127.0.0.1:7860/` adresinde yerel olarak yayınlanacaktır.

## 🏗️ Teknoloji Yığını
| Katman | Teknoloji | Görev |
|-------|------------|------|
| **Kullanıcı Arayüzü (UI)** | Gradio (v5) | Sade ve minimal Chatbot arayüzü |
| **Dil Modeli (LLM)** | Qwen 2.5 7B Instruct | Dili anlama ve otonom araç (tool) seçimi |
| **Veri Sağlayıcı** | Python `requests` | Binance.US API'si ile anlık fiyat okuma |
| **Veritabanı** | SQLite3 | Kullanıcı varlıkları ve portföy durumunun kalıcı olarak saklanması |
| **Sunucu Ortamı** | Hugging Face Spaces | Uygulamanın bulutta canlı olarak (ZeroGPU ile) barındırılması |

---
*Mert Ali tarafından ❤️ ile geliştirildi.*
