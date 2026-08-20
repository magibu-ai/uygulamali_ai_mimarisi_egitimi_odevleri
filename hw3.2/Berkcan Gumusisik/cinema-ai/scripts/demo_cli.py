"""Uçtan uca terminal demosu.

Aynı agent + tool-calling döngüsünü iki backend ile çalıştırır:
  * Çevrimiçi : LLM_API_KEY tanımlıysa gerçek modeli (ör. Groq) kullanır.
  * Çevrimdışı: --offline ile yahut anahtar yokken yerel MOCK model devreye girer
                (API'siz, kural tabanlı). Tool-yönlendirme + DB akışı birebir aynıdır.

Çalıştırma:
    python scripts/demo_cli.py                 # anahtar varsa gerçek model, yoksa mock
    python scripts/demo_cli.py --offline       # her durumda mock (API gerekmez)
    python scripts/demo_cli.py "korku filmi öner"   # tek mesaj
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Proje kökünü import yoluna ekle (script doğrudan çalıştırıldığında).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _print_trace(trace: list[dict]) -> None:
    """Tetiklenen tool-call'ları okunur biçimde bastırır."""
    if not trace:
        print("   (tool çağrısı yapılmadı)")
        return
    for i, step in enumerate(trace, 1):
        args = json.dumps(step["arguments"], ensure_ascii=False)
        result = json.dumps(step["result"], ensure_ascii=False)
        print(f"   [{i}] 🔧 TOOL-CALL: {step['name']}({args})")
        print(f"       ↩︎  SONUÇ: {result}")


def run(messages: list[str]) -> None:
    """Örnek konuşmayı agent üzerinden çalıştırır (backend config'ten seçilir)."""
    # Not: --offline env'i set edildikten SONRA import edilmeli.
    from src.agent import respond
    from src.config import get_llm_config

    cfg = get_llm_config()
    mode = "MOCK (yerel, API'siz)" if cfg.use_mock else f"{cfg.model} @ {cfg.base_url}"
    print(f"Backend: {mode}\n")

    history: list[dict] = []
    for user_msg in messages:
        print(f"👤 KULLANICI: {user_msg}")
        reply, trace = respond(history, user_msg, cfg=cfg)
        print("🛠  ARKA PLAN (tetiklenen tool-call'lar):")
        _print_trace(trace)
        print(f"🎬 CINEMA-AI: {reply}\n")
        print("-" * 70)
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply})


def main() -> None:
    parser = argparse.ArgumentParser(description="Cinema-AI terminal demosu")
    parser.add_argument("--offline", action="store_true", help="Yerel mock modeli zorla (API gerekmez)")
    parser.add_argument("message", nargs="*", help="Tek seferlik kullanıcı mesajı")
    args = parser.parse_args()

    if args.offline:
        os.environ["LLM_BACKEND"] = "mock"  # config bunu okuyacak

    print("=" * 70)
    print("  CINEMA-AI — Tool-Calling Film Asistanı (terminal demo)")
    print("=" * 70)

    if args.message:
        run([" ".join(args.message)])
    else:
        # Okuma + yazma + halüsinasyon engelini kapsayan varsayılan senaryo.
        run(
            [
                "Bana 8.7 üstü bir bilim kurgu filmi öner.",
                "Başlangıç filmini izleme listeme ekle.",
                "İzleme listemde neler var?",
                "Uzaylı Kediler 7 filmini bul.",
            ]
        )


if __name__ == "__main__":
    main()
