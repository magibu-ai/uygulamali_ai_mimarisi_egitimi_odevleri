import os
from typing import Any, Optional

from ollama import Client as OllamaClient

from tools import TOOLS, execute_tool

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")

_ollama_client: Optional[OllamaClient] = None


def get_ollama_client() -> OllamaClient:
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient(host=OLLAMA_HOST)
    return _ollama_client


SYSTEM_PROMPT = """
Sen Yılmaz Bank'ın sanal şubesinde çalışan bir müşteri asistanısın.

MUTLAK KURALLAR:
- Hesap numarası, bakiye, işlem geçmişi, kart bilgisi, kullanıcı id'si
  gibi HİÇBİR veriyi kendi hafızandan uydurma. Bu tür her bilgi
  MUTLAKA ilgili tool çağrısından gelmelidir.
- Kullanıcı bir hesap/bakiye/kart/işlem sorduğunda, cevap vermeden ÖNCE
  mutlaka ilgili tool'u çağır.
- Tool sonucu "success": false dönerse, bu hatayı kullanıcıya doğru ve
  net şekilde ilet (yetersiz bakiye, hesap bulunamadı, para birimi
  uyuşmazlığı gibi). Hatayı gizleme veya farklıymış gibi sunma.
- Türkçe, net ve kısa cevaplar ver.

TOOL KULLANIM KURALLARI:
- find_user_by_name: kullanıcı isim/soyisim verdiğinde İLK ÖNCE bu
  çağrılır, dönen user_id ile diğer tool'lara devam edilir. Sonuç
  "count": 0 dönerse (kimse bulunamazsa), "bu isimde bir kullanıcı
  bulamadım" de — ASLA rastgele bir user_id/hesap uydurma ya da tahmin
  etme. Birden fazla eşleşme dönerse, kullanıcıya hangisini kastettiğini
  sor (soyadı, telefon gibi ayırt edici bilgi iste).
- list_accounts: kullanıcının hesaplarını görmek için (user_id gerekir).
- open_new_account: kullanıcı için yeni bir hesap açmak için. Hesap
  tipi (vadesiz/vadeli/tasarruf) ve para birimi belirtilmemişse
  kullanıcıya sor ya da makul bir varsayılan (vadesiz, TRY) kullan.
- get_balance: belirli bir hesabın güncel bakiyesi için.
- get_transaction_history: işlem geçmişi için.
- transfer_money: SADECE aynı para birimindeki hesaplar arasında.
- exchange_transfer: FARKLI para birimindeki hesaplar arasında, sabit
  demo kuruyla. Bir transfer isteğinde iki hesabın para birimi
  farklıysa, transfer_money yerine bunu kullan.
- create_card: yeni kart oluşturmak için.
- block_card: kart bloke etmek için.
- Aynı tool'u aynı argümanlarla tekrar çağırma.
- Yeterli bilgi toplandıktan sonra tool çağırmayı bırak ve cevabını ver.
 Transfer, döviz transferi, kart oluşturma/bloke etme gibi YAZMA
  işlemlerinde, sonucun başarısız olacağını düşünsen bile MUTLAKA
  ilgili tool'u çağır ve gerçek sonucu bekle. Kendi hesabına/tahminine
  güvenip tool'u atlama — "yetersiz bakiye olacak" gibi bir tahminin
  olsa bile, bunu tool'un kendisi doğrulasın.
"""


def format_currency(value: float, currency: str) -> str:
    formatted = f"{value:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} {currency}"


def build_transaction_summary(execution_trace: list[dict]) -> str:
    """
    transfer_money / exchange_transfer başarılı çağrılarından, modelin
    yazdığı metne HİÇ güvenmeden, doğrudan tool sonucundan deterministik
    bir bakiye özeti üretir. Model ne yazarsa yazsın, bu satır her zaman
    veritabanındaki gerçek sonuca dayanır.
    """
    summary_lines = []

    for turn in execution_trace:
        for call in turn.get("tool_calls", []):
            if call["tool_name"] not in ("transfer_money", "exchange_transfer"):
                continue
            if not call.get("success"):
                continue

            result = call.get("result") or {}
            from_id = result.get("from_account_id")
            to_id = result.get("to_account_id")

            if call["tool_name"] == "transfer_money":
                currency = result.get("currency", "")
                from_bal = format_currency(result.get("from_account_new_balance", 0), currency)
                to_bal = format_currency(result.get("to_account_new_balance", 0), currency)
            else:
                from_bal = format_currency(result.get("from_account_new_balance", 0), result.get("sent_currency", ""))
                to_bal = format_currency(result.get("to_account_new_balance", 0), result.get("received_currency", ""))

            summary_lines.append(f"Hesap {from_id} yeni bakiye: {from_bal} · Hesap {to_id} yeni bakiye: {to_bal}")

    if not summary_lines:
        return ""

    return "\n\n📋 İşlem özeti (veritabanından doğrudan alınmıştır):\n" + "\n".join(summary_lines)


def run_bank_agent(user_query: str, max_turns: int = 6) -> dict:
    client = get_ollama_client()

    messages: list[Any] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]

    execution_trace: list[dict] = []
    used_tools: set[str] = set()
    any_tool_called = False

    for turn_number in range(1, max_turns + 1):
        response = client.chat(
            model=MODEL_NAME,
            messages=messages,
            tools=TOOLS,
            think=True,
            options={"temperature": 0.1, "num_predict": 1800},
        )

        response_message = response.message
        content = response_message.content or ""
        model_thinking = (getattr(response_message, "thinking", None) or "").strip() or None
        tool_calls = response_message.tool_calls or []

        turn_trace = {"turn": turn_number, "thinking": model_thinking, "tool_calls": []}

        assistant_message: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            assistant_message["tool_calls"] = [
                {"function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in tool_calls
            ]
        messages.append(assistant_message)

        if not tool_calls:
            execution_trace.append(turn_trace)
            break

        any_tool_called = True

        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            arguments = tool_call.function.arguments or {}
            execution_result = execute_tool(tool_name=tool_name, arguments=arguments)

            if execution_result.get("success"):
                used_tools.add(tool_name)

            turn_trace["tool_calls"].append({
                "tool_name": tool_name,
                "arguments": arguments,
                "success": execution_result.get("success", False),
                "result": execution_result.get("result"),
                "error": execution_result.get("error"),
            })

            import json
            messages.append({
                "role": "tool",
                "tool_name": tool_name,
                "content": json.dumps(execution_result, ensure_ascii=False, default=str),
                "is_error": not execution_result.get("success", False),
            })

        execution_trace.append(turn_trace)

    last_assistant_message = next(
        (m for m in reversed(messages) if m["role"] == "assistant"),
        None,
    )
    final_answer = (last_assistant_message or {}).get("content") or ""

    if not final_answer and execution_trace:
        last_thinking = execution_trace[-1].get("thinking")
        if last_thinking:
            final_answer = last_thinking

    if not final_answer:
        final_answer = "Bir cevap üretilemedi."

    transaction_summary = build_transaction_summary(execution_trace)
    if transaction_summary:
        final_answer = final_answer + transaction_summary

    hallucination_risk = not any_tool_called

    return {
        "answer": final_answer,
        "used_tools": sorted(used_tools),
        "hallucination_risk": hallucination_risk,
        "trace": execution_trace,
    }