"""
llm.py — Colab'da çalışan LLM'e HTTP isteği gönderen wrapper.

Colab notebook'ta Gemma 4 E4B modeli Flask/FastAPI endpoint'i olarak çalışır.
Bu modül o endpoint'e istek gönderir.
Colab bağlantısı yoksa fallback olarak sadece context'i döndürür.
"""

import os
import logging
from typing import List, Dict, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Colab LLM endpoint URL'i (.env'den veya environment'tan)
DEFAULT_COLAB_URL = os.environ.get(
    "COLAB_LLM_URL", "http://localhost:5000/generate"
)

# Prompt template — sadece context'e dayanarak cevap üretme talimatı
SYSTEM_PROMPT = """Sen bir Türkçe tıbbi bilgi asistanısın. Sana verilen bağlam (context) bilgilerine dayanarak soruyu cevapla.

KESİNLİKLE UYULMASI GEREKEN KURALLAR:
1. SADECE verilen bağlam bilgilerini kullan.
2. Bağlamda olmayan bilgileri UYDURMA.
3. Emin olmadığın konularda "Bu bilgi verilen kaynaklarda yer almamaktadır" de.
4. Cevabını Türkçe olarak ver.
5. Tıbbi bilgileri doğru ve anlaşılır şekilde aktar."""

USER_PROMPT_TEMPLATE = """Bağlam (Context):
{context}

Soru: {question}

Yukarıdaki bağlam bilgilerine dayanarak soruyu cevapla:"""


def format_context(chunks: List[Dict]) -> str:
    """
    Chunk listesini LLM'e verilecek context string'ine dönüştürür.

    Args:
        chunks: Retriever'dan gelen chunk listesi.

    Returns:
        str: Formatlanmış context metni.
    """
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        title = chunk.get("metadata", {}).get("title", "Başlıksız")
        text = chunk.get("text", "")
        score = chunk.get("score", 0.0)
        context_parts.append(
            f"[Kaynak {i}] (Başlık: {title}, Benzerlik: {score:.2f})\n{text}"
        )
    return "\n\n---\n\n".join(context_parts)


def build_prompt(context: str, question: str) -> str:
    """
    LLM için prompt oluşturur.

    Args:
        context: Formatlanmış context metni.
        question: Kullanıcı sorusu.

    Returns:
        str: Tam prompt.
    """
    return USER_PROMPT_TEMPLATE.format(context=context, question=question)


def generate_answer(
    chunks: List[Dict],
    question: str,
    colab_url: Optional[str] = None,
    timeout: int = 120,
) -> Dict:
    """
    Context chunk'ları ve soru ile LLM'den cevap üretir.

    Args:
        chunks: Retriever'dan gelen chunk listesi.
        question: Kullanıcı sorusu.
        colab_url: Colab LLM endpoint URL'i. None ise varsayılan kullanılır.
        timeout: HTTP istek timeout süresi (saniye).

    Returns:
        Dict: {"answer": str, "prompt": str, "source": str}
    """
    if colab_url is None:
        colab_url = DEFAULT_COLAB_URL

    context = format_context(chunks)
    prompt = build_prompt(context, question)

    # Colab endpoint'ine istek gönder
    try:
        logger.info(f"Colab LLM'e istek gönderiliyor: {colab_url}")

        response = requests.post(
            colab_url,
            json={
                "prompt": prompt,
                "system_prompt": SYSTEM_PROMPT,
                "max_new_tokens": 1024,
                "temperature": 0.3,
                "top_p": 0.9,
            },
            timeout=timeout,
        )

        if response.status_code == 200:
            result = response.json()
            answer = result.get("response", result.get("answer", ""))
            logger.info("Colab LLM cevap üretti.")
            return {
                "answer": answer,
                "prompt": prompt,
                "source": "colab_gemma",
            }
        else:
            logger.warning(
                f"Colab LLM hata döndürdü: {response.status_code} - {response.text}"
            )

    except requests.exceptions.ConnectionError:
        logger.warning(
            "Colab LLM endpoint'ine bağlanılamadı. "
            "Colab notebook'un çalıştığından ve tunnel'ın açık olduğundan emin olun."
        )
    except requests.exceptions.Timeout:
        logger.warning(f"Colab LLM isteği zaman aşımına uğradı ({timeout}s).")
    except Exception as e:
        logger.warning(f"Colab LLM isteğinde beklenmeyen hata: {e}")

    # Fallback: Colab bağlantısı yoksa context'i döndür
    logger.info("Fallback modu: Sadece retrieval sonuçları döndürülüyor.")
    fallback_answer = (
        "⚠️ Colab LLM bağlantısı kurulamadı. "
        "Aşağıda retrieval sonuçları (ilgili metin parçaları) listelenmiştir:\n\n"
    )
    for i, chunk in enumerate(chunks, 1):
        title = chunk.get("metadata", {}).get("title", "Başlıksız")
        fallback_answer += f"📄 Kaynak {i}: {title}\n{chunk['text'][:300]}...\n\n"

    return {
        "answer": fallback_answer,
        "prompt": prompt,
        "source": "fallback_context_only",
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("=" * 60)
    print("LLM Modülü — Test")
    print("=" * 60)

    # Örnek chunk'lar ile test
    test_chunks = [
        {
            "text": "Diyabet, kan şekeri seviyelerinin normalin üzerinde olduğu kronik bir hastalıktır.",
            "metadata": {"title": "Diyabet Nedir?"},
            "score": 0.85,
        }
    ]

    result = generate_answer(test_chunks, "Diyabet nedir?")
    print(f"\nKaynak: {result['source']}")
    print(f"Cevap:\n{result['answer'][:500]}")
