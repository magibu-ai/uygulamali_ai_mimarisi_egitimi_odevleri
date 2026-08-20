# 📢 Ödev 5.1 — Yerel LLM Asistanı

**Son tarih:** 13 Ağu 2026 18:59 GMT+3

---

## 🎯 Ödevin Amacı

Yerel (local) bir dil modeli üzerinde, kurgulanan senaryoya uygun **sistem istemini (system prompt)** ve **araç kullanımını (tool calling)** en verimli şekilde optimize ederek çalışan somut bir ürün ortaya koymak.

---

## 🛠️ Gereksinimler

- **Temel Kod Yapısı:** GitHub reposundaki `ollama_asistan` dizini temel alınacak; üzerindeki dosyalar (4-5 dosya) kendi senaryoya göre düzenlenecek.
- **Yerel Model Kullanımı:** Model kendi bilgisayarında **Ollama** veya **LM Studio** üzerinden çalıştırılacak.
- **Model Seçimi:** Serbest. Kriterler: bilgisayarda sorunsuz çalışması, senaryoya hizmet etmesi, **tool calling** yapabilmesi.
- **Sistem İstemi:** Modelin rolü, sınırları ve senaryoya özel kuralları tanımlanıp optimize edilecek.
- **Araç Kullanımı (Tool Calling):**
  - **İnternet Araması:** Kullanıcı sorularını doğru anahtar kelimelere dönüştürüp arama yapan bir araç eklenebilir (Tavily, DuckDuckGo, Yandex veya Google).
  - **Senaryoya Özel Tool:** En az **1 adet** senaryoya özel araç tanımlanacak (zorunlu).
- **Ek / Opsiyonel Araçlar:**
  - Vektör Veri Tabanı / RAG: ChromaDB veya PostgreSQL (PGVector)
  - Harici API / MCP: Hava Durumu, Döviz Kuru API'leri veya harici servisler (ör. Sait Sürücü'nün Yargı MCP'si)
  - Kod Yürütme: Python vb. kod yazdırıp `subprocess` ile çalıştırma / Hesap makinesi (Calculator)
- **Arayüz:** Terminal üzerinden girdi-çıktı yeterli. İsteyen OpenChat UI (veya benzeri hazır şablon) kullanabilir.

---

## 💡 Senaryo Seçimi

Genel amaçlı asistan kurgulanabilir; ya da özel bir senaryo (kişisel planlama, hukuk, finans, sağlık vb.) üzerinden ilerlenebilir.

---

## 📦 Teslim Formatı

1. Proje bir **GitHub reposuna** yüklenip linki paylaşılacak.
2. Reponun **README** dosyasında, lokalde test edilen **örnek konuşmalar** yer alacak (kullanıcı sorusu / asistan cevabı, gerekiyorsa tool call adımlarıyla birlikte).

---

## 📌 Not

En özgün senaryoyu geliştiren kişiye ders içinde oylama ile bir takdir/tebrik sunulabilir.

---

## ✅ Kontrol Listesi

- [ ] Senaryo seçildi ve netleştirildi
- [ ] Yerel model kuruldu (Ollama / LM Studio) ve tool calling test edildi
- [ ] System prompt yazıldı ve optimize edildi
- [ ] İnternet arama aracı eklendi
- [ ] Senaryoya özel en az 1 tool tanımlandı
- [ ] (Opsiyonel) RAG / harici API / kod yürütme araçları
- [ ] Terminal arayüzü çalışıyor
- [ ] README'ye örnek konuşmalar + tool call adımları eklendi
- [ ] GitHub reposu push'landı, link paylaşıldı
