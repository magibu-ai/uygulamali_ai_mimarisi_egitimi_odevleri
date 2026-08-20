import phishing_rag
import ollama_client

collection = phishing_rag.get_collection(ollama_client.DEFAULT_EMBED)
print("Count:", collection.count())

hits = phishing_rag.search("Yurtiçi Kargo phishing e-posta linke tiklatma")
print(hits)
res = phishing_rag.answer_phishing("Yurtiçi Kargo phishing e-posta linke tiklatma")
print(res)
