"""Araç çağırabilen HidroRisk asistanı (komut satırı).

Döngü çok basit:
kullanıcı sorar -> model ya cevap verir ya da bir araç çağırır
-> aracı biz çalıştırır, sonucu modele geri veririz
-> model nihai cevabı yazar

Kullanım:
python chat.py
"""

import argparse

import ollama_client
import tools


MAX_TOOL_ROUNDS = 5  # sonsuz araç döngüsüne karşı emniyet freni


SYSTEM_PROMPT = """Sen HidroRisk adında Türkçe konuşan bir hidroloji ve hidrolik ön değerlendirme asistanısın.

Elinde 5 araç var:

- calculate_peak_runoff: Rasyonel Yöntem ile pik yüzeysel akış debisini hesaplar.

- check_channel_capacity: Manning denklemi ile dikdörtgen açık kanal kapasitesini hesaplar ve verilen tasarım debisine göre yeterliliğini kontrol eder.

- calculate_spi: Aylık yağış verisi içeren CSV dosyasından seçilen zaman ölçeğinde Standartlaştırılmış Yağış İndisi (SPI) hesaplar.

- plot_spi_series: Aylık yağış verisi içeren CSV dosyasından seçilen zaman ölçeğinde SPI zaman serisi grafiği oluşturur ve PNG dosyası olarak kaydeder.

- internet_search: Güncel bilgi, standart, mevzuat veya genel bilgi için internette arama yapar.

KURALLAR:

- Sayısal bir hidroloji veya hidrolik hesabı için uygun araç varsa hesabı kendin tahmin etme, ilgili aracı kullan.

- Hesap için gerekli bir parametre eksikse değer uydurma. Kullanıcıdan eksik bilgiyi iste.

- Manning n katsayısı, kanal eğimi, yağış şiddeti, akım katsayısı gibi mühendislik girdilerini kullanıcı vermediyse kendin seçme.

- Bir yağış serisinin kurak veya nemli olduğunu söylemeden önce SPI hesabı gerekiyorsa calculate_spi aracını kullan.

- Aracın döndürdüğü sayısal sonucu esas al ve sonucu değiştirme.

- Güncel veya dış kaynaktan doğrulanması gereken bilgiler için internet_search aracını kullan.

- Selamlaşma, sohbet ve kavramsal sorular için araç çağırmana gerek yok.

- Kanal yeterliliği sorularında araç sonucu YETERLI ise cevaba "Evet", YETERSIZ ise "Hayır" diye başla. Sonuçla çelişen bir ifade kullanma.

- Araç sonucundaki teknik terimleri anlamlarını değiştirecek şekilde yeniden adlandırma. Örneğin "uniform akis" ifadesini aynen koru.

- SPI sonucunu yorumlarken yalnızca toolun belirttiği son tarihteki sınıfı söyle. Tüm veri serisinin genel olarak kurak, nemli, normal veya dengeli olduğunu söyleme ve geleceğe yönelik devam edeceği anlamına gelen yorum yapma.

- Kullanıcı SPI grafiği, çizim, plot veya görselleştirme isterse plot_spi_series aracını kullan. Grafik veya çizim sonucu oluşturulduğunda dosya yolunu kullanıcıya bildir.

- Kullanıcı internet_search için belirli bir sonuç sayısı isterse max_results değerini aynı sayı olarak kullan.

- internet_search aracının döndürdüğü kaynak başlıklarını ve URL'leri aynen kullan. Başlıkları yeniden adlandırma, URL'leri değiştirme veya araç sonucunda bulunmayan kaynak ekleme.

- internet_search aracı yalnızca başlık ve URL döndürüyorsa kaynakların içeriği hakkında ek açıklama üretme. Yalnızca araç sonucunda gerçekten bulunan bilgileri aktar.

- internet_search aracı kullanıldıysa nihai cevapta yalnızca aracın döndürdüğü kaynakları numaralı liste halinde başlık ve URL ile ver. Kaynak listesinden önce veya sonra açıklama, özet, yorum, çıkarım ya da sonuç cümlesi ekleme.

- Herhangi bir araç çağrıldıktan sonra nihai cevabı araç sonucuna dayandır. Aracın döndürmediği sayısal değer, kaynak, URL veya teknik sonuç ekleme.

- HidroRisk bir ön değerlendirme asistanıdır; sonuçları nihai mühendislik projesi veya resmi onay olarak sunma.
"""


parser = argparse.ArgumentParser(
    description="Ollama tabanli HidroRisk asistani."
)

parser.add_argument(
    "--chat-model",
    default=ollama_client.CHAT_MODEL,
    help="Ollama sohbet modeli",
)

args = parser.parse_args()


def run_tool_calls(tool_calls: list[dict]) -> list[dict]:
    """Modelin istedigi araclari calistirir ve sonuclari mesaj formatinda dondurur."""

    messages = []

    for call in tool_calls:
        name = call["function"]["name"]
        arguments = call["function"].get("arguments") or {}

        print(f"\n[TOOL] {name}({arguments})")

        function = tools.TOOLS.get(name)

        if function is None:
            output = f"'{name}' adinda bir arac yok."
        else:
            try:
                output = function(**arguments)
            except Exception as exc:  # arac hatasi sohbeti bitirmesin
                output = f"Arac calistirilamadi: {exc}"

        messages.append(
            {
                "role": "tool",
                "tool_name": name,
                "content": output,
            }
        )

    return messages


print("=" * 60)
print("                         HIDRORISK")
print("          Yerel Hidroloji ve Hidrolik Risk Asistanı")
print("=" * 60)
print()
print(f"Model : {args.chat_model}")
print()
print("Araçlar:")
print("  [1] Pik Debi Hesabı")
print("  [2] Açık Kanal Kapasitesi")
print("  [3] SPI Kuraklık Analizi")
print("  [4] SPI Grafik Oluşturma")
print("  [5] İnternet Araması")
print()
print("Çıkmak için: çık")
print("-" * 60)
print()


messages = [{"role": "system", "content": SYSTEM_PROMPT}]


while True:
    try:
        question = input("Siz > ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        break

    if not question:
        continue

    if question.lower() in {"cik", "cık", "çık", "çik", "exit", "quit"}:
        break

    messages.append({"role": "user", "content": question})

    try:
        for _ in range(MAX_TOOL_ROUNDS):
            message = ollama_client.chat(
                messages,
                model=args.chat_model,
                tools=tools.TOOL_SCHEMAS,
            )

            messages.append(message)

            tool_calls = message.get("tool_calls")

            if not tool_calls:
                break

            messages.extend(run_tool_calls(tool_calls))

    except RuntimeError as exc:
        print(f"\nHata: {exc}\n")
        continue

    print(f"\nHidroRisk > {(message.get('content') or '').strip()}\n")
print("-" * 60)