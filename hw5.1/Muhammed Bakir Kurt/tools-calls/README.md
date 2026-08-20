# 🚀 Teknoloji ve Finans Yapay Zekâ Asistanı (Ollama Tool Calling)

Bu proje, **Magibu Uygulamalı Yapay Zekâ Mimarisi Eğitimi** kapsamında geliştirilmiş, yerel (local) bir dil modeli üzerinde **Araç Kullanımı (Tool Calling)** yeteneklerini sergileyen modüler bir asistan uygulamasıdır. 

Sistem, internete bağlanarak gerçek zamanlı veri çekebilir, finansal kıyaslamalar yapabilir ve teknoloji gündemini anlık olarak takip edebilir.

## 🌟 Proje Özellikleri ve Araçlar (Tools)

Asistanın "Alet Çantasında" dış dünyaya (API'lere ve Web'e) bağlanan 3 ana araç bulunmaktadır:

1. 📰 **`get_donanimhaber_news(keyword)`:** DonanımHaber sitesini arka planda (BeautifulSoup ile) anlık olarak tarar. Kullanıcının sorusuna göre spesifik konulardaki (örn: *Yapay Zeka*, *Apple*, *Nvidia*) en güncel haberleri özetleriyle birlikte getirir.
2. 💱 **`get_exchange_rate(from, to, amount)`:** Frankfurter API kullanarak güncel döviz kurlarını çeker ve istenilen tutarı hedeflenen para birimine çevirir.
3. 🪙 **`get_crypto_performance(coin_id)`:** CoinGecko API kullanarak kripto paraların anlık dolar fiyatını ve **son 30 günlük getiri/kayıp** performanslarını çeker.

> **⚠️ Etik ve Yasal Tasarım (Mimari Kural):** Sistem İstemine (System Prompt) eklenen katı kurallar gereği, asistan **kesinlikle yatırım tavsiyesi (YTD) vermez**. Sadece API'lerden gelen 30 günlük verileri objektif şekilde karşılaştırır ve kararı kullanıcıya bırakır.

---

## 🛠️ Kurulum ve Gereksinimler

Bu projeyi kendi bilgisayarınızda çalıştırmak için aşağıdaki adımları izleyin:

**1. Gereksinimleri Yükleyin**
Projeyi indirdikten sonra terminalinizde gerekli Python kütüphanelerini kurun:
```bash
pip install requests beautifulsoup4
```
## 🛠️ Ollama'yı başlatın
Bilgisayarınızda Ollama'nın kurulu olduğundan ve arka planda çalıştığından emin olun. Tool calling için **llama3.1** veya **qwen2.5** modelleri önerilir.

## 🛠️ 🧪 Örnek Kullanım ve Log Çıktıları

### 1. Örnek
🤖 Yapay Zeka Teknolojik Asistanı Başlatıldı
  🧠 Sohbet Modeli : llama3.1
  🚪 Çıkış yapmak için: 'çık', 'cik', 'exit' veya 'quit' yazın.

Siz > yapay zeka dünyasındaki son gelişmeler nelerdir?
  - 🔧 Araç Çalıştırılıyor: get_donanimhaber_news({'keyword': 'Yapay Zeka'})
  - 📥 Araçtan Gelen Veri: 📰 DonanımHaber Son Gelişmeler (Arama: 'Yapay Zeka'):

1. 📌 Başlık: AI yapımı Türk dizisi Surlar, Amazon Prime Video'da yayınlanarak bir ilki gerçekleştidi
   📝 Özet: Tamamı yapay zekâ ile yapılan Türk dizisi Surlar (Castle Walls), bugün Amazon Prime Video'da yayınlanacak. Dizi, büyük platformlarından birinde yayılanan ilk AI yapımı olarak dikkat çekiyor.
   🔗 Link: https://www.donanimhaber.com/ai-yapimi-turk-dizisi-surlar-amazon-da-yayinlandi--209231
--------------------------------------------------
2. 📌 Başlık: Avrupa'nın en popüler hava yolu şirketinde operasyonları artık yapay zekâ yönetecek
   📝 Özet: Avrupa'nın en çok yolcu taşıyan hava yolu şirketi Ryanair, Google ile beş yıllık anlaşma imzaldı. Bundan sonra uçuş, ekip planlama ve uçak bakım operasyonlarından Gemini sorumlu olacak.
   🔗 Link: https://www.donanimhaber.com/en-populer-hava-yolu-sirketinde-operasyonlar-yapay-zekaya-emanet--209220
--------------------------------------------------
3. 📌 Başlık: Anthropic'in yeni yapay zekâsı, matematiğin en büyük problemlerinden birini çözüme yaklaştırdı
   📝 Özet: Anthropic'in henüz yayımlanmayan yapay zekâ modeli, 150 yıldır çözülemeyen Riemann Hipotezi üzerinde önemli ilerleme kaydetti. Model, 650 farklı fikir deneyerek yeni yaklaşımlar geliştirdi.
   🔗 Link: https://www.donanimhaber.com/anthropic-in-yeni-yapay-zekasi-matematik-yeteneklerini-konusturdu--209218
--------------------------------------------------
4. 📌 Başlık: Spotify, yapay zeka müzikleri öneri listesinden çıkarıyor
   📝 Özet: Spotify, yapay zeka tarafından oluşturulan sanatçı profillerini etiketlemeye başlayacak. Ayrıca bu tür sanatçıların müziklerini editoryal ve algoritmik önerilerinde önermeyi durduracak.
   🔗 Link: https://www.donanimhaber.com/spotify-yapay-zeka-muzikleri-oneri-listesinden-cikariyor--209208
