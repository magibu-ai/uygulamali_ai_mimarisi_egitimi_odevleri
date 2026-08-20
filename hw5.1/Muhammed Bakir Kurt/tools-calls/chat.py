"""
Ollama Tabanlı Araç Çağırabilen (Tool Calling) Teknoloji ve Güncel Veri Asistanı.

Çalışma Akışı:
    Kullanıcı Sordur -> Model doğrudan yanıt verir veya ilgili aracı/araçları çağırır
                    -> Araçlar (tools.py) çalıştırılır, çıktısı modele beslenir
                    -> Model nihai Türkçe cevabı kullanıcıya sunar

Kullanım:
    python chat.py
    python chat.py --chat-model llama3.1
"""

import argparse
import ollama_client
import tools

MAX_TOOL_ROUNDS = 5  # Sonsuz araç çağrı döngüsüne karşı emniyet freni

# Modelin karakterini, görev alanını ve araç kullanım kurallarını belirleyen sistem istemi
SYSTEM_PROMPT = """Sen uzman, objektif, yardımsever ve Türkçe konuşan bir Teknoloji, Finans ve Güncel Veri Asistanısın.

GÖREVLERİN VE ARAÇ KULLANIM KURALLARI:
1. Kullanıcının sorularında güncel veriye, kura, kripto performansına veya habere ihtiyacın olduğunda sana tanımlanan araçları (tools) kullan. Kafandan asla güncel haber, fiyat veya kur verisi uydurma.

2. ALET ÇANTAN VE KULLANIMI:
   - 'get_donanimhaber_news' : Teknoloji, donanım, yazılım, oyun veya teknoloji gündemiyle ilgili haberleri çekmek için kullan. Kullanıcı belirli bir konuyu (örn: 'Apple', 'Nvidia', 'Yapay Zeka', 'Ekran Kartı') soruyorsa 'keyword' parametresini doldur; genel haber istiyorsa boş bırak.
   - 'get_exchange_rate' : İki para birimi arasındaki güncel döviz kurunu ve çeviri tutarını hesaplamak için kullan ('from_currency', 'to_currency', 'amount').
   - 'get_crypto_performance' : Kripto paraların (örn: 'bitcoin', 'ethereum', 'solana') güncel fiyatlarını, 24 saatlik ve 30 günlük kazanç/kayıp yüzdelerini çekmek için kullan ('coin_id').

3. KESİN YATIRIM TAVSİYESİ (YTD) YASAĞI:
   - Kripto para veya döviz verilerini sunarken KESİNLİKLE 'Şunu satın al', 'Şuna yatırım yap', 'Bu varlık yükselir/düşer' gibi doğrudan veya dolaylı yatırım tavsiyeleri VERME.
   - Sadece araçlardan gelen 30 günlük verileri, istatistikleri ve piyasa durumunu objektif şekilde karşılaştır, riskleri hatırlat ve nihai kararı her zaman kullanıcıya bırak.

4. SUNUM VE SOHBET:
   - Selamlaşma, genel sohbet veya araç gerektirmeyen mantık sorularında araç çağırmana gerek yoktur, doğrudan yanıt ver.
   - Araçlardan gelen bilgileri kullanıcıya samimi, profesyonel, anlaşılır ve Türkçe bir özet halinde sun."""

def run_tool_calls(tool_calls: list[dict]) -> list[dict]:
    """Modelin çağırmak istediği fonksiyonları tetikler ve sonuçları mesaj formatında döndürür."""
    messages = []
    for call in tool_calls:
        name = call["function"]["name"]
        arguments = call["function"].get("arguments") or {}
        
        # Kaputun altında hangi aracın hangi parametreyle çağrıldığını terminalde gösterelim
        print(f"  🔧 Araç Çalıştırılıyor: {name}({arguments})")

        function = tools.TOOLS.get(name)
        if function is None:
            output = f"'{name}' adında bir araç sistemde tanımlı değil."
        else:
            try:
                output = function(**arguments)
            except Exception as exc:
                output = f"Araç çalıştırılırken hata oluştu: {exc}"
        print(f"  📥 Araçtan Gelen Veri: {str(output)}")    
        messages.append({
            "role": "tool",
            "tool_name": name,
            "content": str(output)
        })
    return messages


def main():
    parser = argparse.ArgumentParser(description="Ollama tabanlı araç çağırabilen (Tool Calling) asistan.")
    parser.add_argument(
        "--chat-model",
        default=ollama_client.CHAT_MODEL,
        help="Ollama üzerinde çalışacak sohbet modeli (varsayılan: llama3.1)"
    )
    args = parser.parse_args()

    print("🤖 Yapay Zeka Teknolojik Asistanı Başlatıldı")
    print(f"  🧠 Sohbet Modeli : {args.chat_model}")
    print("  🚪 Çıkış yapmak için: 'çık', 'cik', 'exit' veya 'quit' yazın.\n")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            question = input("Siz > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nGörüşmek üzere!")
            break

        if not question:
            continue

        if question.lower() in {"cik", "çık", "exit", "quit"}:
            print("Görüşmek üzere!")
            break

        # Kullanıcı sorusunu sohbet geçmişine ekle
        messages.append({"role": "user", "content": question})

        try:
            for _ in range(MAX_TOOL_ROUNDS):
                # Modele mesaj geçmişini ve tools.py içindeki JSON şemalarını gönderiyoruz
                message = ollama_client.chat(
                    messages=messages,
                    model=args.chat_model,
                    tools=tools.TOOL_SCHEMAS
                )
                messages.append(message)

                tool_calls = message.get("tool_calls")
                
                # Model araç çağırmadıysa yanıt üretmiştir, döngüyü sonlandır
                if not tool_calls:
                    break

                # Model araç çağırdıysa ilgili fonksiyonu çalıştır ve sonucu sohbet geçmişine ekle
                tool_messages = run_tool_calls(tool_calls)
                messages.extend(tool_messages)

        except RuntimeError as exc:
            print(f"\nHata Oluştu: {exc}\n")
            continue

        # Modelin ürettiği son yanıtı yazdır
        response_content = (message.get("content") or "").strip()
        if response_content:
            print(f"\nAsistan > {response_content}\n")


if __name__ == "__main__":
    main()