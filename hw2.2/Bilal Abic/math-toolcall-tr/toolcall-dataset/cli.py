"""Matematik Tool-Call veri seti ureteci.

Kullanim:
    python cli.py topics
    python cli.py run --n 100        # soru + cevap tek akista, 5'lik turlarla
    python cli.py questions --n 60   # sadece soru
    python cli.py answers            # bekleyen sorulari cevapla
    python cli.py export
    python cli.py stats
"""
import argparse
import json
import os
import random
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import config
import exporters
import prompts
import providers
import topics

ROOT_DIR = config.ROOT
Q_FILE = config.DATA_DIR / "questions.json"
D_FILE = config.DATA_DIR / "dataset.json"
CHAT_FILE = config.DATA_DIR / "dataset_chat.json"


# --- yardimcilar ------------------------------------------------------------
def load(path) -> list:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, rows) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def pick_providers(flag: str) -> list[str]:
    available = config.enabled_providers()
    if not available:
        sys.exit("HATA: .env icinde OPENAI_API_KEY veya GEMINI_API_KEY yok.")
    wanted = list(config.PROVIDERS) if flag == "both" else [flag]
    chosen = [p for p in wanted if p in available]
    if not chosen:
        sys.exit(f"HATA: {flag} icin API anahtari tanimli degil.")
    if len(chosen) < len(wanted):
        print(f"  uyari: sadece {', '.join(chosen)} kullanilabiliyor")
    return chosen


def run_parallel(jobs, worker, quiet: bool = False):
    """jobs uzerinde worker'i paralel calistir, sonuclari duz listede topla."""
    out, done = [], 0
    with ThreadPoolExecutor(max_workers=config.WORKERS) as pool:
        futures = [pool.submit(worker, job) for job in jobs]
        for fut in as_completed(futures):
            done += 1
            try:
                result = fut.result()
            except Exception as exc:  # noqa: BLE001
                print(f"  atlandi: {exc}")
                continue
            out.extend(result if isinstance(result, list) else [result])
            if not quiet:
                print(f"  [{done}/{len(jobs)}] {len(out)} kayit", end="\r")
    if not quiet:
        print()
    return out


