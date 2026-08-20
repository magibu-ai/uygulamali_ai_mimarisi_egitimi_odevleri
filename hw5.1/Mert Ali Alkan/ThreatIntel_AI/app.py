import os
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv

load_dotenv()

import re
import ollama_client
import tools
from chat import SYSTEM_PROMPT, run_tool_calls

app = Flask(__name__, static_folder='static')


def _auto_calculate_risk(tool_logs: list[dict]) -> dict | None:
    """Arac sonuclarini tarayarak DETERMINISTIK risk skoru hesaplar.
    
    LLM'in boolean parametreleri yanlis gondermesi sorununu tamamen ortadan kaldirir.
    Python kodu arac ciktilarini anahtar kelimelerle tarar ve skoru hesaplar.
    """
    # Hic arac cagrilmadiysa (basit sohbet) skor hesaplama
    tool_names = [log["name"] for log in tool_logs]
    if "analyze_email" not in tool_names and "extract_urls" not in tool_names:
        return None
    
    all_results = " ".join(log["result"] for log in tool_logs).lower()
    
    score = 0
    flags = {}
    
    # 1. Zararli URL var mi? (+40)
    if "'zararli/supheli' isaretledi" in all_results:
        score += 40
        flags["has_malicious_url"] = True
    else:
        flags["has_malicious_url"] = False
    
    # 2. Gonderici supheli mi? (+30)
    if "kimlige burunme" in all_results or "masquerading" in all_results:
        score += 30
        flags["is_sender_suspicious"] = True
    else:
        flags["is_sender_suspicious"] = False
    
    # 3. Domain yeni mi? (+20)
    if "cok supheli!" in all_results or "yeni veya sahte olabilir!" in all_results:
        score += 20
        flags["is_domain_new"] = True
    else:
        flags["is_domain_new"] = False
    
    # 4. Aciliyet var mi? (+10)
    if "aciliyet iceriyor mu?: evet" in all_results:
        score += 10
        flags["urgency"] = True
    else:
        flags["urgency"] = False
    
    category = "LOW"
    if score >= 30: category = "MEDIUM"
    if score >= 60: category = "HIGH"
    if score >= 80: category = "CRITICAL"
    
    return {
        "score": score,
        "category": category,
        "flags": flags,
        "text": f"Otomatik Risk Skoru: {score}/100. Seviye: {category}. "
                f"Detay: sender_suspicious={flags['is_sender_suspicious']}, "
                f"malicious_url={flags['has_malicious_url']}, "
                f"domain_new={flags['is_domain_new']}, "
                f"urgency={flags['urgency']}"
    }


@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return app.send_static_file(filename)

import json
from flask import Response, stream_with_context

