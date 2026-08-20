# Kampus Asistani: LLM Tabanli Otonom Ajan

Bu proje, yerel makinede calisan ve buyuk dil modellerinin dis dunya ile etkilesime girmesini saglayan "Tool Calling"mimarisi uzerine insa edilmis otonom bir kampusu asistanidir. Proje, Gazi Universitesi ogrencilerinin temel kampusu ihtiyaclarina hizli ve dogru yanitlar verebilmesi amaciyla gelistirilmistir.

Sistem, modelin halusinasyon uretmesini engellemek amaciyla katistirici sistem istemleri ile sinirlandirilmis ve yalnizca dis araclardan aldigi dogrulanmis verileri kullanarak yanit uretmek uzere yapilandirilmistir.

## Mimari ve Entegre Araclar

Asistan, kullanicinin niyetini analiz ederek asagidaki araclari otonom olarak cagirabilir ve sonuclari isleyebilir:

1.  **get_daily_menu:** HTML_DOZER mantigiyla kazinmis verileri dondurur. Sistemin veri butunlugunu korumak amaciyla, Firebase sema standartlarina ve `document_id` gibi yapisal alan kistlarina kati bir sekilde uyum saglayan JSON formatinda yanit uretir.
2.  **get_weather:** Open-Meteo API altyapisini kullanarak belirtilen lokasyonun anlik hava durumu, sicaklik, nem ve ruzgar verilerini getirir.
3.  **internet_search:** Akademik takvim, universite duyurulari ve genel aramalar icin DuckDuckGo (Lite) ve alternatif olarak Wikipedia API'sini kullanarak guncel internet verilerini sisteme dahil eder.

## Gereksinimler ve Kurulum

Projenin calisabilmesi icin sisteminizde Python 3.x ve Ollama'nin kurulu olmasi gerekmektedir.

1.  Depoyu yerel bilgisayariniza klonlayin.
2.  Gerekli kutuphanelerin kurulu oldugundan emin olun (Standart `requests` kutuphanesi kullanilmaktadir).
3.  Ollama uzerinden araclari destekleyen (tool-calling) uyumlu modeli indirin:
    `ollama pull llama3.1`

## Kullanim

Uygulamayi baslatmak icin terminal uzerinden asagidaki komutu calistirin:

`python chat.py --chat-model llama3.1`

Sistem basladiktan sonra, asistan komut satirinda kullanici girdilerini bekleyecektir. "Bugun yemekhanede ne var?" veya "Ankara hava durumu nedir?" gibi dogal dil sorgulari ile asistanin ilgili araclari tetiklemesini saglayabilirsiniz.

## Karsilasilan Sorunlar ve Cozumleri

Gelistirme ve test surecinde karsilasilan temel hatalar ve uygulanan cozum adimlari asagida belgelenmistir:

### Hata 1: Baglanti Reddedildi (Connection Error)
*   **Hata Ciktisi:** `Ollama'ya baglanilamadi (http://localhost:11434). Once 'ollama serve' komutunu calistirin...`
*   **Neden:** Ollama HTTP sunucusunun arka planda calismamasi.
*   **Cozum:** Windows uzerinde Ollama uygulamasi manuel olarak baslatilmis veya terminal uzerinden yeni bir sekmede `ollama serve` komutu calistirilarak yerel sunucu ayaga kaldirilmistir.

### Hata 2: Modelin Arac Kullanimi (Tool Calling) Desteklememesi
*   **Hata Ciktisi:** `Ollama hatasi (400): {"error":"registry.ollama.ai/library/llama3:latest does not support tools"}`
*   **Neden:** Baslangicta kullanilan standart `llama3` modelinin, yerlesik bir arac cagirma yetenegine sahip olmamasi. Model, disaridan gonderilen fonksiyon semalarini isleyemedigi icin HTTP 400 hatasi dondurmustur.
*   **Cozum:** Meta tarafindan ozel olarak arac kullanimi icin optimize edilmis olan `llama3.1` modeli `ollama pull llama3.1` komutu ile sisteme indirilmis ve baslatma komutu `--chat-model llama3.1` parametresi ile guncellenerek sorun giderilmistir.


## Örnek Kullanım ve Test Logları

Sistemin yerel makinede çalıştırıldığı ve kullanıcının girdisine göre araçlarınotonom olarak tetiklendiği örnek bir terminal oturumu aşağıdadır:

```text
PS C:\Users\kampus_asistani> python chat.py --chat-model llama3.1
🎓 Kampüs / Yemekhane Asistanı Başlatıldı
  Sohbet Modeli : llama3.1
  Çıkmak için   : cik

Öğrenci > Bugün yemekhanede ne var?
  ⚙️ Çalıştırılıyor: get_daily_menu({'date_str': '2023-12-01'})

Asistan > Yemekhane menüsünde Ezogelin Çorbası, İzmir Köfte ve Şehriyeli Pirinç Pilavı gibi lezzetler var. Cacık ve mevsim meyvesi de ekstra olarak sunuluyor. Kalori değeri 1050 kcal.
