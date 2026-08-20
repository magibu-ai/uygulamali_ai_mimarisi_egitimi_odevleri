---
title: X Twitter Research Agent
emoji: 🔎
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 4.44.1
app_file: app.py
python_version: "3.12"
pinned: false
---

# X/Twitter Research Agent

OpenRouter tool calling, Xquik'in salt-okunur REST API'si ve PostgreSQL kullanan,
kanıta dayalı bir X/Twitter araştırma asistanı.

- Kaynak kod: https://github.com/berkbirkan/x-twitter-research-agent
- Hugging Face Space: https://huggingface.co/spaces/berkbirkan/x-twitter-research-agent

Kullanıcı doğal dilde marka, ürün veya özel bir araştırma sorusu sorar. Agent
arama stratejisini ve X sorgularını kendisi belirler; gerçek gönderileri Xquik
üzerinden getirir, kaynakları PostgreSQL'e tool-call ile kaydeder ve yalnızca
doğrulanmış gönderi kimliklerine dayanan yapılandırılmış bir rapor üretir.

> Xquik bağımsız bir üçüncü taraf hizmetidir ve X Corp. ile bağlantılı değildir.
> Kullanıcı kendi OpenRouter ve Xquik API anahtarlarını kullanır.

## Özellikler

- OpenRouter'dan dinamik, yalnızca tool-calling destekli model listesi
- Structured output destekli modeller için belirgin rozet
- Xquik `GET /x/tweets/search` ve `GET /x/tweets/{id}` entegrasyonu
- X üzerinde yazma işlemlerini engelleyen endpoint allowlist'i
- Agentın kendi karar verdiği çok adımlı arama akışı
- Kullanıcı tanımlı 10–200 gönderi bütçesi; varsayılan 50
- PostgreSQL okuma ve yazma işlemlerinin model tool-call'larıyla yapılması
- Kaynak ID doğrulamasıyla halüsinasyon engelleme
- Çok turlu araştırma ve rapor sürümleri
- Anonim oturum, hash'lenmiş erişim kodu ve yedi günlük saklama
- Canlı ve temizlenmiş tool-call günlüğü
- Markdown ve JSON rapor çıktısı
- Gradio ve Hugging Face Spaces desteği

## Mimari

```text
Kullanıcı / Gradio
        │
        ▼
Özel Python agent döngüsü ─────► OpenRouter
        │                         tool_calls
        ├── search_x_posts ─────► Xquik REST API (GET-only)
        ├── get_x_post ─────────► Xquik REST API (GET-only)
        │
        ├── save_search_results ─┐
        ├── finalize_research ───┤
        ├── get_saved_research ──┼──► PostgreSQL / Neon
        ├── list_session_research┤
        └── delete_research ─────┘
```

Model serbest SQL çalıştıramaz. Model tool seçer; backend Pydantic şemalarını,
oturum yetkisini, bütçeyi ve kaynak kimliklerini deterministik olarak doğrular.

## Tool'lar

| Tool | Kaynak | İşlem |
|---|---|---|
| `search_x_posts` | Xquik | Herkese açık gönderi arama |
| `get_x_post` | Xquik | Tek gönderi okuma |
| `save_search_results` | PostgreSQL | Değiştirilmemiş API sonucunu kaydetme |
| `finalize_research` | PostgreSQL | Doğrulanmış rapor sürümü yazma |
| `get_saved_research` | PostgreSQL | ID ve erişim koduyla araştırma okuma |
| `list_session_research` | PostgreSQL | Anonim oturum geçmişini okuma |
| `delete_research` | PostgreSQL | Açık onaydan sonra araştırma silme |

## Halüsinasyon kontrolleri

1. Xquik sonucu geçici ve tahmin edilemez bir `search_call_id` alır.
2. Model kullanacağı sonuçları `save_search_results` ile kaydetmek zorundadır.
3. Tool, modelin geri yazdığı metni değil geçici bellekteki özgün API verisini kaydeder.
4. `finalize_research`, bütün tema ve kanıt tweet ID'lerini kaydedilmiş kayıtlarla karşılaştırır.
5. Bilinmeyen bir ID varsa transaction reddedilir ve rapor gösterilmez.
6. Tweet metni güvenilmeyen veri kabul edilir; tweet içindeki talimatlar uygulanmaz.

