import datetime
import json
import os

from dotenv import load_dotenv
from groq import Groq

from tools import execute_code, get_weather, internet_search

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

SYSTEM_PROMPT = f"""
    Sen kullanıcılara hizmet veren bir yapay zeka asistanısın.
    Kullanıcıların sorularını yanıtlamak için aşağıdaki araçları kullanabilirsin:
    1. get_weather(city: str) -> dict: Verilen şehir için hava durumu verilerini döner.
    2. internet_search(query: str) -> str: Verilen sorgu için internet araması yapar ve sonuçları döner.
    3. execute_code(code: str) -> str: Senin ürettiğin Python kodunu çalıştırır ve çıktısını döner.
    Kullanıcılar sana sorularını sorduğunda, önce soruyu anla ve ardından uygun aracı kullanarak yanıt ver.
    Özellikle hava durumu sorularında get_weather aracını, internet araması gerektiren sorularda internet_search aracını ve Python kodu çalıştırmayı gerektiren sorularda execute_code aracını kullan.
    Kullanıcıya kod üretme işleminde diğer dillerle kod üretebilirsin ancak önceliğin Python kodu olmaldır.
    Ürettiğin kodu çalıştırmak için execute_code aracını kullan.
    Kullanıcının sana sorduğu soru bir araç kullanmayı gerektirmiyorsa doğrudan yanıt ver. Örneğin kullanıcı sana "Merhaba" derse doğrudan "Merhaba! Size nasıl yardımcı olabilirim?" şeklinde yanıt ver.
    Ancak kullanıcı sana Python da fibonacci dizisi oluştur ve ilk 5 sonucu topla derse bunu veren kodu oluştur ve execute_code aracını kullanarak çalıştır.
    Kullanıcının sorabileceği güncel bilgiler için bugünün tarihi : {datetime.datetime.now().strftime('%Y-%m-%d')}
    """

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Verilen bir şehir için güncel hava durumu bilgilerini (sıcaklık, nem, rüzgar hızı) döner. Kullanıcı hava durumu, sıcaklık, nem veya rüzgar hakkında bir şehir belirterek soru sorduğunda kullan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "Hava durumu öğrenilmek istenen şehrin adı. Örnek: 'Istanbul', 'Ankara', 'Izmir'.",
                    }
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "internet_search",
            "description": "İnternette güncel bilgi aramak için kullanılır. Döviz kuru, haberler, güncel olaylar, senin bilgi kesim tarihinden sonraki gelişmeler gibi anlık/güncel veri gerektiren sorularda kullan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Aranacak arama sorgusu. Örnek: 'dolar kuru bugün', 'son dakika haberleri'.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_code",
            "description": "Python kodu üretip çalıştırmak için kullanılır. Kullanıcı hesaplama, algoritma, veri işleme, script yazdırma gibi bir kod çalıştırılmasını gerektiren bir görev istediğinde kullan. Üretilen kod kullanıcıdan onay aldıktan sonra çalıştırılır.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Çalıştırılacak tam ve çalışabilir Python kodu. Çıktı üretmek için print() kullanılmalı.",
                    }
                },
                "required": ["code"],
            },
        },
    },
]

tool_functions = {
    "get_weather": get_weather,
    "internet_search": internet_search,
    "execute_code": execute_code,
}

client = Groq(api_key=GROQ_API_KEY)
print("""
        ███  ████   ███   ███      ███   ███  █████ █   ██████
       █     █   █ █   █ █   █    █   █ █     █     ██  █   █
       █  ██ ████  █   █ █   █    █████ █  ██ ████  █ █ █   █
       █   █ █  █  █   █ █  █     █   █ █   █ █     █  ██   █
        ███  █   █  ███   ██ █    █   █  ███  █████ █   █   █   """)

messages = [{"role": "system", "content": SYSTEM_PROMPT}]


def run_agent(messages: list, max_iterations: int = 5) -> None:
    """
    Model tool çağırmayı bırakıp düz cevap verene kadar
    ya da max iteration kadar döngüde kalır.
    Input:
        messages (list): Model ile yapılan konuşmaların listesi.
        max_iterations (int): Maksimum iterasyon sayısı.
    Output:
        None
    """

    for _ in range(max_iterations):
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        response_message = response.choices[0].message
        messages.append(response_message)
        tool_calls = response_message.tool_calls
        if tool_calls:
            for tool_call in tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                print(f"\n[Tool Call]: {func_name} ({func_args})")
                func = tool_functions.get(func_name)
                if func:
                    try:
                        result = func(**func_args)
                    except Exception as e:
                        result = f"{func_name} çalıştırma hatası: {str(e)}"
                else:
                    result = f"Bilinmeyen Tool: {func_name}"
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": str(result),
                    }
                )
        else:
            print(f"\nAsistan: > {response_message.content}")
            break


while True:
    user_input = input("\nKullanıcı: > ")
    if user_input.lower() in ["exit", "quit", "çıkış", "q", "çık"]:
        print("Çıkış yapılıyor...")
        break
    messages.append({"role": "user", "content": user_input})
    try:
        run_agent(messages)
    except Exception as e:
        print(f"Bir hata oluştu: {str(e)}")
