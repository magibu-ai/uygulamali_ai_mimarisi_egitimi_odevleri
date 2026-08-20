"""Agentic RAG pipeline: sorguyu düzeltir, hybrid retrieval ile bağlam toplar, yetmezse sorguyu yeniden yazıp tekrar dener."""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

import db
import explain
from embedder import embed_query

load_dotenv()

_client = OpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
)
_MODEL = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")

REFUSAL_MESSAGE = (
    "Bu soruyu elimdeki bilgilerle güvenilir şekilde cevaplayamıyorum. "
    "Farklı bir şey sorar mısın?"
)


def _chat(system, user, *, json_mode=False):
    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = _client.chat.completions.create(
        model=_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
        **kwargs,
    )
    return resp.choices[0].message.content.strip()


def rewrite_query(question: str) -> str:
    system = (
        "Sen bir arama sorgusu düzenleyicisisin. Kullanıcının Türkçe sorusunu "
        "al; yazım hatalarını düzelt, konuşma dilini/argoyu ansiklopedik ve "
        "nötr bir arama ifadesine çevir, gereksiz kelimeleri at. Sadece "
        "düzeltilmiş sorguyu tek satır olarak döndür, başka hiçbir şey yazma."
    )
    rewritten = _chat(system, question)
    return rewritten.strip().strip('"')


def _reciprocal_rank_fusion(result_lists, k=60):
    """Birden fazla sıralı sonuç listesini RRF ile tek bir sıralamaya birleştirir."""
    scores = {}
    rows_by_id = {}
    for results in result_lists:
        for rank, row in enumerate(results):
            scores[row["id"]] = scores.get(row["id"], 0.0) + 1.0 / (k + rank + 1)
            rows_by_id[row["id"]] = row
    ranked_ids = sorted(scores, key=scores.get, reverse=True)
    return [rows_by_id[rid] for rid in ranked_ids]


def retrieve(query: str, k_dense=15, k_sparse=15, top_parents=4, verbose=False):
    """Hybrid child retrieval + parent'a genişletme. Context blok listesi döner."""
    query_vector = embed_query(query)
    dense_hits = db.dense_search(query_vector, k=k_dense)
    sparse_hits = db.sparse_search(query, k=k_sparse)
    fused_children = _reciprocal_rank_fusion([dense_hits, sparse_hits])

    if verbose:
        explain.print_dense_results(query, dense_hits)
        explain.print_sparse_results(query, sparse_hits)
        explain.print_fusion_results(fused_children, dense_hits, sparse_hits)

    parent_ids_in_order = []
    seen = set()
    for child in fused_children:
        pid = child["parent_chunk_id"]
        if pid and pid not in seen:
            seen.add(pid)
            parent_ids_in_order.append(pid)
        if len(parent_ids_in_order) >= top_parents:
            break

    parents = db.get_parent_chunks(parent_ids_in_order)
    documents = db.get_documents(p["document_id"] for p in parents.values())

    blocks = []
    for pid in parent_ids_in_order:
        parent = parents.get(pid)
        if not parent:
            continue
        doc = documents.get(parent["document_id"], {})
        blocks.append(
            {
                "title": doc.get("title", "Bilinmeyen Başlık"),
                "source_url": doc.get("source_url", ""),
                "text": parent["text"],
            }
        )
    if verbose:
        explain.print_selected_parents(blocks)
    return blocks


def judge_and_answer(question: str, context_blocks: list) -> dict:
    system = (
        "Sen sadece verilen bağlamı kullanarak cevap veren bir Türkçe "
        "asistansın. Bağlamda yer almayan hiçbir bilgiyi uydurma, tahmin "
        "yürütme. Bağlam soruyu cevaplamaya yetiyorsa cevabı bağlamdaki "
        "bilgiye dayanarak yaz. Yetmiyorsa 'not_found' durumunu döndür ve "
        "eksik bilgiyi bulmak için denenebilecek, sorudan farklı açıdan "
        "yazılmış (daha spesifik ya da daha genel) bir arama sorgusu öner. "
        "SADECE şu JSON şemasıyla cevap ver, başka hiçbir metin ekleme: "
        '{"status": "answered" | "not_found", "answer": string|null, '
        '"reformulated_query": string|null}'
    )
    context_text = "\n\n".join(
        f"[{i + 1}] Başlık: {b['title']} ({b['source_url']})\n{b['text']}"
        for i, b in enumerate(context_blocks)
    ) or "(bağlam boş — hiç ilgili chunk bulunamadı)"
    user = f"Soru: {question}\n\nBağlam:\n{context_text}"
    raw = _chat(system, user, json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {"status": "not_found", "answer": None, "reformulated_query": None}


def run(question: str, max_attempts: int = 3, verbose: bool = False) -> dict:
    """Tüm pipeline'ı çalıştırır. Trace ile birlikte final sonucu döner."""
    trace = []
    query = rewrite_query(question)

    for attempt in range(1, max_attempts + 1):
        if verbose:
            explain.print_attempt_header(attempt, max_attempts, query)
        context_blocks = retrieve(query, verbose=verbose)
        result = judge_and_answer(question, context_blocks)
        if verbose:
            explain.print_judge_verdict(result)
        trace.append(
            {
                "attempt": attempt,
                "query": query,
                "sources": [b["title"] for b in context_blocks],
                "status": result.get("status"),
            }
        )

        if result.get("status") == "answered" and result.get("answer"):
            outcome = {"status": "answered", "answer": result["answer"], "trace": trace}
            if verbose:
                explain.print_final(outcome)
            return outcome

        next_query = result.get("reformulated_query")
        if not next_query or next_query == query:
            break
        query = next_query

    outcome = {"status": "refused", "answer": REFUSAL_MESSAGE, "trace": trace}
    if verbose:
        explain.print_final(outcome)
    return outcome


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "Kapadokya hangi ilde yer alır?"
    out = run(q, verbose=True)
    print(json.dumps(out, ensure_ascii=False, indent=2))
