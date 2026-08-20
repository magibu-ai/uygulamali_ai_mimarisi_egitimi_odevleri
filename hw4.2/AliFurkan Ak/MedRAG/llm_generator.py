import json
import logging
import requests
from typing import List, Dict, Any, Optional, Callable
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MedRAG.LLMGenerator")

MEDICAL_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_medical_database",
        "description": "Searches verified Turkish hospital medical articles database for medical questions, diseases, symptoms, treatments, or health advice.",
        "parameters": {
            "type": "object",
            "properties": {
                "medical_query": {
                    "type": "string",
                    "description": "Extracted medical topic search string in Turkish."
                }
            },
            "required": ["medical_query"]
        }
    }
}

INTENT_SYSTEM_PROMPT = """Sen MedRAG klinik sağlık asistanısın. Kullanıcının girdisini inceleyip aşağıdaki 3 KESİN KURALA göre karar ver:

1. KURAL (TIBBİ / SAĞLIK / İLAÇ / TEDAVİ / SEMPTOM SORULARI - KESİNLİKLE TOOL CALL YAP):
Kullanıcı herhangi bir hastalık, semptom, sağlık sorusu, tedavi, ameliyat, ilaç, ağrı, yaralanma, beslenme/diyet veya vücut sağlığı ile ilgili soru sorduğunda (Örn: 'tedavi nasıl yapılır', 'nedir', 'belirtileri nelerdir', 'ne yapmalıyım', 'ilaç kullanımı', 'parmağım kesildi', 'renk körlüğü' vb.) KESİNLİKLE 'search_medical_database' fonksiyonunu çağır. Kendi genel bilgilerinden doğrudan tıbbi yanıt VERME.

2. KURAL (GÜNLÜK SELAMLAŞMA & SOHBET):
Kullanıcı 'merhaba', 'selam', 'nasılsın', 'nasıl gidiyor', 'teşekkürler', 'iyi günler', 'sen kimsin' gibi günlük nezaket, tanışma veya sohbet ifadeleri kullandığında fonksiyon çağırma; doğrudan nazik ve yardımsever bir karşılama yanıtı ver (Örn: "Merhaba! Ben MedRAG Sağlık Asistanı. İyiyim, teşekkürler! Sağlığınızla ilgili nasıl yardımcı olabilirim?").

3. KURAL (TIBBİ DIŞI KONULAR):
Kullanıcı sağlık ve tıp DIŞINDAKİ konularda (yazılım, kodlama, yemek tarifi, siber güvenlik, spor, finans vb.) soru sorduğunda fonksiyon çağırma; KESİNLİKLE tam olarak şu standart reddetme yanıtını ver:
"Maalesef, ben yalnızca sağlık ve tıp alanında hizmet veren bir bilgi asistanıyım. Bu konuda yardımcı olamam. Sağlık alanında bir sorunuz var mıdır?"
"""

RAG_SYNTHESIS_SYSTEM_PROMPT = """Sen MedRAG uzman tıbbi bilgi asistanısın. Görevin, yalnızca aşağıda sağlanan doğrulanmış hastane makalesi pasajlarını kullanarak kullanıcının tıbbi sorusuna net, doğru ve anlaşılır bir Türkçe yanıt sentezlemektir.

KURALLAR VE TALİMATLAR:
1. YALNIZCA verilen "TIBBİ KAYNAK PASAJLARI" içeriğindeki bilgileri kullan. Pasajlarda yer almayan tıbbi iddialarda bulunma ve bilgi uydurma.
2. Yanıt içerisinde bilgi verdiğin cümlelerin sonuna ilgili kaynağın numarasını atıf olarak ekle (Örn: "...diyabet hastalarında insülin direnci görülebilir [Kaynak 1].").
3. Profesyonel, anlaşılır, düzenli ve empatik bir dil kullan.
4. Yanıtın en sonuna şu standart uyarıyı ekle:
   "⚠️ *Not: Bu yanıt doğrulanmış klinik kaynaklardan sentezlenmiş bilgilendirme amaçlı içeriktir. Kesin tanı ve tedavi için mutlaka uzman bir hekime başvurunuz.*"
"""

