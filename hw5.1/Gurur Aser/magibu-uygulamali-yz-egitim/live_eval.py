"""Run a small, reproducible live evaluation against the configured Ollama model."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .chat import PantryAgent
from .ollama_client import MODEL, OllamaClient
from .pantry import DEFAULT_SEED_PATH, PantryStore
from .tools import PantryTools

ALL_TOOLS = frozenset(
    {
        "list_pantry",
        "internet_search",
        "add_pantry_item",
        "consume_pantry_item",
        "remove_pantry_item",
    }
)
DEFAULT_REPORT_PATH = Path(__file__).resolve().parent / "artifacts" / "live_eval.json"


@dataclass(frozen=True)
class Scenario:
    name: str
    prompts: tuple[str, ...]
    required_tools: frozenset[str] = frozenset()
    forbidden_tools: frozenset[str] = frozenset()
    expected_pending: bool | None = None
    expected_state_change: bool | None = None
    reply_terms: tuple[str, ...] = ()


def default_scenarios(today: date | None = None) -> tuple[Scenario, ...]:
    current = today or datetime.now().astimezone().date()
    add_date = (current + timedelta(days=8)).isoformat()
    return (
        Scenario("greeting", ("Merhaba, kısaca kendini tanıtır mısın?",), forbidden_tools=ALL_TOOLS, expected_state_change=False),
        Scenario("urgent_inventory", ("Envanterimde öncelikle tüketmem gereken ürünler hangileri?",), frozenset({"list_pantry"}), expected_state_change=False),
        Scenario("milk_stock", ("Dolabımda ne kadar süt var?",), frozenset({"list_pantry"}), expected_state_change=False),
        Scenario("long_term_stock", ("Pirinç stok durumumu kontrol et.",), frozenset({"list_pantry"}), expected_state_change=False),
        Scenario("recipe_search", ("Dolabımdaki acil ürünlerle yapabileceğim pratik bir tarif ara.",), frozenset({"list_pantry", "internet_search"}), expected_state_change=False),
        Scenario("expired_food_safety", ("Son kullanma tarihi geçmiş ürünleri tüketmem güvenli mi?",), frozenset({"list_pantry"}), expected_state_change=False, reply_terms=("geçmiş", "tüket")),
        Scenario("add_preview", (f"Envantere 2 adet biber ekle; kategori sebze, son kullanma tarihi {add_date}.",), frozenset({"add_pantry_item"}), expected_pending=True, expected_state_change=False),
        Scenario("add_confirm", (f"Envantere 2 adet biber ekle; kategori sebze, son kullanma tarihi {add_date}.", "onayla"), frozenset({"add_pantry_item"}), expected_pending=False, expected_state_change=True, reply_terms=("uygulandı",)),
        Scenario("consume_preview", ("sut-1 kimlikli üründen 0.5 litre tüket.",), frozenset({"consume_pantry_item"}), expected_pending=True, expected_state_change=False),
        Scenario("remove_cancel", ("domates-1 kimlikli ürünü envanterden sil.", "iptal"), frozenset({"remove_pantry_item"}), expected_pending=False, expected_state_change=False, reply_terms=("iptal",)),
        Scenario("bare_confirmation", ("onayla",), forbidden_tools=ALL_TOOLS, expected_pending=False, expected_state_change=False, reply_terms=("bekleyen",)),
        Scenario("unrelated_question", ("2 + 2 kaç eder?",), forbidden_tools=ALL_TOOLS, expected_state_change=False, reply_terms=("4",)),
    )


def assess_scenario(
    scenario: Scenario,
    turns: Sequence[dict[str, Any]],
    *,
    state_changed: bool,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    observed_tools = {
        str(log.get("name", ""))
        for turn in turns
        for log in (turn.get("tool_logs") or [])
    }
    missing = sorted(scenario.required_tools - observed_tools)
    forbidden = sorted(scenario.forbidden_tools & observed_tools)
    if missing:
        reasons.append("eksik araç: " + ", ".join(missing))
    if forbidden:
        reasons.append("yasak araç: " + ", ".join(forbidden))

    final = turns[-1] if turns else {}
    if scenario.expected_pending is not None and bool(final.get("pending")) != scenario.expected_pending:
        reasons.append(f"pending beklenen={scenario.expected_pending} gerçekleşen={bool(final.get('pending'))}")
    if scenario.expected_state_change is not None and state_changed != scenario.expected_state_change:
        reasons.append(
            "durum dosyası değişimi "
            f"beklenen={scenario.expected_state_change} gerçekleşen={state_changed}"
        )
    reply = str(final.get("reply", "") or "").casefold()
    if not reply:
        reasons.append("boş final yanıtı")
    if scenario.reply_terms and not any(term.casefold() in reply for term in scenario.reply_terms):
        reasons.append("yanıt terimi bulunamadı: " + " | ".join(scenario.reply_terms))
    return not reasons, reasons


def _public_turn(prompt: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "prompt": prompt,
        "reply": result.get("reply", ""),
        "pending": bool(result.get("pending")),
        "tool_logs": [
            {
                "name": log.get("name"),
                "arguments": log.get("arguments", {}),
                "result": log.get("result", {}),
                "duration_ms": log.get("duration_ms"),
            }
            for log in result.get("tool_logs") or []
        ],
    }


def run_evaluation(scenarios: Sequence[Scenario] | None = None) -> dict[str, Any]:
    selected = tuple(scenarios or default_scenarios())
    records: list[dict[str, Any]] = []
    client = OllamaClient()
    try:
        for scenario in selected:
            with tempfile.TemporaryDirectory(prefix="les8-live-eval-") as temporary:
                state_path = Path(temporary) / "pantry.json"
                store = PantryStore(state_path, seed_path=DEFAULT_SEED_PATH)
                before = state_path.read_bytes()
                agent = PantryAgent(PantryTools(store), client=client)
                turns: list[dict[str, Any]] = []
                for prompt in scenario.prompts:
                    result = agent.respond(prompt)
                    turns.append(_public_turn(prompt, result))
                state_changed = state_path.read_bytes() != before
                passed, reasons = assess_scenario(scenario, turns, state_changed=state_changed)
                records.append(
                    {
                        "name": scenario.name,
                        "passed": passed,
                        "reasons": reasons,
                        "state_changed": state_changed,
                        "turns": turns,
                    }
                )
    finally:
        client.close()

    passed_count = sum(record["passed"] for record in records)
    return {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": MODEL,
        "summary": {"passed": passed_count, "total": len(records)},
        "scenarios": records,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dolap Kurtarıcı canlı Ollama değerlendirmesi")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args(argv)
    report = run_evaluation()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = report["summary"]
    print(f"Canlı değerlendirme: {summary['passed']}/{summary['total']} geçti")
    print(f"Rapor: {args.output}")
    for record in report["scenarios"]:
        if not record["passed"]:
            print(f"- {record['name']}: {'; '.join(record['reasons'])}")
    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":  # pragma: no cover - command-line entry point
    raise SystemExit(main())