def make_jobs(count: int, active: list[str], domain: str | None,
              fresh: bool = False) -> list[dict]:
    """(alt alan, konu, senaryo, zorluk) kombinasyonlarindan is listesi.

    fresh=True ise once hic uretilmemis konular secilir; bitince rastgeleye doner.
    """
    combos = topics.all_combos()
    if domain:
        combos = [c for c in combos if c[0] == domain]
        if not combos:
            sys.exit(f"HATA: '{domain}' alt alani yok. 'python cli.py topics' ile bak.")

    batches = max(1, -(-count // config.BATCH_SIZE))  # yukari yuvarlama

    queue: list[tuple[str, str]] = []
    if fresh:
        covered = {(r["domain"], r["topic"]) for r in load(D_FILE)}
        queue = [c for c in combos if c not in covered]
        random.shuffle(queue)
        print(f"Islenmemis konu: {len(queue)} (once bunlar uretilecek)")

    jobs = []
    for i in range(batches):
        dom, top = queue.pop() if queue else random.choice(combos)
        jobs.append(
            {
                "provider": active[i % len(active)],
                "domain": dom,
                "topic": top,
                "scenario": random.choice(list(topics.SCENARIOS)),
                "difficulty": random.choice(topics.DIFFICULTIES),
                "count": config.BATCH_SIZE,
            }
        )
    return jobs


# --- uretim adimlari --------------------------------------------------------
def gen_questions(job: dict, system: str) -> list[dict]:
    """Tek istekle BATCH_SIZE adet soru + arac semasi uretir."""
    prov = job["provider"]
    user = prompts.question_prompt(
        count=job["count"],
        domain=job["domain"],
        topic=job["topic"],
        scenario=job["scenario"],
        scenario_desc=topics.SCENARIOS[job["scenario"]],
        difficulty=job["difficulty"],
    )
    data = providers.complete_json(prov, system, user)
    rows = []
    for item in data.get("items", []):
        if not item.get("user_message") or not item.get("tools"):
            continue
        # Model nadiren bozuk JSON uretip listeye ham string birakiyor; onu ele.
        tools = exporters.valid_tools(item)
        if not tools:
            continue
        rows.append(
            {
                "id": f"q_{uuid.uuid4().hex[:10]}",
                "domain": job["domain"],
                "topic": job["topic"],
                "scenario": job["scenario"],
                "difficulty": job["difficulty"],
                "tools": tools,
                "question": item["user_message"].strip(),
                "expected_tools": item.get("expected_tools", []),
                "question_provider": prov,
                "question_model": providers.model_of(prov),
                "created_at": now(),
            }
        )
    return rows


def answer_question(job: tuple[str, dict], system: str) -> dict:
    """Bir soruya thinking + arac cagrilari + cevap uretir."""
    prov, q = job
    user = prompts.answer_prompt(
        domain=q["domain"],
        topic=q["topic"],
        scenario=q["scenario"],
        scenario_desc=topics.SCENARIOS[q["scenario"]],
        difficulty=q["difficulty"],
        tools_json=json.dumps(q["tools"], ensure_ascii=False, indent=2),
        user_message=q["question"],
    )
    data = providers.complete_json(prov, system, user)
    if not data.get("answer") or not data.get("thinking"):
        raise ValueError(f"{q['id']}: eksik alan (answer/thinking)")
    return {
        **q,
        "thinking": data["thinking"].strip(),
        "tool_calls": data.get("tool_calls", []),
        "tool_results": data.get("tool_results", []),
        "answer": data["answer"].strip(),
        "answer_provider": prov,
        "answer_model": providers.model_of(prov),
        "answered_at": now(),
    }


def dedupe(new_rows: list[dict], seen: set[str]) -> list[dict]:
    """Ayni soru metnini iki kez almayi engeller. seen kumesini gunceller."""
    kept = []
    for row in new_rows:
        key = row["question"].lower().strip()
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept


# --- komut: topics ----------------------------------------------------------
def cmd_topics(_args) -> None:
    total = 0
    for domain, items in topics.DOMAINS.items():
        print(f"\n{domain}  ({len(items)} konu)")
        for t in items:
            print(f"  - {t}")
        total += len(items)
    print(f"\nToplam: {len(topics.DOMAINS)} alt alan, {total} konu, "
          f"{len(topics.SCENARIOS)} senaryo, {len(topics.DIFFICULTIES)} zorluk")
    print(f"Olasi kombinasyon: {total * len(topics.SCENARIOS) * len(topics.DIFFICULTIES)}")


# --- komut: run (soru + cevap tek akista) -----------------------------------
def cmd_run(args) -> None:
    active = pick_providers(args.provider)
    system = prompts.system_prompt(config.LANG)
    jobs = make_jobs(args.n, active, args.domain, args.fresh)

    questions, dataset = load(Q_FILE), load(D_FILE)
    seen = {r["question"].lower().strip() for r in questions}

    # WORKERS'i doldurmak icin her "dalgada" birkac tur birlikte islenir.
    # ornek: WORKERS=12, BATCH_SIZE=5 -> dalga basi 2 tur = 10 paralel cevap cagrisi.
    per_wave = max(1, config.WORKERS // config.BATCH_SIZE)
    waves = [jobs[i:i + per_wave] for i in range(0, len(jobs), per_wave)]

    print(f"Uretim: {len(jobs)} tur x {config.BATCH_SIZE} soru = ~{len(jobs) * config.BATCH_SIZE} kayit")
    print(f"Saglayici: {', '.join(active)} | isci: {config.WORKERS} | "
          f"dalga: {per_wave} tur ({per_wave * config.BATCH_SIZE} soru birlikte)")
    print("Her dalga: sorulari paralel uret -> paralel cevapla -> diske yaz\n")

    for wi, wave in enumerate(waves, 1):
        # 1) dalgadaki tum turlarin sorularini paralel uret (her tur = 1 istek)
        batch = run_parallel(wave, lambda j: gen_questions(j, system), quiet=True)
        batch = dedupe(batch, seen)
        if not batch:
            print(f"[dalga {wi}/{len(waves)}] yeni soru cikmadi (tekrar), atlandi")
            continue

        # 2) dalganin tum sorularini paralel cevapla (WORKERS'a kadar es zamanli)
        answer_jobs = [(active[k % len(active)], q) for k, q in enumerate(batch)]
        answered = run_parallel(answer_jobs, lambda j: answer_question(j, system), quiet=True)

        # 3) diske yaz. Cevaplanamayan soru questions.json'da kalir, 'answers' ile tekrar denenir.
        questions.extend(batch)
        dataset.extend(answered)
        save(Q_FILE, questions)
        save(D_FILE, dataset)
        save(CHAT_FILE, [exporters.to_chat(r) for r in dataset])

        print(f"[dalga {wi}/{len(waves)}] +{len(answered)}/{len(batch)} cevap | "
              f"toplam {len(dataset)} kayit -> yazildi")

    print(f"\nBITTI  toplam {len(dataset)} kayit")
    print(f"  {D_FILE}      (tam metadata)")
    print(f"  {CHAT_FILE}   (sohbet formati)")


# --- komut: questions -------------------------------------------------------
def cmd_questions(args) -> None:
    active = pick_providers(args.provider)
    system = prompts.system_prompt(config.LANG)
    jobs = make_jobs(args.n, active, args.domain, args.fresh)

    print(f"Soru uretimi: {len(jobs)} istek x {config.BATCH_SIZE} = ~{len(jobs) * config.BATCH_SIZE}")
    print(f"Saglayici: {', '.join(active)} | isci: {config.WORKERS}")

    new_rows = run_parallel(jobs, lambda j: gen_questions(j, system))

    existing = load(Q_FILE)
    seen = {r["question"].lower().strip() for r in existing}
    added = dedupe(new_rows, seen)
    save(Q_FILE, existing + added)
    print(f"OK  +{len(added)} yeni soru ({len(new_rows) - len(added)} tekrar elendi) -> {Q_FILE}")


# --- komut: answers ---------------------------------------------------------
def cmd_answers(args) -> None:
    active = pick_providers(args.provider)
    system = prompts.system_prompt(config.LANG)

    questions = load(Q_FILE)
    if not questions:
        sys.exit(f"HATA: {Q_FILE} bos. Once 'python cli.py run' veya 'questions' calistir.")

    dataset = load(D_FILE)
    done_ids = {r["id"] for r in dataset}
    pending = [q for q in questions if q["id"] not in done_ids]
    if args.limit:
        pending = pending[: args.limit]
    if not pending:
        print("Cevaplanmamis soru yok.")
        return

    print(f"Cevap uretimi: {len(pending)} soru | saglayici: {', '.join(active)}")
    jobs = [(active[i % len(active)], q) for i, q in enumerate(pending)]
    new_rows = run_parallel(jobs, lambda j: answer_question(j, system))

    dataset += new_rows
    save(D_FILE, dataset)
    save(CHAT_FILE, [exporters.to_chat(r) for r in dataset])
    print(f"OK  +{len(new_rows)} kayit -> {D_FILE} (toplam {len(dataset)})")


# --- komut: export ----------------------------------------------------------
def cmd_export(args) -> None:
    dataset = load(D_FILE)
    if not dataset:
        sys.exit(f"HATA: {D_FILE} bos. Once 'python cli.py run' calistir.")

    save(CHAT_FILE, [exporters.to_chat(r) for r in dataset])
    print(f"OK  {len(dataset)} sohbet -> {CHAT_FILE}")

    with_think = not args.no_thinking
    sg = config.DATA_DIR / "train_sharegpt.jsonl"
    oa = config.DATA_DIR / "train_openai.jsonl"
    gm = config.DATA_DIR / "train_gemini.jsonl"
    n0 = exporters.write_jsonl(sg, (exporters.to_sharegpt(r, with_think) for r in dataset))
    n1 = exporters.write_jsonl(oa, (exporters.to_openai(r, args.inline_thinking) for r in dataset))
    n2 = exporters.write_jsonl(gm, (exporters.to_gemini(r, args.inline_thinking) for r in dataset))
    print(f"OK  {n0} kayit -> {sg}   <-- Unsloth/Colab bunu kullanir")
    print(f"OK  {n1} kayit -> {oa}")
    print(f"OK  {n2} kayit -> {gm}")
    print(f"    ham veri (thinking + kaynak bilgisi dahil) -> {D_FILE}")


# --- komut: push (Hugging Face Hub) -----------------------------------------
def cmd_push(args) -> None:
    try:
        from datasets import load_dataset
    except ImportError:
        sys.exit("HATA: pip install datasets huggingface_hub")

    token = args.token or os.getenv("HF_TOKEN", "")
    if not token:
        sys.exit("HATA: HF_TOKEN (.env) yok. huggingface.co/settings/tokens -> write token")

    src = config.DATA_DIR / "train_sharegpt.jsonl"
    if not src.exists():
        sys.exit(f"HATA: {src} yok. Once 'python cli.py export' calistir.")

    ds = load_dataset("json", data_files=str(src), split="train")
    print(f"Yukleniyor: {len(ds)} kayit -> {args.repo} (private={args.private})")
    ds.push_to_hub(args.repo, token=token, private=args.private)

    print(f"\nOK  https://huggingface.co/datasets/{args.repo}")
    print("Colab veri yukleme hucresi:")
    print(f'    dataset = load_dataset("{args.repo}", split="train")')


# --- komut: card (dataset kartini yukle) ------------------------------------
def cmd_card(args) -> None:
    try:
        from huggingface_hub import HfApi
    except ImportError:
        sys.exit("HATA: pip install huggingface_hub")

    token = args.token or os.getenv("HF_TOKEN", "")
    if not token:
        sys.exit("HATA: HF_TOKEN (.env) yok.")

    kind = "model" if args.model else "dataset"
    card = ROOT_DIR / ("MODEL_CARD.md" if args.model else "CARD.md")
    if not card.exists():
        sys.exit(f"HATA: {card} yok.")

    HfApi().upload_file(
        path_or_fileobj=str(card),
        path_in_repo="README.md",
        repo_id=args.repo,
        repo_type=kind,
        token=token,
        commit_message=f"{kind.capitalize()} karti guncellendi",
    )
    prefix = "" if args.model else "datasets/"
    print(f"OK  {kind} karti yuklendi -> https://huggingface.co/{prefix}{args.repo}")


# --- komut: stats -----------------------------------------------------------
def cmd_stats(_args) -> None:
    dataset = load(D_FILE)
    print(f"Sorular : {len(load(Q_FILE))}")
    print(f"Kayitlar: {len(dataset)}")
    if not dataset:
        return

    def tally(key):
        counts = {}
        for r in dataset:
            counts[r.get(key, "?")] = counts.get(r.get(key, "?"), 0) + 1
        return sorted(counts.items(), key=lambda kv: -kv[1])

    for key, title in [
        ("domain", "Alt alan"),
        ("scenario", "Senaryo"),
        ("difficulty", "Zorluk"),
        ("question_model", "Soruyu ureten model"),
        ("answer_model", "Cevabi ureten model"),
    ]:
        print(f"\n{title}:")
        for name, count in tally(key):
            print(f"  {name:<45} {count}")

    no_call = sum(1 for r in dataset if not r.get("tool_calls"))
    print(f"\nArac cagirmayan ornek: {no_call} / {len(dataset)}")


# --- giris ------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Matematik Tool-Call veri seti ureteci")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_provider(p):
        p.add_argument("--provider", default=config.DEFAULT_PROVIDER,
                       choices=["openai", "gemini", "both"])

    sub.add_parser("topics", help="alt alan ve konu listesi").set_defaults(fn=cmd_topics)

    p = sub.add_parser("run", help="soru + cevap tek akista (onerilen)")
    p.add_argument("--n", type=int, default=50, help="hedef kayit sayisi")
    p.add_argument("--domain", help="tek bir alt alanla sinirla")
    p.add_argument("--fresh", action="store_true",
                   help="once hic uretilmemis konulari isle (kapsamayi genisletir)")
    add_provider(p)
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("questions", help="sadece soru uret")
    p.add_argument("--n", type=int, default=50, help="hedef soru sayisi")
    p.add_argument("--domain", help="tek bir alt alanla sinirla")
    p.add_argument("--fresh", action="store_true",
                   help="once hic uretilmemis konulari isle")
    add_provider(p)
    p.set_defaults(fn=cmd_questions)

    p = sub.add_parser("answers", help="bekleyen sorulari cevapla")
    p.add_argument("--limit", type=int, help="en fazla N soru isle")
    add_provider(p)
    p.set_defaults(fn=cmd_answers)

    p = sub.add_parser("export", help="sharegpt + sohbet + openai + gemini formatlari")
    p.add_argument("--inline-thinking", action="store_true",
                   help="openai/gemini jsonl'de thinking'i cevaba <think> olarak gom")
    p.add_argument("--no-thinking", action="store_true",
                   help="sharegpt ciktisinda <think> bloklarini koyma (sadece arac+cevap)")
    p.set_defaults(fn=cmd_export)

    p = sub.add_parser("push", help="train_sharegpt.jsonl'i Hugging Face Hub'a yukle")
    p.add_argument("repo", help="hedef repo, orn: kullanici/math-toolcall")
    p.add_argument("--private", action="store_true", help="ozel veri seti olarak yukle")
    p.add_argument("--token", help="HF write token (yoksa .env icindeki HF_TOKEN)")
    p.set_defaults(fn=cmd_push)

    p = sub.add_parser("card", help="CARD.md / MODEL_CARD.md'yi HF README'si olarak yukle")
    p.add_argument("repo", help="hedef repo, orn: kullanici/math-toolcall")
    p.add_argument("--model", action="store_true",
                   help="model reposuna yukle (MODEL_CARD.md); yoksa dataset (CARD.md)")
    p.add_argument("--token", help="HF write token (yoksa .env icindeki HF_TOKEN)")
    p.set_defaults(fn=cmd_card)

    sub.add_parser("stats", help="veri seti dagilimi").set_defaults(fn=cmd_stats)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
