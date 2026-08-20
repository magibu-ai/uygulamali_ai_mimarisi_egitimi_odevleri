import json
import os

from huggingface_hub import InferenceClient

import tools
import tool_schemas


# Hugging Face üzerinde kullanılacak model.
MODEL_ID = os.getenv("MODEL_ID", "openai/gpt-oss-20b")

# Tek kullanıcı turunda sonsuz tool-call döngüsünü önlemek için üst sınır.
MAX_TOOL_STEPS = 6

client = InferenceClient(api_key=os.getenv("HF_TOKEN"))


SYSTEM_PROMPT = """
Sen Kocaeli için geliştirilmiş bir Akarsu Gözlem ve Debi Uyarı Asistanısın.

Kurallar:
1. İstasyon listesi, ölçüm bilgileri, uyarı oluşturma ve mevcut uyarıları sorgulama
   işlemlerinde mutlaka sana verilen araçları kullan.
2. Veritabanından veya araç sonucundan gelmeyen hiçbir hidrolojik değeri uydurma.
3. Bir araç found=false veya success=false döndürürse işlemin başarısız olduğunu açıkça belirt.
4. Veritabanında bulunmayan bir istasyon hakkında ölçüm veya uyarı bilgisi üretme.
5. Uyarının başarıyla oluşturulduğunu yalnızca create_flow_alert veya create_flow_alerts aracı success=true döndürürse söyle.
6. Kullanıcı birden fazla işlem isterse gerekli araçları mantıklı sırayla kullan.
7. Araçlardan dönen sonuçları değiştirme veya yeni sayısal değer ekleme.
8. Konuşma geçmişini dikkate al. Kullanıcı "o istasyon", "bu uyarı" veya "az önceki ölçüm"
   gibi ifadeler kullanırsa önceki konuşmadaki bağlamı koru.
9. Kullanıcı oluşturduğu uyarıların durumunu sorarsa list_flow_alerts aracını kullan.
10. Nihai yanıtını profesyonel, kısa ve anlaşılır Türkçe ile ver.
11. Kullanıcı "tüm istasyonlar", "hepsi", "her istasyon", "her yere" veya "bütün istasyonlar" gibi toplu bir ifade kullanırsa isteği önceki konuşmada geçen tek bir istasyona daraltma.

12. Kullanıcı tüm aktif istasyonlar için aynı uyarıyı isterse create_flow_alerts aracını all_active=true ile kullan.

13. Kullanıcı birden fazla belirli istasyon için aynı uyarıyı isterse create_flow_alerts aracını station_names listesi ile kullan.

14. create_flow_alert aracını yalnızca tek bir istasyon açıkça hedeflendiğinde kullan.
""".strip()


def _arguments_to_dict(arguments):
    """Modelden gelen function arguments alanını güvenli biçimde Python dict'e çevirir."""
    if isinstance(arguments, dict):
        return arguments
    if not arguments:
        return {}
    return json.loads(arguments)


def _tool_call_to_dict(tool_call):
    """HF tool-call nesnesini konuşma geçmişine eklenebilir sözlüğe çevirir."""
    arguments = tool_call.function.arguments
    if isinstance(arguments, dict):
        arguments = json.dumps(arguments, ensure_ascii=False)

    return {
        "id": tool_call.id,
        "type": tool_call.type or "function",
        "function": {
            "name": tool_call.function.name,
            "arguments": arguments,
        },
    }


def _copy_history(conversation_history):
    """Gradio State'ten gelen geçmişi mutasyondan koruyarak kopyalar."""
    if not conversation_history:
        return []
    return [dict(message) for message in conversation_history]


def run_agent(user_message, conversation_history=None):
    """
    Bir kullanıcı turunu çalıştırır ve konuşma geçmişini bir sonraki tura taşır.

    Akış:
        Kullanıcı -> LLM -> Tool Call -> Python/SQLite -> Tool Response -> LLM

    Çıktılar:
        1. Tool-call günlüğü
        2. Kullanıcıya gösterilen yanıt/durum
        3. Güncellenmiş konuşma geçmişi (Gradio State için)
    """
    user_message = (user_message or "").strip()
    history = _copy_history(conversation_history)

    if not user_message:
        yield "", "Lütfen önce bir soru veya işlem girin.", history
        return

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {"role": "user", "content": user_message},
    ]

    log_text = "## ⚙️ Tool-Call Günlüğü\n\n"

    # Kullanıcının yeni mesajı da arayüzde hemen görünsün.
    yield log_text, "İstek analiz ediliyor...", messages[1:]

    try:
        for step in range(1, MAX_TOOL_STEPS + 1):
            response = client.chat_completion(
                model=MODEL_ID,
                messages=messages,
                tools=tool_schemas.TOOLS,
                tool_choice="auto",
                max_tokens=800,
                temperature=0.1,
            )

            assistant = response.choices[0].message
            tool_calls = assistant.tool_calls or []

            # Model artık araç çağırmıyorsa bu kullanıcı turu tamamlanmıştır.
            if not tool_calls:
                final_answer = (
                    assistant.content
                    or "İşlem tamamlandı ancak model metin yanıtı üretmedi."
                )

                messages.append({
                    "role": "assistant",
                    "content": final_answer,
                })

                log_text += (
                    f"\n✅ **Bu kullanıcı turu tamamlandı.** "
                    f"Toplam LLM adımı: {step}\n"
                )

                yield log_text, final_answer, messages[1:]
                return

            # Assistant'ın tool-call kararı tam konuşma geçmişine eklenir.
            assistant_message = {
                "role": "assistant",
                "content": assistant.content or "",
                "tool_calls": [_tool_call_to_dict(tc) for tc in tool_calls],
            }
            messages.append(assistant_message)

            log_text += f"### 🔁 Adım {step}\n\n"

            for tool_call in tool_calls:
                function_name = tool_call.function.name

                try:
                    function_args = _arguments_to_dict(tool_call.function.arguments)
                except json.JSONDecodeError:
                    function_args = {}
                    tool_result = {
                        "success": False,
                        "message": "Model araç parametrelerini geçerli JSON formatında üretemedi.",
                    }
                else:
                    tool_result = tools.execute_tool(function_name, function_args)

                log_text += (
                    f"**➡️ Tool Call:** `{function_name}`\n\n"
                    "```json\n"
                    f"{json.dumps(function_args, indent=2, ensure_ascii=False)}\n"
                    "```\n\n"
                )

                yield (
                    log_text,
                    f"`{function_name}` aracı çalıştırılıyor...",
                    messages[1:],
                )

                log_text += (
                    "**⬅️ Tool Response:**\n\n"
                    "```json\n"
                    f"{json.dumps(tool_result, indent=2, ensure_ascii=False)}\n"
                    "```\n\n"
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )

                yield (
                    log_text,
                    "Araç sonucu modele geri gönderiliyor...",
                    messages[1:],
                )

        log_text += (
            "\n⚠️ **Agent güvenlik sınırına ulaştı.** "
            f"Bir kullanıcı turunda en fazla {MAX_TOOL_STEPS} LLM/tool adımına izin veriliyor.\n"
        )
        yield (
            log_text,
            "İşlem çok fazla araç çağrısı gerektirdiği için güvenlik amacıyla durduruldu.",
            messages[1:],
        )

    except Exception as exc:
        log_text += (
            "\n### ❌ Sistem Hatası\n\n"
            "```text\n"
            f"{type(exc).__name__}: {exc}\n"
            "```\n"
        )
        yield (
            log_text,
            "Model veya Hugging Face bağlantısında bir hata oluştu.",
            history,
        )