class LLMGenerator:
    """
    Agentic LLM Service using Ollama (Qwen2.5:7b).
    Features:
    1. Tool Calling (Function Calling) for intent detection (Medical vs Greeting vs Non-medical refusal).
    2. Grounded RAG Synthesis with inline citations ([Kaynak 1]).
    """

    def __init__(
        self,
        ollama_url: str = config.OLLAMA_URL,
        model_name: str = config.LLM_MODEL_NAME
    ):
        self.ollama_url = ollama_url.rstrip("/")
        self.model_name = model_name

    def is_available(self) -> bool:
        """Checks if Ollama service is reachable and model is available."""
        try:
            res = requests.get(f"{self.ollama_url}/api/tags", timeout=3)
            if res.status_code == 200:
                models = [m.get("name", "") for m in res.json().get("models", [])]
                return any(self.model_name in m for m in models)
        except Exception:
            pass
        return False

    def process_chat(self, user_query: str, search_executor: Callable[[str], List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Agentic Chat Processing Flow:
        Step 1: Pass query + tool definition to Qwen2.5:7b.
        Step 2: Inspect if Qwen2.5:7b emitted a tool call to 'search_medical_database'.
        - If NO Tool Call: LLM classified input as Greeting/Daily Chat or Non-Medical Refusal. Return direct LLM content without vector search.
        - If Tool Call Emitted: Execute search_executor(medical_query), then synthesize RAG answer with citations.
        """
        logger.info(f"Processing query via Agentic LLM ({self.model_name}): '{user_query}'")

        # Step 1: Initial Chat Request with Tools
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_query}
            ],
            "tools": [MEDICAL_SEARCH_TOOL],
            "stream": False,
            "options": {
                "temperature": config.LLM_TEMPERATURE
            }
        }

        try:
            res = requests.post(f"{self.ollama_url}/api/chat", json=payload, timeout=1200)
            if res.status_code != 200:
                logger.error(f"Ollama initial chat call failed status={res.status_code}: {res.text}")
                # Fallback to direct search
                return self._execute_fallback_search(user_query, search_executor)

            res_json = res.json()
            message = res_json.get("message", {})
            tool_calls = message.get("tool_calls", [])

            # Case A: No Tool Call Emitted by Ollama (Daily Greeting / Conversational Chat / Refusal)
            if not tool_calls:
                llm_response_text = message.get("content", "").strip()

                if not llm_response_text:
                    llm_response_text = "Merhaba! Ben MedRAG Sağlık Asistanı. Sağlığınızla ilgili nasıl yardımcı olabilirim?"

                logger.info(f"No tool call emitted for query '{user_query}'. Returning direct LLM response without vector search.")
                return {
                    "search_executed": False,
                    "safety_gate_triggered": False,
                    "synthesized_answer": llm_response_text,
                    "results": []
                }

            # Case B: Tool Call Triggered (Medical Question)
            tool_call = tool_calls[0]
            func_name = tool_call.get("function", {}).get("name", "")
            func_args = tool_call.get("function", {}).get("arguments", {})

            # Ensure arguments dict parsing if string
            if isinstance(func_args, str):
                try:
                    func_args = json.loads(func_args)
                except Exception:
                    func_args = {"medical_query": user_query}

            extracted_query = func_args.get("medical_query", user_query)
            logger.info(f"Agentic Tool Call Triggered: '{func_name}' with query: '{extracted_query}'")

            # Step 2: Run Vector Search + Reranker
            search_results = search_executor(extracted_query)

            # Case B1: Safety Gate Triggered (0 results / below threshold)
            if not search_results:
                logger.info("Safety Gate triggered: Search results were below similarity threshold.")
                no_source_msg = (
                    "⚠️ *Aradığınız tıbbi konuyla ilgili veritabanımızda doğrulanmış klinik kaynak bulunamamıştır. "
                    "MedRAG güvenliğiniz için kaynak kullanamadığı durumlarda yanıt üretmemektedir. "
                    "Kesin bilgi ve tedavi için lütfen bir uzman hekime başvurunuz.*"
                )
                return {
                    "search_executed": True,
                    "safety_gate_triggered": True,
                    "synthesized_answer": no_source_msg,
                    "results": []
                }

            # Case B2: Synthesize Grounded RAG Response with Citations
            synthesized_answer = self.synthesize_rag_response(user_query, search_results)

            return {
                "search_executed": True,
                "safety_gate_triggered": False,
                "synthesized_answer": synthesized_answer,
                "results": search_results
            }

        except Exception as e:
            logger.error(f"Error during agentic chat processing: {e}", exc_info=True)
            return self._execute_fallback_search(user_query, search_executor)

    def synthesize_rag_response(self, query: str, context_chunks: List[Dict[str, Any]]) -> str:
        """Synthesizes RAG Turkish response with [Kaynak N] citations from context chunks."""
        formatted_passages = []
        for idx, chunk in enumerate(context_chunks, 1):
            text = chunk.get("chunk_text", "").strip()
            url = chunk.get("url", "")
            source_info = f" [URL: {url}]" if url else ""
            formatted_passages.append(f"--- TIBBİ KAYNAK [{idx}]{source_info} ---\n{text}")

        context_str = "\n\n".join(formatted_passages)

        prompt_content = f"""KULLANICI SORUSU:
{query}

TIBBİ KAYNAK PASAJLARI:
{context_str}

Lütfen yukarıdaki tıbbi kaynak pasajlarını esas alarak kullanıcının sorusuna doğrudan ve kapsamlı bir Türkçe yanıt sentezle. Cümle sonlarında [Kaynak 1], [Kaynak 2] şeklinde atıf eklemeyi unutma."""

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": RAG_SYNTHESIS_SYSTEM_PROMPT},
                {"role": "user", "content": prompt_content}
            ],
            "stream": False,
            "options": {
                "temperature": config.LLM_TEMPERATURE
            }
        }

        try:
            res = requests.post(f"{self.ollama_url}/api/chat", json=payload, timeout=600)
            if res.status_code == 200:
                content = res.json().get("message", {}).get("content", "")
                if content:
                    return content.strip()
        except Exception as e:
            logger.error(f"RAG synthesis API call error: {e}")

        # Fallback text if synthesis fails
        return "Sorgunuzla ilgili doğrulanmış klinik kaynak pasajları aşağıda listelenmiştir."

    def _execute_fallback_search(self, query: str, search_executor: Callable[[str], List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Fallback search execution if initial Ollama LLM call fails or misses tool calling."""
        results = search_executor(query)
        if not results:
            no_source_msg = (
                "⚠️ *Aradığınız tıbbi konuyla ilgili veritabanımızda doğrulanmış klinik kaynak bulunamamıştır. "
                "MedRAG güvenliğiniz için kaynak kullanamadığı durumlarda yanıt üretmemektedir. "
                "Kesin bilgi ve tedavi için lütfen bir uzman hekime başvurunuz.*"
            )
            return {
                "search_executed": True,
                "safety_gate_triggered": True,
                "synthesized_answer": no_source_msg,
                "results": []
            }

        synthesized_answer = self.synthesize_rag_response(query, results)
        return {
            "search_executed": True,
            "safety_gate_triggered": False,
            "synthesized_answer": synthesized_answer,
            "results": results
        }
