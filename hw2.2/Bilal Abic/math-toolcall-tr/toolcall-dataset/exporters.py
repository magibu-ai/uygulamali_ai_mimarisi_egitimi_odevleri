"""Veri setini OpenAI ve Gemini egitim formatlarina cevirir."""
import json

SYSTEM_TEXT = (
    "Sen araclari kullanabilen bir asistansin. Gerektiginde uygun fonksiyonu dogru "
    "parametrelerle cagir, donen sonucu kullaniciya net ve dogal bir dille acikla."
)


def valid_tools(rec: dict) -> list[dict]:
    """Sadece duzgun sekilli arac semalarini dondur.

    Model nadiren bozuk JSON uretip listeye ham string parcasi birakabiliyor;
    bu girdiler export'u cokertmesin diye burada elenir.
    """
    return [
        t for t in rec.get("tools", [])
        if isinstance(t, dict) and isinstance(t.get("function"), dict)
    ]


def _meta(rec: dict) -> dict:
    return {
        "id": rec["id"],
        "domain": rec["domain"],
        "topic": rec["topic"],
        "scenario": rec["scenario"],
        "difficulty": rec["difficulty"],
        "thinking": rec["thinking"],
        "question_provider": rec["question_provider"],
        "question_model": rec["question_model"],
        "answer_provider": rec["answer_provider"],
        "answer_model": rec["answer_model"],
    }


def to_openai(rec: dict, inline_thinking: bool = False) -> dict:
    """OpenAI chat / fine-tuning formati."""
    messages = [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": rec["question"]},
    ]

    calls = rec.get("tool_calls") or []
    if calls:
        tool_calls, results = [], rec.get("tool_results") or []
        for i, call in enumerate(calls):
            tool_calls.append(
                {
                    "id": f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": json.dumps(call.get("arguments", {}), ensure_ascii=False),
                    },
                }
            )
        messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
        for i, call in enumerate(calls):
            result = results[i]["result"] if i < len(results) else {}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": f"call_{i}",
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    answer = rec["answer"]
    if inline_thinking:
        answer = f"<think>\n{rec['thinking']}\n</think>\n\n{answer}"
    messages.append({"role": "assistant", "content": answer})

    return {"messages": messages, "tools": valid_tools(rec), "metadata": _meta(rec)}


def to_gemini(rec: dict, inline_thinking: bool = False) -> dict:
    """Gemini contents / functionDeclarations formati."""
    declarations = [t["function"] for t in valid_tools(rec)]
    contents = [{"role": "user", "parts": [{"text": rec["question"]}]}]

    calls = rec.get("tool_calls") or []
    if calls:
        results = rec.get("tool_results") or []
        contents.append(
            {
                "role": "model",
                "parts": [
                    {"functionCall": {"name": c["name"], "args": c.get("arguments", {})}}
                    for c in calls
                ],
            }
        )
        contents.append(
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "name": c["name"],
                            "response": results[i]["result"] if i < len(results) else {},
                        }
                    }
                    for i, c in enumerate(calls)
                ],
            }
        )

    answer = rec["answer"]
    if inline_thinking:
        answer = f"<think>\n{rec['thinking']}\n</think>\n\n{answer}"
    contents.append({"role": "model", "parts": [{"text": answer}]})

    return {
        "systemInstruction": {"parts": [{"text": SYSTEM_TEXT}]},
        "tools": [{"functionDeclarations": declarations}],
        "contents": contents,
        "metadata": _meta(rec),
    }


def to_chat(rec: dict) -> list[dict]:
    """Sohbet formati: content / images / role / thinking / tool_calls alanlari.

    Iki mesaj uretir. Arac cagrilari ve sonuclari asistan mesajinin tool_calls
    alaninda birlikte durur; arac cagrilmadiysa alan null olur.
    """
    results = rec.get("tool_results") or []
    calls = [
        {
            "name": c["name"],
            "arguments": c.get("arguments", {}),
            "result": results[i]["result"] if i < len(results) else None,
        }
        for i, c in enumerate(rec.get("tool_calls") or [])
    ]
    return [
        {
            "content": rec["question"],
            "images": None,
            "role": "user",
            "thinking": None,
            "tool_calls": None,
        },
        {
            "content": rec["answer"],
            "images": None,
            "role": "assistant",
            "thinking": rec["thinking"],
            "tool_calls": calls or None,
        },
    ]


def to_sharegpt(rec: dict, with_thinking: bool = True) -> dict:
    """Unsloth / ShareGPT formati: {"conversations": [{"from","value"}, ...]}.

    standardize_data_formats bunu role/content'e cevirir, ardindan Gemma-4 chat
    template uygulanir. Cok-turlu kurgu (tool_calls varsa):
        human : soru
        gpt   : <think>...</think> + <tool_call>...</tool_call>   (loss burada)
        human : <tool_response>...</tool_response>                (maskeli)
        gpt   : dogal dille son cevap                             (loss burada)
    Arac cagrilmayan orneklerde tek gpt turu: <think> + cevap.
    """
    think = (rec.get("thinking") or "").strip()
    calls = rec.get("tool_calls") or []
    results = rec.get("tool_results") or []

    convos: list[dict] = [{"from": "human", "value": rec["question"]}]

    if calls:
        call_lines = "\n".join(
            "<tool_call>"
            + json.dumps({"name": c["name"], "arguments": c.get("arguments", {})},
                         ensure_ascii=False)
            + "</tool_call>"
            for c in calls
        )
        first = f"<think>\n{think}\n</think>\n\n{call_lines}" if (with_thinking and think) else call_lines
        convos.append({"from": "gpt", "value": first})

        resp_lines = "\n".join(
            "<tool_response>"
            + json.dumps(results[i]["result"] if i < len(results) else {}, ensure_ascii=False)
            + "</tool_response>"
            for i in range(len(calls))
        )
        convos.append({"from": "human", "value": resp_lines})
        convos.append({"from": "gpt", "value": rec["answer"]})
    else:
        value = f"<think>\n{think}\n</think>\n\n{rec['answer']}" if (with_thinking and think) else rec["answer"]
        convos.append({"from": "gpt", "value": value})

    return {"conversations": convos}


def write_jsonl(path, rows) -> int:
    with open(path, "w", encoding="utf-8") as fh:
        count = 0
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count
