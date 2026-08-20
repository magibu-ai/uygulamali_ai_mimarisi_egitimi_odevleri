import time
import ollama
from tools import AVAILABLE_TOOLS, TOOL_DEFINITIONS

MODEL_NAME = "qwen2.5:3b"
MAX_ITERATIONS = 5
MAX_HISTORY = 10

SYSTEM_PROMPT = """
Sen "Akıllı Tekstil ve Örgü Asistanı" (Craft Companion) adında uzman bir yapay zeka asistanısın.

GÖREVLERİN:
- Örgü, tığ işi, amigurumi, iplik türleri, ip markaları, motifler ve malzeme hesaplama sorularını yanıtlamak.
- Tanımlı araçları (tools) doğru zamanda, izin istemeden DOĞRUDAN çalıştırmak.

KAPSAMA DAHİL KONULAR (KESİNLİKLE YANITLA):
- Amigurumi, tığ işi, el örgüsü, motif tarifleri.
- İp markaları (Alize, Nako, Gazzal vb.), iplik kalitesi ve iplik karşılaştırmaları.
- Örgü yıkama, bakım ve birleştirme (yatak dikişi) teknikleri.

KATI KAPSAM DIŞI VE REDDETME (GUARDRAIL):
- Dikiş makinesi kullanımı, terzilik, konfeksiyon veya el sanatları dışı (yazılım, matematik, genel kültür) soruları REDDET.
- Reddetme Mesajı: "Üzgünüm, ben sadece örgü, tığ işi ve el sanatları alanında hizmet vermek üzere özelleştirilmiş bir asistanım. Bu konuda size yardımcı olamam."

ZORUNLU ARAÇ (TOOL) KULLANIM KURALLARI:
1. Kullanıcı İP MARKASI, TREND, BAKIM, MOTİF TARİFİ veya İPLİK KARŞILAŞTIRMASI sorduğunda -> DOĞRUDAN `web_search` aracını çalıştır.
2. Kullanıcı KISALTMA veya TERİM (sc, hdc, magic ring) sorduğunda -> DOĞRUDAN `query_craft_rag` aracını çalıştır.
3. Kullanıcı MALZEME/HESAP sorduğunda -> `calculate_craft_material` aracını çalıştır.
4. Kullanıcı BİRİM DÖNÜŞÜMÜ (inç, oz) sorduğunda -> `convert_yarn_units` aracını çalıştır.
5. Kullanıcı "KAYDET" dediğinde -> `export_project_plan` aracını çalıştır.

ÇIKTI KURALLARI:
- "Arama yapayım mı?", "Başka sorunuz var mı?" gibi sorular KESİNLİKLE SORMA.
- `web_search` çıktısı aldığında bilgileri sade bir Türkçe liste olarak sun ve cevabı DOĞRUDAN BİTİR.
"""



CRAFT_KEYWORDS = [
    "örgü", "orgu", "tığ", "tig", "ip", "iplik", "ilmek", "motif",
    "amigurumi", "crochet", "knitting", "yarn", "pattern", "battaniye", "kazak",
    "sc", "hdc", "dc", "inc", "dec", "magic ring", "sihirli halka", "blocking", 
    "şiş", "sis", "yumak", "metraj", "inç", "inc", "cm", "gram", "oz", "yarda", 
    "ölçü", "olcu", "yatak dikişi", "hırka", "yıkama", "papatya","motif","sık iğne","trabzan"
]

def check_domain_with_llm(user_query: str) -> bool:
    classification_prompt = f"""
    Aşağıdaki kullanıcı sorusunu analiz et ve el sanatları (örgü/tığ işi) kapsamına girip girmediğine karar ver.

    KAPSAM İÇİ (EVET):
    - El örgüsü, tığ işi, amigurumi, iplik türleri, motifler.
    - Örgü parçalarını elle birleştirme (yatak dikişi / seaming).
    - Örgü projeleri için ip/ilmek hesabı, yıkama/bakım ve birim dönüşümleri.

    KAPSAM DIŞI (HAYIR):
    - Dikiş makinesi kullanımı, kumaş kesimi, kalıp çıkarma, terzilik ve tekstil imalatı.
    - Örgü/el sanatı dışındaki tüm genel konular (yazılım, genel kültür, matematik vb.).

    Soru: "{user_query}"
    
    Sadece 'EVET' veya 'HAYIR' yanıtı ver.
    """
    try:
        res = ollama.chat(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": classification_prompt}],
            options={"temperature": 0.1}
        )
        answer = res.get("message", {}).get("content", "").strip().upper()
        return "EVET" in answer
    except Exception:
        return True

def is_on_topic(user_query: str) -> bool:
    query_lower = user_query.lower()
    if any(keyword in query_lower for keyword in CRAFT_KEYWORDS):
        return True
    return check_domain_with_llm(user_query)

def run_conversation(messages: list) -> str:
    REJECTION_MESSAGE = "Üzgünüm, ben sadece örgü, tığ işi ve el sanatları alanında hizmet vermek üzere özelleştirilmiş bir asistanım. Bu konuda size yardımcı olamam."

    if messages and messages[-1]["role"] == "user":
        last_user_msg = messages[-1]["content"]
        if not is_on_topic(last_user_msg):
            return REJECTION_MESSAGE

    trimmed_history = messages[-MAX_HISTORY:] if len(messages) > MAX_HISTORY else messages
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + trimmed_history

    iteration = 0

    try:
        while iteration < MAX_ITERATIONS:
            iteration += 1

            response = ollama.chat(
                model=MODEL_NAME,
                messages=full_messages,
                tools=TOOL_DEFINITIONS,
                options={"temperature": 0.1}
            )

            message = response.get("message", {})
            tool_calls = message.get("tool_calls")

            if not tool_calls:
                return message.get("content", "")

            full_messages.append(message)

            for tool_call in tool_calls:
                func_name = tool_call["function"]["name"]
                func_args = tool_call["function"]["arguments"]

                print(f"\n   [AJAN ADIMI {iteration}]: '{func_name}' aracı çalıştırılıyor...")
                print(f" └─ Parametreler: {func_args}")

                start_time = time.time()
                
                if func_name in AVAILABLE_TOOLS:
                    try:
                        tool_result = AVAILABLE_TOOLS[func_name](**func_args)
                        exec_time = round(time.time() - start_time, 3)
                        print(f" └─ Tamamlandı ({exec_time}s) -> Sonuç: {tool_result}")
                    except Exception as err:
                        tool_result = f"Araç çalıştırma hatası: {str(err)}"
                else:
                    tool_result = f"Hata: {func_name} adında bir araç tanımlı değil."

                full_messages.append({
                    "role": "tool",
                    "content": str(tool_result)
                })

        return "İşlem adımları sınırına ulaşıldı. Lütfen talebinizi daha basit parçalara bölerek iletin."

    except Exception as e:
        return f"Sistem hatası oluştu: {str(e)}"