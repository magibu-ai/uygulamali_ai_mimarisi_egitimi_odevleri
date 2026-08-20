"""Ollama yerel servisi ile iletişim ve Guardrail mantığı."""

import os
import json
import requests
from typing import Dict, Any, List
from tools_def import TOOL_SCHEMAS

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = "qwen2.5:7b"

SYSTEM_PROMPT = """Sen yalnızca Türkçe Selamlaşma, Matematiksel Hesaplamalar ve Matematik Araştırmaları konusunda hizmet veren uzman bir asistansın.

KESİN VE DEĞİŞTİRİLEMEZ KURALLAR:
1. MATEMATİKSEL İŞLEMLERDE KENDİN DOĞRUDAN HESAPLAMA SONUCU VEYA SAYISAL CEVAP ÜRETME!
   - Kullanıcı herhangi bir matematiksel hesaplama (toplama, çarpma, matris, türev, integral, asal sayı, yüzde, alan/hacim, istatistik, denklem vb.) istediğinde KESİNLİKLE 'generate_math_js' aracını çağır.
   - Bu araç çağrısında (tool call) tarayıcı tarafında (client-side) çalıştırılacak JavaScript kodu (code), dosya adı (filename) ve açıklama üret.

2. MATEMATİKSEL SABİT & FORMÜL ARAMALARI (DUCKDUCKGO SEARCH):
   - Kullanıcı matematiksel bir sabit (ör. dünyanın yarıçapı, euler sayısı, ışık hızı, yerçekimi ivmesi), matematiksel bir formül, geometri kuralı veya matematik tarihi hakkında bilgi istediğinde 'duckduckgo_math_search' aracını çağır.
   - Genel kültür, haberler, magazin, spor vb. MATEMATİK DIŞI konularda web araması yapma!

3. SELAMLAŞMA VE HAL-HATIR MESAJLARI:
   - Kullanıcı 'Merhaba', 'Selam', 'Nasılsın?', 'İyi günler' gibi selamlaşma mesajları yazdığında dostane ve samimi şekilde Türkçe yanıt ver.
   - Selamlaşma için araç (tool) çağırmana gerek yoktur.

4. KAPSAM DIŞI KONULAR (STRICT GUARDRAIL):
   - Matematik ve Selamlaşma DIŞINDAKİ HERHANGİ bir konuda (tarih, coğrafya, hava durumu, genel kültür, kodlama eğitimi, sağlık, spor, güncel olaylar vb.) KESİNLİKLE DESTEK VERME.
   - Kapsam dışı sorular geldiğinde AYNEN şu standart yanıtı ver:
     "Üzgünüm, ben yalnızca matematiksel hesaplamalar ve matematik araştırmaları konusunda yardımcı olabilirim."

5. ARACIN İÇERİĞİ (JAVASCRIPT KODU VE PARAMETRELER):
   - Ürettiğin JavaScript kodu tarayıcıda hatasız çalışmalıdır.
   - KODUN İÇİNDE GİRDİLERİ TANIMLA VEYA 'args' DİZİSİNİ DOLU GÖNDER.
6. DÜZ METİN MESAJLARINDA KOD YAZMA:
   - Düz metin yanıtlarında (content) KESİNLİKLE JavaScript kodları veya ```javascript kod blokları YAZMA. Kodlar sadece ve sadece 'generate_math_js' aracıyla gönderilmelidir.
"""