Duygu değerlendirmesi ayrı bir deterministik algoritma değildir. Agent, kullanıcının
özel sorusu ve gerçek gönderiler bağlamında değerlendirme yapar; rapor bunu yorum
olarak sunar ve belirsizlikleri belirtir.

## Yerel kurulum

Gereksinimler: Python 3.9+ ve Docker.

```bash
git clone https://github.com/berkbirkan/x-twitter-research-agent.git
cd x-twitter-research-agent
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
docker compose up -d postgres
alembic upgrade head
python app.py
```

Arayüz: `http://localhost:7860`

Son kullanıcı OpenRouter ve Xquik anahtarlarını arayüzde parola alanlarına girer.
Bu anahtarlar PostgreSQL'e, `.env` dosyasına veya tool loglarına yazılmaz.

## Neon ve Hugging Face Space

1. Neon'da bir PostgreSQL veritabanı oluşturun.
2. Neon bağlantı adresini psycopg biçimine getirin:

   ```text
   postgresql+psycopg://USER:PASSWORD@HOST/DATABASE?sslmode=require
   ```

3. Migration'ı bağlantı adresiyle bir kez çalıştırın:

   ```bash
   DATABASE_URL="..." alembic upgrade head
   ```

4. Hugging Face Space ayarlarında `DATABASE_URL` adında Secret oluşturun.
5. OpenRouter veya Xquik anahtarını Space Secret olarak eklemeyin; bunları her
   son kullanıcı kendi oturumunda girer.

Uygulama bağlantı adresini kullanıcı arayüzüne göndermez. Neon uygulamaya özel
olsa da kod standart PostgreSQL `DATABASE_URL` ile başka sağlayıcılarda çalışır.

## Örnek akış

Kullanıcı girdisi:

```text
Son bir haftada OpenRouter hakkındaki fiyat şikâyetlerini araştır ve en sık
tekrarlanan sorunları gerçek gönderilerle göster.
```

Temizlenmiş tool günlüğü:

```text
✓ 1. search_x_posts · 24 benzersiz herkese açık gönderi döndü
✓ 2. save_search_results · 24 gönderi kaydedildi
✓ 3. search_x_posts · 17 benzersiz herkese açık gönderi döndü
✓ 4. save_search_results · 17 gönderi kaydedildi
✓ 5. finalize_research · Araştırma raporu v1 kaydedildi

Bütçe: 41/50 benzersiz gönderi
Xquik aramaları: 2
```

Tool paneli API anahtarlarını, authorization header'larını ve modelin gizli
reasoning içeriğini göstermez.

## Örnek çıktı

Aşağıdaki ekran görüntüsü, “son bir haftadaki yapay zeka ile ilgili Türkçe
gönderileri araştır” sorusu için tamamlanan uçtan uca bir çalışmayı; model
seçimini, kanıta dayalı raporu ve arka planda gerçekleşen tool-call günlüğünü
gösterir.

<img src="https://huggingface.co/spaces/berkbirkan/x-twitter-research-agent/resolve/main/assets/screenshot.png" alt="X/Twitter Research Agent örnek araştırma ekranı ve tool-call günlüğü" width="900">

Oluşturulan raporlar iki farklı biçimde incelenebilir:

- [Markdown örnek raporu](assets/thr-dwsjntjgdwqeb9zkynruea-v1.md)
- [JSON örnek raporu](assets/thr-dwsjntjgdwqeb9zkynruea-v1.json)

## Testler

```bash
pytest
ruff check .
```

Testler model kataloğu filtresini, Xquik sorgu sınırlarını, secret maskelemesini,
erişim kodunu, PostgreSQL kaynak doğrulamasını ve salt-okunur tool yüzeyini kapsar.

## Veri saklama

- Gönderi metni ve gerekli metadata son etkinlikten itibaren yedi gün saklanır.
- Medya dosyaları, profilin tamamı ve ham Xquik cevabı saklanmaz.
- Kullanıcı açık onayla araştırmasını daha erken silebilir.
- Süresi dolmuş araştırmalar bakım temizliğiyle silinir.

## Sınırlar

- En fazla 8 agent adımı ve 6 Xquik araması
- Arama başına en fazla 50, araştırma başına en fazla 200 benzersiz gönderi
- Xquik kredi, kota ve erişilebilirlik sınırları geçerlidir
- X üzerindeki içerikler eksik, silinmiş veya temsili olmayan bir örneklem olabilir
- Agent raporu araştırma yardımıdır; duygu değerlendirmeleri nesnel ölçüm değildir

## Lisans

MIT
