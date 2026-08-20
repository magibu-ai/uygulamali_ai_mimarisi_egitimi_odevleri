---
title: Kargo Kurye Asistani
emoji: 💻
colorFrom: gray
colorTo: red
sdk: gradio
sdk_version: 6.22.0
python_version: '3.12'
app_file: app.py
pinned: false
license: mit
---

# * Akıllı Kargo ve Kurye Asistanı

Bu proje, bir Büyük Dil Modelinin dış dünyaya (gerçek bir SQLite veritabanına) erişip, hem veri okuyabildiği hem de yeni kayıt yazabildiği uçtan uca çalışan bir asistan uygulamasıdır. 

## * Senaryo Özeti
Bir kargo şirketinin otonom müşteri hizmetleri botu tasarlanmıştır. Modelin halüsinasyon yapmasını engellemek için katı sistem kuralları konmuş ve cevapların doğrudan veritabanından gelen yanıtlara dayanması sağlanmıştır.
- **Kargo Sorgulama (READ):** Kullanıcı "KRG123" gibi bir takip numarası verdiğinde, asistan `kargo_sorgula` aracını tetikler, veritabanını tarar ve kargonun güncel durumunu söyler.
- **Kurye Talep Etme (WRITE):** Kullanıcı kurye istediğinde, asistan `kurye_talep_et` aracını çalıştırarak kullanıcının verilerini veritabanına yeni bir sipariş olarak kaydeder ve üretilen dinamik takip numarasını kullanıcıya sunar.

## * Model ve Mimari Bilgisi
- **Kullanılan Model:** `meta-llama/Llama-3.3-70B-Instruct` (Hugging Face API üzerinden)
- **Veritabanı:** `SQLite` (Dahili, yerel dosya tabanlı kargo.db)
- **Arayüz:** `Gradio` (Sistem loglarının izlenebildiği yer)

## * Projeyi Yerelde Çalıştırma Adımları
1. Projeyi bilgisayarınıza indirin.
2. Gerekli kütüphaneleri yükleyin: `pip install -r requirements.txt`
3. Terminalde/CMD'de ortam değişkeni olarak Hugging Face token'ınızı ayarlayın.
   - Windows: `set HF_TOKEN=sizin_token_degeriniz`
   - Mac/Linux: `export HF_TOKEN="sizin_token_degeriniz"`
4. Uygulamayı başlatın: `python app.py`
5. Tarayıcınızda `http://127.0.0.1:7860` adresine giderek asistanı kullanmaya başlayın.

## * Canlı Demo Bağlantısı
Uygulamanın bulut üzerinde çalışan canlı versiyonunu Hugging Face Spaces üzerinden deneyimleyebilirsiniz:
**(https://huggingface.co/spaces/Egertekin/kargo-kurye-asistani)**

## * Sistem Logları ve Tool-Call Örneği
Aşağıdaki örnekte, modelin kullanıcıdan aldığı bilgilerle nasıl veritabanı kaydı oluşturduğunu (WRITE işlemi) görebilirsiniz:

![Ekran görüntüsü 2026-07-31 230901](https://cdn-uploads.huggingface.co/production/uploads/6a22efc141d82ed47a0d8f35/zW4dH628dP870BqxqY_5W.png)