def perform_ddg_search(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """DuckDuckGo kullanarak web araması yapar (matematik bağlamlı)."""
    results = []
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            ddg_gen = ddgs.text(query, max_results=max_results)
            if ddg_gen:
                for r in ddg_gen:
                    results.append({
                        "title": r.get("title", ""),
                        "snippet": r.get("body", ""),
                        "url": r.get("href", "")
                    })
    except Exception as e:
        print(f"DuckDuckGo arama hatası: {e}")
    return results


def get_available_models() -> List[str]:
    """Yerel Ollama sunucusundaki yüklü modelleri listeler."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=300)
        if resp.status_code == 200:
            data = resp.json()
            models = [m.get("name") for m in data.get("models", []) if m.get("name")]
            return models if models else [DEFAULT_MODEL]
    except Exception as e:
        print(f"Ollama modelleri alınamadı: {e}")
    return [DEFAULT_MODEL]


def chat_with_agent(user_messages: List[Dict[str, str]], model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    """
    Kullanıcı mesajlarını alarak Ollama chat API'sine tool şeması ile gönderir.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(user_messages)

    payload = {
        "model": model,
        "messages": messages,
        "tools": TOOL_SCHEMAS,
        "stream": False,
        "options": {
            "temperature": 0.1  # Kod ve mantık üretimi için düşük sıcaklık
        }
    }

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=300
        )
        response.raise_for_status()
        res_data = response.json()
        message = res_data.get("message", {})

        tool_calls = message.get("tool_calls", [])
        if tool_calls:
            # Model tool call tetikledi
            first_call = tool_calls[0]
            func_data = first_call.get("function", {})
            func_name = func_data.get("name")
            arguments = func_data.get("arguments", {})

            # arguments string ise json parse et
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except Exception:
                    arguments = {}

            if func_name == "duckduckgo_math_search":
                query = arguments.get("query", "")
                max_results = int(arguments.get("max_results", 3))
                search_results = perform_ddg_search(query, max_results=max_results)
                return {
                    "type": "web_search",
                    "query": query,
                    "results": search_results,
                    "message": f"'{query}' konusu için matematiksel web araması yapıldı."
                }

            if func_name == "generate_math_js":
                filename = arguments.get("filename", "math_script.js")
                if not filename.endswith(".js"):
                    filename += ".js"
                
                description = arguments.get("description", "Matematiksel hesaplama scripti")
                code = arguments.get("code", "")
                js_function_name = arguments.get("function_name", "")
                args_list = arguments.get("args", [])

                # JS dosyasını sunucuda kaydet
                scripts_dir = os.path.join(os.path.dirname(__file__), "generated_scripts")
                os.makedirs(scripts_dir, exist_ok=True)
                file_path = os.path.join(scripts_dir, filename)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(code)

                # Static dizine de kopyala/kaydet (tarayıcı erişimi için)
                static_scripts_dir = os.path.join(os.path.dirname(__file__), "static", "scripts")
                os.makedirs(static_scripts_dir, exist_ok=True)
                static_file_path = os.path.join(static_scripts_dir, filename)
                with open(static_file_path, "w", encoding="utf-8") as f:
                    f.write(code)

                return {
                    "type": "tool_call",
                    "tool_name": func_name,
                    "filename": filename,
                    "file_url": f"/static/scripts/{filename}",
                    "description": description,
                    "code": code,
                    "function_name": js_function_name,
                    "args": args_list,
                    "message": f"İşlem için '{filename}' dosyası üretildi. Hesaplama tarayıcıda çalıştırılıyor..."
                }

        # Düz yanıt (Selamlaşma veya Kapsam Dışı Reddetme veya Yanlışlıkla Metin İçine Kod Yazma)
        content = message.get("content", "").strip()

        # Eğer model tool_call tetiklemeyip düz metin içine kod bloğu yazdıysa bunu yakala
        import re
        code_match = re.search(r'```(?:javascript|js)?\s*([\s\S]*?)```', content)
        if code_match:
            extracted_code = code_match.group(1).strip()
            description_text = re.sub(r'```(?:javascript|js)?\s*[\s\S]*?```', '', content).strip()
            if not description_text:
                description_text = "Matematiksel hesaplama"

            filename = "calculate_script.js"
            static_scripts_dir = os.path.join(os.path.dirname(__file__), "static", "scripts")
            os.makedirs(static_scripts_dir, exist_ok=True)
            static_file_path = os.path.join(static_scripts_dir, filename)
            with open(static_file_path, "w", encoding="utf-8") as f:
                f.write(extracted_code)

            return {
                "type": "tool_call",
                "tool_name": "generate_math_js",
                "filename": filename,
                "file_url": f"/static/scripts/{filename}",
                "description": description_text,
                "code": extracted_code,
                "function_name": "",
                "args": [],
                "message": f"Hesaplama tarayıcıda çalıştırılıyor..."
            }

        return {
            "type": "text",
            "message": content
        }

    except requests.exceptions.RequestException as exc:
        return {
            "type": "error",
            "message": f"Ollama servisine bağlanırken hata oluştu: {exc}. Ollama servisinin açık olduğundan emin olun."
        }