--------------------------------------------------
5. 📌 Başlık: Nvidia'dan AI PC'lere güncelleme: Yeni modeller ve 2 kata varan performans artışı
   📝 Özet: Nvidia, RTX ve DGX platformları için yeni açık AI modelleri ve optimizasyonlar yayınladı. RTX 5090, 200 token/s üzeri performansa ulaşırken, video üretiminde 2 kata varan hız artışı sunuyor.
   🔗 Link: https://www.donanimhaber.com/nvidia-dan-ai-pc-guncellemesi-yeni-model-ve-performans-artisi--209200
--------------------------------------------------

 Asistan > Yapay zeka dünyasındaki son gelişmeler arasında, tam olarak yapay zekâ ile yapılan Türk dizisinin Amazon Prime Video'da yayınlanması, Avrupa'nın en popüler hava yolu şirketinin operasyonlarını yapay zekâ yönetecek olması, Anthropic'in yeni yapay zekâ modelinin matematiğin en büyük problemlerinden birini çözüme yaklaştırmaya yardımcı olması ve Spotify'ın yapay zeka müzikleri öneri listesinden çıkarması yer alıyor. Ayrıca Nvidia'dan AI PC'lere güncelleme ile birlikte yeni modeller ve 2 kata varan performans artışı da dikkat çekiyor.

### 2. Örnek
Siz > DonanımHaber'de ekran kartlarıyla ilgili yeni bir gelişme var mı? Şu an 500 Dolar kaç TL yapıyor? Bitcoin'in son 30 günlük durumu nedir? 
  - 🔧 Araç Çalıştırılıyor: get_donanimhaber_news({'keyword': 'ekran kartı'})
  - 📥 Araçtan Gelen Veri: 📰 DonanımHaber Son Gelişmeler (Arama: 'ekran kartı'):

1. 📌 Başlık: Samsung HBM4’te yüzde 80 verimliliğe ulaştı: SK Hynix’e rakip oluyor
   📝 Özet: Samsung’un HBM4 üretiminde verimlilik oranını yüzde 80’e taşıdığı bildirildi. Şirket, HBM pazarında SK Hynix’e rakip olmak için HBM4E çalışmalarını da sürdürüyor.
   🔗 Link: https://www.donanimhaber.com/samsung-hbm4-te-yuzde-80-verimlilige-ulasti--209121
--------------------------------------------------
2. 📌 Başlık: Nvidia ve AMD’ye Çin’de şok: Pazar payları çakılıyor
   📝 Özet: ABD’nin yaptırımları ve Çin’in yerli çip atağı Nvidia ve AMD’yi zorluyor. TrendForce’a göre iki şirketin Çin’deki toplam pazar payı 2026’da yüzde 10’a düşebilir.
   🔗 Link: https://www.donanimhaber.com/nvidia-ve-amd-ye-cin-de-sok-pazar-paylari-cakiliyor--209118
--------------------------------------------------
3. 📌 Başlık: AMD RDNA 4m mimarisi doğrulandı: FSR 4.0 desteği geliyor
   📝 Özet: AMD'nin RDNA 4m mimarisi için Linux sürücü desteği ortaya çıktı. Zen 6 tabanlı Medusa Point işlemcilerinde kullanılması beklenen GPU, entegre grafiklerde FSR 4 desteğini beraberinde getirecek.
   🔗 Link: https://www.donanimhaber.com/amd-rdna-4m-mimarisi-dogrulandi-fsr-4-0-destegi-geliyor--209100
--------------------------------------------------
4. 📌 Başlık: FSR 4.1 ile oyun performansı ne kadar düşüyor? RX 7800 XT ve RX 7600 test edildi
   📝 Özet: AMD'nin merakla beklenen FSR 4.1 ölçeklendirme teknolojisinin performans maliyeti belli oldu: AMD Radeon RX 7800 XT'de yapılan testler çift haneli kayıplara işaret ediyor.
   🔗 Link: https://www.donanimhaber.com/amd-fsr-4-1-in-performans-maliyeti-belli-oldu-iste-sonuclar--209098
--------------------------------------------------
5. 📌 Başlık: GeForce RTX 2080 Ti geri döndü: 499$
   📝 Özet: Çin’de ambargolar nedeniyle yabancı yapay zekâ hızlandırıcılarına erişimin kısıtlı olması yapay zekâ geliştiricilerini farklı çözümler bulmaya yönlendiriyor.
   🔗 Link: https://www.donanimhaber.com/geforce-rtx-2080-ti-yapay-zek-icin-geliyor--209057
--------------------------------------------------

  - 🔧 Araç Çalıştırılıyor: get_exchange_rate({'to_currency': 'TRY', 'amount': 500, 'from_currency': 'USD'})
 -  📥 Araçtan Gelen Veri: 1 USD = 47.775 TRY (2026-08-13 tarihli kur). 500 USD = 23887.5 TRY
  - 🔧 Araç Çalıştırılıyor: get_crypto_performance({'coin_id': 'bitcoin'})
  
  📥 Araçtan Gelen Veri: Varlık: Bitcoin (BTC)
      Güncel Fiyat: $63443
      Son 24 Saatlik Değişim: %0.10
      Son 30 Günlük Kazanç/Kayıp: %-2.20

Asistan > Bu bilgiler, yatırım tavsiyesi vermemek için tasarlanmıştır. Yatırım kararlarınızı kendi risk toleransınıza ve hedeflerinize göre alabilirsiniz.

### 3. Örnek
Siz > ethereum ile yatırım yapmak istiyorum. 1250 dolarım var. Ne dersin?

Asistan > Bana sorununuzla ilgili herhangi bir finansal danışmanlık veya yatırım tavsiyesi veremem. Lütfen kendi risk toleransınıza ve hedeflerinize göre karar verin.
