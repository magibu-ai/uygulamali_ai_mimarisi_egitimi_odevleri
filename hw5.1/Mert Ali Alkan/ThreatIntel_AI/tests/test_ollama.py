import sys
import traceback
import ollama_client
import tools
from chat import SYSTEM_PROMPT

report_prompt = """Aşağıda analiz edilen şüpheli e-posta ve OSINT araçlarının sonuçları yer almaktadır:

--- E-POSTA ---
merhaba

--- ARAÇ SONUÇLARI ---
HİÇBİR ARAÇ KULLANILMADI (Sistem Hatası veya Model Araç Kullanmayı Reddetti).

--- HESAPLANAN RİSK SKORU ---
Hesaplanamadı (Araç çağrılmadığı için).

GÖREV: Yukarıdaki bilgileri harmanlayarak, daha önce belirtilen RAPOR FORMATI'na (Karar, Risk Skoru, Önemli Bulgular vb.) tam uygun bir şekilde nihai raporu oluştur. Risk skorunu hesaplanan skor olarak yaz. Sadece rapor metnini üret."""

msg = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": report_prompt}]
try:
    res = ollama_client.chat(msg, tools=None)
    print("SUCCESS")
    print(res)
except Exception as e:
    print("ERROR")
    traceback.print_exc()
