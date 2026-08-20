# Polen Takibi Asistanı

- Herhangi bir şehir için Kızılağaç, Huş, Çim, Pelin, Zeytin ve Kanaryaotu polenlerinin seviyesini döndürüyor.

Not: Çok uğraştım ama sondaki çıktıları engelleyemedim maalesef.

- Model olarak Qwen 2.5 kullanılıyor.
- Polen seviyelerini Open Meteo'dan çekiliyor.
- Sadece Tool Calling var RAG'e hiç girmedim.

# Örnek Diyalog

Siz > Ankara'daki polen durumu nedir?
  🔧 get_pollen_status({'city': 'Ankara'})

Asistan > Ankara'daki polen durumu şu şekildedir:
- Kızılağaç Poleni: Düşük seviye
- Huş Poleni: Düşük seviye
- Çim Poleni: Orta seviye
- Pelin Poleni: Düşük seviye
- Zeytin Poleni: Düşük seviye
- Kanaryaotu Poleni: Düşük seviye