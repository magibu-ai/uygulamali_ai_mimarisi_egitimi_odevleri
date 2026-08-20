# 🎓 KampüsGPT

KampüsGPT, üniversite öğrencilerine yardımcı olmak amacıyla geliştirilmiş, **Ollama üzerinde yerel olarak çalışan ve tool calling destekleyen bir yapay zekâ asistanıdır.**

Projenin temel amacı, yerel bir dil modelinin kullanıcı isteğine göre doğru aracı seçmesini sağlamaktır. Asistan; not hesaplama işlemlerinde özel olarak geliştirilen not hesaplama aracını, güncel bilgi veya kaynak gerektiğinde ise internet arama aracını kullanır.

## 🚀 Özellikler

KampüsGPT aşağıdaki yeteneklere sahiptir:

- Üniversite öğrencilerinin basit sorularını cevaplama
- Vize ve final notlarından ders ortalaması hesaplama
- Geçmek için gerekli final notunu hesaplama
- İnternetten güncel bilgi ve kaynak araştırma
- Kullanıcı isteğine göre doğru aracı otomatik seçme
- Araç gerekmeyen sorularda gereksiz tool çağrısından kaçınma
- Tamamen yerel bir dil modeli ile çalışma

## 🤖 Kullanılan Model

Projede Ollama üzerinden aşağıdaki yerel model kullanılmıştır:

```text
gemma4:12b
```

Model bilgisayar üzerinde yerel olarak çalışmaktadır.

## 🛠️ Kullanılan Araçlar

Projede iki adet tool bulunmaktadır.

### 1. grade_calculator

Bu araç projeye özel olarak geliştirilmiştir.

Öğrencinin vize notunu, final notunu, vize-final yüzdelerini ve geçme notunu kullanarak ders ortalamasını veya geçmek için gereken minimum final notunu hesaplar.

Örneğin:

```text
Vize: 60
Vize oranı: %40
Final oranı: %60
Geçme notu: 50

Gerekli final notu: 43.33
```

### 2. internet_search

Bu araç, kullanıcının güncel bilgi veya internet kaynağı istediği durumlarda kullanılır.

Arama işlemi DuckDuckGo üzerinden gerçekleştirilir.

Örneğin kullanıcı:

```text
Python decorator hakkında internetten kaynak bul.
```

şeklinde bir soru sorduğunda model `internet_search` aracını çağırır ve bulunan sonuçlardan yararlanarak kullanıcıya cevap verir.

## 🧠 System Prompt

Modelin hangi durumda hangi aracı kullanacağı system prompt ile kontrol edilmektedir.

Temel kurallar şunlardır:

- Not, vize, final veya ders ortalaması hesaplamalarında `grade_calculator` kullanılır.
- Not hesapları model tarafından tahmin edilmez, araç üzerinden hesaplanır.
- Güncel bilgi veya internet kaynağı gerektiğinde `internet_search` kullanılır.
- Basit veya genel sorularda gereksiz tool çağrısı yapılmaz.
- Selamlaşma gibi mesajlarda araç kullanılmaz.
- Tool tarafından döndürülmeyen bilgiler uydurulmaz.
- Cevaplar Türkçe, kısa ve anlaşılır şekilde verilir.

## 📁 Proje Yapısı

```text
kampusgpt/
│
├── chat.py
├── ollama_client.py
├── tools.py
├── requirements.txt
└── README.md
```

## ⚙️ Kurulum

Öncelikle Ollama'nın bilgisayarda kurulu ve çalışıyor olması gerekmektedir.

Kullanılan modeli kontrol etmek için:

```bash
ollama list
```

Python bağımlılıklarını yüklemek için:

```bash
python3 -m pip install -r requirements.txt
```

## ▶️ Çalıştırma

Program proje klasöründe aşağıdaki komut ile çalıştırılır:

```bash
python3 chat.py
```

Program başladığında:

```text
🎓 KampüsGPT
Model: gemma4:12b
Çıkmak için: cik

Siz >
```

Programdan çıkmak için:

```text
cik
```

yazılabilir.

# 🧪 Örnek Konuşmalar

## Örnek 1 — Geçmek İçin Gereken Final Notu

**Kullanıcı:**

```text
Vizeden 60 aldım. Vize %40 final %60 etkiliyor.
Geçme notu 50. Finalden kaç almam lazım?
```

**Tool Call:**

```text
🔧 grade_calculator({
    'final': None,
    'final_orani': 60,
    'gecme_notu': 50,
    'vize': 60,
    'vize_orani': 40
})
```

**KampüsGPT:**

```text
Vizeden aldığın 60 puanı ve ağırlıkları hesapladığımda,
dersi geçmek için final sınavından en az 43.33 alman gerekiyor.
Başarılar dilerim!
```

---

## Örnek 2 — Farklı Bir Not Senaryosu

**Kullanıcı:**

```text
Vizem 20. Geçme notu 60. Vize %40 final %60.
Finalden kaç almam lazım?
```

**Tool Call:**

```text
🔧 grade_calculator({
    'final': None,
    'final_orani': 60,
    'gecme_notu': 60,
    'vize': 20,
    'vize_orani': 40
})
```

**KampüsGPT:**

```text
Dersi geçebilmek için final sınavından en az 86.67
alman gerekiyor. Başarılar!
```

---

## Örnek 3 — İnternet Araması

**Kullanıcı:**

```text
Python decorator hakkında internetten 3 kaynak bul.
```

**Tool Call:**

```text
🔧 internet_search({
    'query': 'Python decorator kaynaklar'
})
```

**KampüsGPT:**

```text
Python decorator'ları, mevcut bir fonksiyonun veya metodun
davranışını kodunu değiştirmeden genişletmek için kullanılan
yapılardır.

İnternet aramasından bulunan kaynaklar kullanılarak
kullanıcıya ilgili konu hakkında kısa bir açıklama ve
kaynak önerileri sunulur.
```

> Not: İnternet araması sonucunda dönen kaynaklar aramanın yapıldığı zamana göre değişebilir.

---

## Örnek 4 — Tool Gerektirmeyen Soru

**Kullanıcı:**

```text
2+2 kaç?
```

**KampüsGPT:**

```text
2+2=4 eder. Başka bir konuda yardımcı olabilir miyim?
```

Bu örnekte herhangi bir tool çağrısı yapılmamıştır.

## 🔄 Tool Calling Akışı

```text
Kullanıcı Sorusu
       ↓
Yerel Dil Modeli
       ↓
Tool gerekli mi?
    ↙       ↘
  Hayır      Evet
   ↓          ↓
Cevap      Tool Call
              ↓
         Python Fonksiyonu
              ↓
          Tool Sonucu
              ↓
         Yerel Dil Modeli
              ↓
            Cevap
```

## 🎯 Projenin Amacı

Bu projede genel amaçlı büyük bir asistan geliştirmek yerine, küçük ve anlaşılır bir öğrenci asistanı senaryosu seçilmiştir.

Özellikle aşağıdaki konulara odaklanılmıştır:

- Yerel dil modeli kullanımı
- System prompt tasarımı
- Tool calling
- Doğru tool seçimi
- Gereksiz tool kullanımının engellenmesi
- Senaryoya özel Python aracı geliştirilmesi
- İnternet araması entegrasyonu

Sonuç olarak KampüsGPT, kullanıcı isteğini analiz ederek gerekli durumlarda doğru aracı çağırabilen basit bir yerel yapay zekâ asistanı olarak geliştirilmiştir.
