import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from llm.client import llm


ROOT_DIR = Path(__file__).resolve().parent.parent

RESPONDER_PROMPT_PATH = (
    ROOT_DIR
    / "prompts"
    / "responder_prompt.txt"
)

RESPONDER_PROMPT = RESPONDER_PROMPT_PATH.read_text(
    encoding="utf-8"
)


def _serialize_tool_results(
    tool_results: list[Any],
) -> str:
    """
    Tool sonuçlarını LLM'e gönderilecek JSON metnine dönüştürür.
    """

    serializable_results = []

    for result in tool_results:
        if isinstance(result, BaseModel):
            serializable_results.append(
                result.model_dump(mode="json")
            )
        elif isinstance(result, dict):
            serializable_results.append(result)
        else:
            serializable_results.append(
                {
                    "value": str(result)
                }
            )

    return json.dumps(
        serializable_results,
        indent=2,
        ensure_ascii=False,
        default=str,
    )


def _remove_thinking_text(answer: str) -> str:
    """
    Model cevabına sızabilecek düşünme bloklarını temizler.
    """

    cleaned_answer = answer.strip()

    cleaned_answer = re.sub(
        r"<think>.*?</think>",
        "",
        cleaned_answer,
        flags=re.DOTALL | re.IGNORECASE,
    )

    if "</think>" in cleaned_answer.lower():
        parts = re.split(
            r"</think>",
            cleaned_answer,
            maxsplit=1,
            flags=re.IGNORECASE,
        )

        if len(parts) == 2:
            cleaned_answer = parts[1]

    return cleaned_answer.strip()


def generate_response(
    user_message: str,
    tool_results: list[Any],
) -> str:
    """
    Kullanıcının sorusunu ve tool sonuçlarını kullanarak
    doğal dilde nihai cevap üretir.
    """

    if not user_message.strip():
        raise ValueError(
            "Kullanıcı mesajı boş olamaz."
        )

    tool_results_json = _serialize_tool_results(
        tool_results
    )

    messages = [
        {
            "role": "system",
            "content": RESPONDER_PROMPT,
        },
        {
            "role": "user",
            "content": (
                "Kullanıcının sorusu:\n\n"
                f"{user_message}\n\n"
                "Tool sonuçları (JSON):\n\n"
                f"{tool_results_json}"
            ),
        },
    ]

    print("🧠 Responder LLM çağrısı başlıyor...", flush=True)

    try:
        response = llm.generate(
            messages=messages,
            think=False,
        )
    except Exception as exc:
        print(
            f"❌ Responder LLM çağrısı başarısız: {repr(exc)}",
            flush=True,
        )
        raise RuntimeError(
            f"Responder LLM çağrısı başarısız oldu: {exc}"
        ) from exc
    
    print("✅ Responder LLM cevabı alındı.", flush=True)

    answer = response.message.content

    if not answer or not answer.strip():
        raise RuntimeError(
            "Responder boş bir cevap döndürdü."
        )

    cleaned_answer = _remove_thinking_text(answer)

    if not cleaned_answer:
        raise RuntimeError(
            "Responder cevabı temizlendikten sonra boş kaldı."
        )

    return cleaned_answer