"""Phase 5: build the official 30-question benchmark (20 positive, 10 negative).

The benchmark is DETERMINISTIC and model-free: positive evidence is located in
the real chunks via a whitespace-tolerant regex (so the stored evidence is an
exact excerpt of the referenced chunk), and negative topics are verified to have
zero lexical presence in the corpus. Semantic verification (ChromaDB) is a
separate audit step: scripts/verify_benchmark.py.

Writes the frozen, tracked file: data/benchmark/benchmark.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import load_config, resolve_path  # noqa: E402

BENCHMARK_VERSION = "1.0"

# (id, question, parent_id, locator) — locator is an answer-bearing clause that
# exists in one of the parent's chunks (matched whitespace-tolerantly).
POSITIVES = [
    ("pos_001", "Anemi nedir ve neden ortaya çıkar?", "doc_00000",
     "oksijen taşıyan kırmızı kan hücrelerinin eksikliğinde ortaya çıkan durumdur"),
    ("pos_002", "Hepatit virüsünün kaç ana türü vardır?", "doc_00001",
     "A, B, C, D ve E tipleri olarak adlandırılan beş ana türü vardır"),
    ("pos_003", "Çölyak hastalığı hangi proteine karşı gelişen bir hassasiyettir?", "doc_00018",
     "gluten adlı proteine karşı, ömür boyu süren ve kronikleşen"),
    ("pos_004", "Antibiyotikler bakterilere karşı nasıl etki eder?", "doc_00072",
     "doğrudan öldürerek (bakterisidal) ya da çoğalmalarını engelleyerek (bakteriyostatik)"),
    ("pos_005", "Bulimia nervozada kilo almamak için hangi telafi edici davranışlara başvurulur?", "doc_00078",
     "kusma, aşırı egzersiz veya laksatif kullanımı gibi telafi edici davranışlara"),
    ("pos_006", "İyot eksikliği tiroid bezinde hangi sorunlara yol açar?", "doc_00085",
     "tiroid bezinde büyüme (guatr) ve hipotiroidizm gibi sağlık sorunlarına yol açabilir"),
    ("pos_007", "Vaskülit bağışıklık sistemiyle nasıl bir ilişki sonucu ortaya çıkar?", "doc_00109",
     "bağışıklık sisteminin yanlışlıkla kan damarlarına saldırmasıyla ortaya çıkar"),
    ("pos_008", "Veba hastalığı insanlara başlıca nasıl bulaşır?", "doc_00110",
     "esas olarak pireler yoluyla bulaşan ve çok kısa süre içerisinde ölüme yol açabilecek"),
    ("pos_009", "Kıl kurdunun bilimsel (tıbbi) adı nedir?", "doc_00120",
     "Enterobius vermicularis adıyla da bilinen bu parazit"),
    ("pos_010", "D vitamini eksikliği hangi hastalıklara yol açabilir?", "doc_00123",
     "osteoporoz, raşitizm, kalp hastalıkları ve bağışıklık sistemi problemleri"),
    ("pos_011", "Kadınlarda ikinci en sık ölüme neden olan kanser türü hangisidir?", "doc_00142",
     "kadınlarda ikinci en sık ölüme neden olan kanser türü ise meme kanseridir"),
    ("pos_012", "Yetişkinlerde normal kalp ritmi dakikada kaç atımdır?", "doc_00151",
     "Normal kalp ritmi yetişkinler için dakika 60-100 atım arasında değişkenlik gösterir"),
    ("pos_013", "Zatürre (pnömoni) en çok hangi gruplarda görülür?", "doc_00165",
     "okul öncesi dönemdeki (5 yaş altı) çocuklarda, 65 yaş üstü erişkinlerde"),
    ("pos_014", "HIV vücutta hangi sisteme saldırır?", "doc_00166",
     "bağışıklık sistemine saldırarak vücut direncini düşüren bir enfeksiyondur"),
    ("pos_015", "Koklear implant işitmeyi nasıl sağlar?", "doc_00174",
     "işitme sinirini doğrudan uyararak çalışırlar"),
    ("pos_016", "Kuduz hastalığı insana nasıl bulaşır?", "doc_00180",
     "vahşi hayvanlardan insanlara ısırık veya tükürük yoluyla bulaşır"),
    ("pos_017", "Kistik fibrozis nasıl bir hastalıktır?", "doc_00198",
     "Genetik bir bozukluk olan kistik fibrozis hastalığında salgı bezlerinin görevini tam olarak yerine getirememesine"),
    ("pos_018", "En sık görülen demans türü hangisidir?", "doc_00214",
     "En sık görülen demans Alzheimer hastalığıdır"),
    ("pos_019", "Varikosel nedir ve nasıl oluşur?", "doc_00217",
     "testis torbasında yer alan kanı boşaltmakla görevli toplardamarların genişlemesi"),
    ("pos_020", "Karbonmonoksit zehirlenmesi nedir?", "doc_00251",
     "renksiz ve kokusuz bir gaz olan karbonmonoksitin solunmasından kaynaklanan ölümcül bir durumdur"),
]

# (id, question, target_topic, keywords-to-prove-absence)
NEGATIVES = [
    ("neg_001", "Ebola virüsü hastalığı nasıl bulaşır ve belirtileri nelerdir?",
     "Ebola virüs hastalığı", ["ebola"]),
    ("neg_002", "Kolera hastalığının belirtileri ve tedavisi nelerdir?",
     "Kolera", ["kolera"]),
    ("neg_003", "Şarbon (antraks) hastalığı insana nasıl bulaşır?",
     "Şarbon / antraks", ["şarbon", "anthrax"]),
    ("neg_004", "Kabakulak hastalığının belirtileri nelerdir?",
     "Kabakulak (parotit)", ["kabakulak"]),
    ("neg_005", "Kırım-Kongo kanamalı ateşi nasıl bulaşır?",
     "Kırım-Kongo kanamalı ateşi", ["kırım kongo", "kkka"]),
    ("neg_006", "Huntington hastalığı nedir ve belirtileri nelerdir?",
     "Huntington hastalığı", ["huntington"]),
    ("neg_007", "Renk körlüğü neden olur ve nasıl teşhis edilir?",
     "Renk körlüğü (renk görme kusuru)", ["renk körlüğü"]),
    ("neg_008", "Narkolepsi hastalığının belirtileri nelerdir?",
     "Narkolepsi", ["narkolepsi"]),
    ("neg_009", "Kekemelik neden olur ve nasıl tedavi edilir?",
     "Kekemelik (konuşma bozukluğu)", ["kekemelik"]),
    ("neg_010", "Kleptomani nedir ve nasıl tedavi edilir?",
     "Kleptomani", ["kleptomani"]),
]


def _load_chunks(path: Path):
    by_parent = defaultdict(list)
    by_id = {}
    for line in open(path, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            by_parent[r["parent_id"]].append(r)
            by_id[r["chunk_id"]] = r
    return by_parent, by_id


def _locate(parent_chunks: list[dict], locator: str) -> tuple[dict, str]:
    pattern = re.compile(r"\s+".join(re.escape(tok) for tok in locator.split()))
    for chunk in parent_chunks:
        m = pattern.search(chunk["chunk_text"])
        if m:
            return chunk, m.group(0)
    raise SystemExit(
        f"ABORT: locator not found in {parent_chunks[0]['parent_id']}: {locator!r}"
    )


def main() -> None:
    config = load_config()
    chunks_path = resolve_path(config["chunking"]["chunks_output"])
    by_parent, _ = _load_chunks(chunks_path)

    corpus_blob = "\n".join(
        c["chunk_text"] for cs in by_parent.values() for c in cs
    ).casefold()
    n_docs = len({c["parent_id"] for cs in by_parent.values() for c in cs})
    n_chunks = sum(len(cs) for cs in by_parent.values())

    questions = []

    # --- positives ---
    for qid, question, parent_id, locator in POSITIVES:
        chunk, evidence = _locate(by_parent[parent_id], locator)
        questions.append({
            "id": qid,
            "question": question,
            "type": "positive",
            "expected_chunk_ids": [chunk["chunk_id"]],
            "expected_parent_ids": [parent_id],
            "expected_urls": [chunk["url"]],
            "title": chunk["title"],
            "source": chunk["source"],
            "evidence": evidence,
            "verification": {
                "answer_present": True,
                "evidence_is_exact_excerpt": True,
                "method": "exact evidence excerpt located in the referenced chunk",
            },
        })

    # --- negatives (lexical absence proof) ---
    for qid, question, topic, keywords in NEGATIVES:
        hits = {k: corpus_blob.count(k.casefold()) for k in keywords}
        total = sum(hits.values())
        if total != 0:
            raise SystemExit(
                f"ABORT: negative {qid} topic present in corpus (hits={hits})"
            )
        questions.append({
            "id": qid,
            "question": question,
            "type": "negative",
            "target_topic": topic,
            "expected_chunk_ids": [],
            "expected_parent_ids": [],
            "expected_urls": [],
            "verification": {
                "answer_present": False,
                "method": "lexical corpus keyword scan (0 hits) + "
                          "semantic ChromaDB top-5 inspection (see verify_benchmark.py)",
                "lexical_keywords": keywords,
                "lexical_hits": total,
            },
        })

    benchmark = {
        "metadata": {
            "benchmark_version": BENCHMARK_VERSION,
            "dataset_name": config["dataset"]["name"],
            "selected_document_count": n_docs,
            "chunk_count": n_chunks,
            "embedding_model": config["embedding"]["model_name"],
            "positive_count": sum(q["type"] == "positive" for q in questions),
            "negative_count": sum(q["type"] == "negative" for q in questions),
            "total_count": len(questions),
            "methodology": (
                "Positives: authored questions grounded in the selected corpus; "
                "each answer verified as an exact evidence excerpt in a specific "
                "chunk. Negatives: realistic medical questions on topics with zero "
                "lexical presence in the corpus, further confirmed unanswerable by "
                "ChromaDB semantic retrieval inspection. Diagnostic pilot queries "
                "are intentionally excluded."
            ),
        },
        "questions": questions,
    }

    out_path = resolve_path(config["paths"]["data_benchmark"]) / "benchmark.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(benchmark, handle, ensure_ascii=False, indent=2)

    print(f"Wrote {out_path}")
    print(f"  docs={n_docs} chunks={n_chunks} "
          f"positives={benchmark['metadata']['positive_count']} "
          f"negatives={benchmark['metadata']['negative_count']}")


if __name__ == "__main__":
    main()
