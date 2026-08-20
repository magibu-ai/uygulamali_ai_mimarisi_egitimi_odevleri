import logging
from typing import List, Union
import requests
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OllamaEmbedder:
    """
    Embedding generator wrapping local Ollama service.
    Default model: embeddinggemma:300m (768-dimensional vectors)
    Uses mini-batching (batch_size=32) to prevent HTTP timeouts.
    """

    def __init__(
        self,
        ollama_url: str = config.OLLAMA_URL,
        model_name: str = config.MODEL_NAME,
        batch_size: int = 32,
        timeout: int = 120
    ):
        self.ollama_url = ollama_url.rstrip("/")
        self.model_name = model_name
        self.embed_endpoint = f"{self.ollama_url}/api/embed"
        self.batch_size = batch_size
        self.timeout = timeout
        self._verify_connection()

    def _verify_connection(self):
        """Verifies connection to local Ollama service and checks model availability."""
        try:
            res = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if res.status_code == 200:
                models = [m.get("name") for m in res.json().get("models", [])]
                logger.info(f"Ollama service active. Available models: {models}")
                if not any(self.model_name in m for m in models):
                    logger.warning(
                        f"Warning: Model '{self.model_name}' not found in Ollama list. "
                        f"Please run 'ollama pull {self.model_name}'."
                    )
            else:
                logger.warning(f"Ollama connection status: HTTP {res.status_code}")
        except Exception as e:
            logger.error(f"Failed to connect to Ollama ({self.ollama_url}): {e}")

    def get_embeddings(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """
        Generates embedding vectors for a string or list of text strings in mini-batches.
        """
        if isinstance(texts, str):
            input_texts = [texts]
        else:
            input_texts = texts

        if not input_texts:
            return []

        all_embeddings = []

        for i in range(0, len(input_texts), self.batch_size):
            batch = input_texts[i : i + self.batch_size]
            payload = {
                "model": self.model_name,
                "input": batch
            }

            try:
                response = requests.post(
                    self.embed_endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout
                )

                if response.status_code != 200:
                    raise RuntimeError(
                        f"Ollama API Error (Status {response.status_code}): {response.text}"
                    )

                data = response.json()
                batch_embeddings = data.get("embeddings", [])

                if not batch_embeddings:
                    raise RuntimeError("Ollama returned empty embeddings response.")

                all_embeddings.extend(batch_embeddings)

            except Exception as e:
                logger.error(f"Embedding generation error (Batch {i}-{i+len(batch)}): {e}")
                raise e

        return all_embeddings

    def get_embedding(self, text: str) -> List[float]:
        """Encodes a single search query string into a float list embedding."""
        embeddings = self.get_embeddings([text])
        return embeddings[0]


if __name__ == "__main__":
    embedder = OllamaEmbedder()
    test_text = "Medical article search and local vector storage"
    vec = embedder.get_embedding(test_text)
    print(f"Model: {embedder.model_name}")
    print(f"Text: '{test_text}'")
    print(f"Vector Dimension: {len(vec)}")
    print(f"Vector First 5 Elements: {vec[:5]}")
