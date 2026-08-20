"""Optional local Qwen generation that cannot bypass retrieval abstention."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from turkish_medical_vector_search.retrieval.search import SearchResult


SYSTEM_PROMPT = """Sen kaynaklara bağlı çalışan Türkçe bir tıbbi bilgi asistanısın.
Yalnızca verilen KANITLAR bölümündeki bilgileri kullan.
Kanıtlarda açıkça bulunmayan bilgiyi ekleme veya genel bilginden tamamlama.
Kısa ve doğrudan cevap ver; kullandığın kanıtları [1], [2] biçiminde belirt.
Bu sistem tanı veya tedavi önerisi vermez."""


class TextGenerator(Protocol):
    """Small interface that keeps orchestration independently testable."""

    def generate(self, *, system_prompt: str, user_prompt: str) -> str: ...


@dataclass(frozen=True)
class GeneratedAnswer:
    text: str
    answered: bool
    sources: list[dict[str, Any]]


def _build_evidence(result: SearchResult, max_context_chunks: int) -> tuple[str, list[dict]]:
    selected = result.hits[:max_context_chunks]
    blocks = []
    sources = []
    for index, hit in enumerate(selected, start=1):
        title = str(hit.metadata.get("title", "Başlıksız kaynak"))
        url = str(hit.metadata.get("url", ""))
        blocks.append(f"[{index}] Başlık: {title}\nURL: {url}\n{hit.chunk_text}")
        sources.append(
            {
                "index": index,
                "chunk_id": hit.chunk_id,
                "title": title,
                "url": url,
                "similarity": hit.similarity,
            }
        )
    return "\n\n".join(blocks), sources


def answer_from_search(
    result: SearchResult,
    generator: TextGenerator,
    *,
    max_context_chunks: int = 3,
) -> GeneratedAnswer:
    """Generate only for an accepted search result; otherwise return the exact rejection."""

    if not result.answerable:
        return GeneratedAnswer(
            text=result.message or "Bu sorunun cevabı dokümanlarımda yer almamaktadır.",
            answered=False,
            sources=[],
        )
    if max_context_chunks < 1:
        raise ValueError("max_context_chunks must be positive")

    evidence, sources = _build_evidence(result, max_context_chunks)
    user_prompt = f"KANITLAR:\n{evidence}\n\nSORU:\n{result.question}"
    text = generator.generate(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt).strip()
    return GeneratedAnswer(text=text, answered=True, sources=sources)


class LocalQwenGenerator:
    """Lazy Transformers wrapper for optional Qwen3 inference on Colab or locally."""

    def __init__(
        self,
        model_id: str = "Qwen/Qwen3-1.7B",
        *,
        load_in_4bit: bool = True,
        max_new_tokens: int = 384,
    ) -> None:
        self.model_id = model_id
        self.load_in_4bit = load_in_4bit
        self.max_new_tokens = max_new_tokens
        self._tokenizer: Any = None
        self._model: Any = None

    def _load(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        if self.load_in_4bit and not torch.cuda.is_available():
            raise RuntimeError("4-bit Qwen yüklemesi CUDA GPU gerektirir; Colab T4 kullanın.")
        quantization_config = None
        if self.load_in_4bit:
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
            )
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            device_map="auto",
            torch_dtype="auto",
            quantization_config=quantization_config,
        )

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        self._load()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        prompt = self._tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)
        output = self._model.generate(
            **inputs,
            max_new_tokens=self.max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.8,
            top_k=20,
            pad_token_id=self._tokenizer.eos_token_id,
        )
        generated_ids = output[0, inputs["input_ids"].shape[1] :]
        return self._tokenizer.decode(generated_ids, skip_special_tokens=True)