@app.route('/api/chat', methods=['POST'])
def chat_api():
    data = request.json
    user_message = data.get('message', '')
    history = data.get('history', [])
    
    if not history:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    else:
        messages = history
        
    user_message_structured = f"GOREV: E-postayi analiz et ve gerekli ARACLARI CAGIR. Asla duz metin yanit verme.\n\n--- E-POSTA ---\n{user_message}\n--- SON ---"
    messages.append({"role": "user", "content": user_message_structured})
    
    def generate():
        try:
            tool_logs = []
            final_response = ""
            
            for _ in range(15):
                message = ollama_client.chat(
                    messages, model=ollama_client.CHAT_MODEL, tools=tools.TOOL_SCHEMAS
                )
                messages.append(message)
                
                content = message.get("content", "")
                
                # Extract and yield think block
                if "<think>" in content:
                    think_match = re.search(r'<think>(.*?)(?:</think>|$)', content, flags=re.DOTALL)
                    if think_match:
                        think_text = think_match.group(1).strip()
                        if think_text:
                            yield f"data: {json.dumps({'type': 'think', 'content': think_text})}\n\n"
                
                tool_calls = message.get("tool_calls")
                
                # Fallback tool parsing for DeepSeek/R1 models that output JSON in content instead of tool_calls
                if not tool_calls and "{" in content:
                    # Strip think block before parsing JSON
                    clean_content = re.sub(r'<think>.*?(?:</think>|$)', '', content, flags=re.DOTALL).strip()
                    # Try to extract JSON from markdown code block or raw text
                    json_match = re.search(r'```(?:json)?\s*(\[.*\]|\{.*\})\s*```', clean_content, flags=re.DOTALL)
                    if not json_match:
                        json_match = re.search(r'(\[.*\]|\{.*\})', clean_content, flags=re.DOTALL)
                        
                    if json_match:
                        try:
                            parsed = json.loads(json_match.group(1))
                            if isinstance(parsed, dict) and "name" in parsed and parsed["name"] in tools.TOOLS:
                                args = parsed.get("arguments", parsed.get("parameters", {}))
                                if not args and parsed["name"] in ["check_virustotal", "check_rdap"]:
                                    urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', user_message)
                                    if urls: args = {"url": urls[0], "domain": urls[0]}
                                elif not args and parsed["name"] == "search_phishing_rag":
                                    args = {"query": user_message}
                                tool_calls = [{"function": {"name": parsed["name"], "arguments": args}}]
                            elif isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict) and "name" in parsed[0] and parsed[0]["name"] in tools.TOOLS:
                                tool_calls = []
                                for p in parsed:
                                    if "name" in p and p["name"] in tools.TOOLS:
                                        args = p.get("arguments", p.get("parameters", {}))
                                        if not args and p["name"] in ["check_virustotal", "check_rdap"]:
                                            urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', user_message)
                                            if urls: args = {"url": urls[0], "domain": urls[0]}
                                        elif not args and p["name"] == "search_phishing_rag":
                                            args = {"query": user_message}
                                        tool_calls.append({"function": {"name": p["name"], "arguments": args}})
                        except Exception:
                            pass
                
                if not tool_calls:
                    break
                    
                for call in tool_calls:
                    yield f"data: {json.dumps({'type': 'tool_call', 'name': call['function']['name'], 'args': call['function'].get('arguments', {})})}\n\n"
                    
                with open("tool_calls.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps(tool_calls, indent=2) + "\n")
                    
                tool_results = run_tool_calls(tool_calls)
                
                for call, result in zip(tool_calls, tool_results):
                    tool_logs.append({
                        "name": call["function"]["name"],
                        "arguments": call["function"].get("arguments", {}),
                        "result": result["content"]
                    })
                    yield f"data: {json.dumps({'type': 'tool_result', 'name': call['function']['name'], 'result': result['content']})}\n\n"
                    
                messages.extend(tool_results)
            
            # ═══ OTOMATİK RİSK SKORU HESAPLAMA ═══
            risk_result = _auto_calculate_risk(tool_logs)
            
            if risk_result:
                yield f"data: {json.dumps({'type': 'tool_call', 'name': 'auto_risk_score', 'args': risk_result['flags']})}\n\n"
                tool_logs.append({
                    "name": "auto_risk_score",
                    "arguments": risk_result["flags"],
                    "result": risk_result["text"]
                })
                yield f"data: {json.dumps({'type': 'tool_result', 'name': 'auto_risk_score', 'result': risk_result['text']})}\n\n"
            
            report_prompt = (
                f"Aşağıda analiz edilen şüpheli e-posta ve OSINT araçlarının sonuçları yer almaktadır:\n\n"
                f"--- E-POSTA ---\n{user_message}\n\n"
                f"--- ARAÇ SONUÇLARI ---\n"
            )
            
            if tool_logs:
                for log in tool_logs:
                    report_prompt += f"Araç: {log['name']}\nSonuç: {log['result']}\n\n"
            else:
                report_prompt += "HİÇBİR ARAÇ KULLANILMADI (Sistem Hatası veya Model Araç Kullanmayı Reddetti).\n\n"
                
            report_prompt += f"--- HESAPLANAN RİSK SKORU ---\n"
            if risk_result:
                report_prompt += f"{risk_result['score']}/100 - {risk_result['category']}\n\n"
            else:
                report_prompt += "Hesaplanamadı (Araç çağrılmadığı için).\n\n"
                
            report_prompt += (
                "GÖREV: Yukarıdaki bilgileri harmanlayarak bir nihai rapor oluştur.\n\n"
                "RAPOR FORMATI (Bu basliklari kullan):\n"
                "Karar: (Zararli / Supheli / Guvenli)\n"
                "Risk Skoru: (Sistemin ilettigi skoru yaz)\n"
                "Onemli Bulgular: (Tespitleri akici dille ozetle. OSINT Sonuclarini da dahil et.)\n"
                "MITRE ATT&CK Eslesmesi: (Varsa acikla, yoksa 'Tespit edilemedi' yaz)\n"
                "Kullaniciya Oneri: (Net guvenlik tavsiyeleri ver)\n\n"
                "SADECE RAPOR METNINI URET, Baska bir sey yazma."
            )

            try:
                final_msg = ollama_client.chat(
                    [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": report_prompt}], 
                    model=ollama_client.CHAT_MODEL, 
                    tools=None
                )
                content = final_msg.get('content', '')
                
                if "<think>" in content:
                    think_match = re.search(r'<think>(.*?)</think>', content, flags=re.DOTALL)
                    if think_match:
                        think_text = think_match.group(1).strip()
                        if think_text:
                            yield f"data: {json.dumps({'type': 'think', 'content': think_text})}\n\n"
                    
                final_response = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            except Exception as ollama_err:
                yield f"data: {json.dumps({'type': 'error', 'content': f'Rapor olusturma sirasinda hata: {str(ollama_err)}'})}\n\n"
                
            if not final_response:
                final_response = "Analiz tamamlandı ancak rapor metni oluşturulamadı (Model bos yanit dondu). Lütfen tekrar deneyin."
                
            yield f"data: {json.dumps({'type': 'report', 'content': final_response})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'Sunucu Hatasi: {str(e)}'})}\n\n"
            
    return Response(stream_with_context(generate()), mimetype="text/event-stream")

if __name__ == '__main__':
    print("ThreatIntel AI calisiyor: http://localhost:5000")
    app.run(host='127.0.0.1', port=5000, debug=False)
