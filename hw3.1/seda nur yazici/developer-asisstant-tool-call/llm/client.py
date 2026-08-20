from types import SimpleNamespace
from typing import Any

from huggingface_hub import InferenceClient

from config import HF_MODEL, HF_PROVIDER, HF_TOKEN


class LLMClient:
    """
    Hugging Face Inference Providers üzerinden sohbet tamamlama
    ve structured output üretir.
    Dönen veri yapısı eski Ollama istemcisiyle uyumludur:
        response.message.content
        response.message.thinking
    """

    def __init__(self) -> None:
        if not HF_TOKEN:
            raise RuntimeError(
                "HF_TOKEN bulunamadı. Hugging Face Space ayarlarında "
                "HF_TOKEN adında bir Secret oluşturun."
            )

        self.client = InferenceClient(
            provider=HF_PROVIDER,
            api_key=HF_TOKEN,
            timeout=90,
        )

        self.model = HF_MODEL

    @staticmethod
    def _create_response(
        content: str,
        thinking: str = "",
    ) -> SimpleNamespace:
        return SimpleNamespace(
            message=SimpleNamespace(
                content=content,
                thinking=thinking,
            )
        )

    def _chat_completion(
        self,
        request_kwargs: dict[str, Any],
    ) -> Any:
        """
        Planner için JSON Schema kullanır.
        Responder için standart chat completion çağrısı yapar.
        """

        schema = request_kwargs.pop("_schema", None)

        try:
            if schema is not None:
                request_kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "ToolPlan",
                        "schema": schema,
                        "strict": True,
                    },
                }

            return self.client.chat_completion(
                **request_kwargs
            )

        except Exception as exc:
            call_type = (
                "structured output"
                if schema is not None
                else "standart chat completion"
            )

            raise RuntimeError(
                "Hugging Face LLM çağrısı başarısız oldu.\n"
                f"Çağrı türü: {call_type}\n"
                f"Model: {self.model}\n"
                f"Provider: {HF_PROVIDER}\n"
                f"Hata türü: {type(exc).__name__}\n"
                f"Hata: {repr(exc)}"
            ) from exc

    def generate(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any] | None = None,
        think: bool = True,
    ) -> SimpleNamespace:
        """
        Modele mesaj gönderir.
        `think` parametresi Planner ve Responder kodlarıyla
        geriye dönük uyumluluk amacıyla korunmaktadır.
        """

        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 1024,
            "_schema": schema,
        }

        response = self._chat_completion(
            request_kwargs=request_kwargs,
        )

        choices = getattr(response, "choices", None)

        if not choices:
            raise RuntimeError(
                "Hugging Face modeli boş bir choices listesi döndürdü."
            )

        message = getattr(choices[0], "message", None)

        if message is None:
            raise RuntimeError(
                "Hugging Face yanıtında message alanı bulunamadı."
            )

        content = getattr(message, "content", None)

        if content is None:
            raise RuntimeError(
                "Hugging Face yanıtında content alanı boş döndü."
            )

        if not isinstance(content, str):
            content = str(content)

        content = content.strip()

        if not content:
            raise RuntimeError(
                "Hugging Face modeli boş metin döndürdü."
            )

        return self._create_response(
            content=content,
            thinking="",
        )


llm = LLMClient()