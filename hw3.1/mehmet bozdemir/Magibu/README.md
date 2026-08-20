# 🌤️ Function Calling / Tool Calling Agent (Open-Meteo Weather)

Bu klasör, **Qwen3.5-9B** dil modelinin dış veri kaynakları ve yardımcı fonksiyonlarla etkileşime girerek (**Tool Calling / Agentic Workflow**) çok adımlı soruları yanıtlama uygulamasını içerir.

## 🛠️ Tanımlanan Araçlar (Tools)
1. **`get_weather`**: Open-Meteo Public API üzerinden canlı hava sıcaklığını (°C) getirir.
2. **`convert_temperature`**: Celsius olarak alınan sıcaklık değerini Fahrenheit (°F) birimine dönüştürür.

## 📌 Canlı Demo (Hugging Face Space)
Uygulamanın çalışan canlı demosuna aşağıdaki bağlantıdan erişebilirsiniz:
👉 **[Hugging Face Space Canlı Demo](https://huggingface.co/spaces/nypgd/open-meteo-tool-calling-agent)**

## 📂 Dosya Yapısı
- `app.py`: Gradio arayüzü, Tool şemaları ve Multi-turn Agent döngüsü.
- `requirements.txt`: Gerekli Python kütüphaneleri listesi.
- `README.md`: Ödev ve proje açıklama dokümanı.