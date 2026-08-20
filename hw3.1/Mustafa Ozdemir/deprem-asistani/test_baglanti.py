import os
from groq import Groq

# 1) Anahtarı ortam değişkeninden OKU (koda yazmıyoruz!)
api_key = os.environ.get("GROQ_API_KEY")

# 2) Güvenlik kontrolü: anahtar tanımlı değilse uyar
if not api_key:
    print("HATA: GROQ_API_KEY tanımlı değil. Önce 'export GROQ_API_KEY=...' çalıştır.")
    exit()

# 3) Groq istemcisini oluştur — modele konuşma "telefonumuz"
client = Groq(api_key=api_key)

# 4) Modele ilk mesajımızı gönder
cevap = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "user", "content": "Merhaba! Tek cümleyle kendini tanıt."}
    ],
)

# 5) Modelin cevabını ekrana yazdır
print(cevap.choices[0].message.content)