#!/usr/bin/env python
"""Publish the project to a Hugging Face repository.

    uv run python scripts/push_to_hub.py --repo erenyanic/e-hekim
    uv run python scripts/push_to_hub.py --repo erenyanic/e-hekim --dry-run

Uploads the source code, the frontend, the benchmark set and the generated
chunk parquet (url / chunk_text / chunk_vector + metadata) to a single dataset
repository.

Safety: the upload set is built from an explicit allow-list of paths and then
passed through a deny-list check. Anything matching a secret pattern aborts the
run before a single byte is sent. `.env`, `.venv/`, `chroma_db/` and caches can
never be included, and the script re-lists the remote repository afterwards to
prove what actually landed.
"""

from __future__ import annotations

import argparse
import fnmatch
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ehekim.config import PROJECT_ROOT, operator_secrets

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("push")

# Only these paths are ever considered for upload.
INCLUDE_PATTERNS = (
    "README.md",
    "pyproject.toml",
    ".env.example",
    ".gitignore",
    "src/ehekim/*.py",
    "scripts/*.py",
    "frontend/*",
    "tests/*.py",
    "data/benchmark_questions.json",
    "data/benchmark_results.json",
    "data/threshold_report.md",
    "data/ingest_manifest.json",
    "data/ehekim_chunks.parquet",
    "data/benchmark_questions.parquet",
)

# Belt and braces: even if an include pattern were widened by mistake, nothing
# matching these may ever be uploaded.
DENY_PATTERNS = (
    ".env",
    ".env.*",
    "*.key",
    "*.pem",
    "*.pfx",
    "*credentials*",
    "*secret*",
    "*token*",
    ".venv/*",
    "chroma_db/*",
    "**/__pycache__/*",
    "*.pyc",
)

# Files small enough to scan for accidentally embedded credentials.
SCAN_SUFFIXES = {".py", ".md", ".json", ".toml", ".js", ".css", ".html", ".txt", ".example"}
SCAN_MAX_BYTES = 2_000_000


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Upload e-hekim to the Hugging Face Hub")
    p.add_argument("--repo", required=True, help="Target repo id, e.g. erenyanic/e-hekim")
    p.add_argument("--repo-type", default="dataset", choices=["dataset", "model", "space"])
    p.add_argument("--private", action="store_true", help="Create the repo as private.")
    p.add_argument("--dry-run", action="store_true", help="List what would be uploaded, then stop.")
    return p.parse_args()


# The only file allowed to survive the `.env.*` deny rule: it is the committed
# template and contains placeholders, never a real value.
DENY_EXCEPTIONS = frozenset({".env.example", "data/benchmark_questions.parquet"})


def is_denied(relative: str) -> bool:
    name = Path(relative).name
    if relative in DENY_EXCEPTIONS:
        return False
    for pattern in DENY_PATTERNS:
        if fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(name, pattern):
            return True
        if pattern.endswith("/*") and relative.startswith(pattern[:-1]):
            return True
    return False


def collect_files() -> list[Path]:
    selected: list[Path] = []
    for pattern in INCLUDE_PATTERNS:
        for path in sorted(PROJECT_ROOT.glob(pattern)):
            if not path.is_file():
                continue
            relative = path.relative_to(PROJECT_ROOT).as_posix()
            if is_denied(relative):
                logger.info("Atlandı (deny-list): %s", relative)
                continue
            selected.append(path)
    return selected


# Two different jobs need two different sensitivities.
#
# `ehekim.security.redact` is deliberately broad: when sanitising output, over-
# redaction is free and a miss is a leak. Reusing it here would block the upload
# on the word "api_key" in a type annotation, on the redaction patterns in
# security.py itself, and on every deliberately-fake key in the test suite.
#
# The upload scanner instead needs precision, so it works in two layers:
#
#   1. An EXACT check against the real values in .env. This is the one that
#      actually matters — it has zero false positives and catches the only
#      credentials this machine holds.
#   2. A narrow provider-shape check, with obvious placeholders filtered out, to
#      catch a credential that was pasted in from somewhere else.
_KEY_SHAPES = (
    re.compile(r"\bsk-or-v1-([A-Za-z0-9_\-]{20,})"),
    re.compile(r"\bsk-([A-Za-z0-9_\-]{20,})"),
    re.compile(r"\bhf_([A-Za-z0-9]{30,})"),
    re.compile(r"\bgsk_([A-Za-z0-9]{30,})"),
    re.compile(r"\bAIza([A-Za-z0-9_\-]{30,})"),
)

_SEQUENCES = ("abcdefghijklmnopqrstuvwxyz", "0123456789")


def _is_obvious_placeholder(body: str) -> bool:
    """True for the fake keys that belong in tests and documentation."""
    lowered = body.lower()
    if "xxx" in lowered or "your" in lowered or "example" in lowered:
        return True
    # sk-000...0f and friends: almost no character variety.
    if len(set(lowered)) <= 4:
        return True
    # abcdef0123456789...: contains a long ascending run.
    for sequence in _SEQUENCES:
        for start in range(len(sequence) - 7):
            if sequence[start : start + 8] in lowered:
                return True
    return False


def scan_for_secrets(paths: list[Path], live_secrets: list[str]) -> list[str]:
    """Return findings; a non-empty list must abort the upload."""
    findings: list[str] = []
    # Only compare against values long enough to be real credentials.
    real = [s for s in live_secrets if s and len(s) >= 16]

    for path in paths:
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        if path.stat().st_size > SCAN_MAX_BYTES or path.suffix not in SCAN_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for number, line in enumerate(text.splitlines(), start=1):
            # Layer 1 — an actual credential from .env appears verbatim.
            for secret in real:
                if secret in line:
                    findings.append(f"{relative}:{number}: .env değeri birebir bulundu")
            # Layer 2 — a credential-shaped token that is not a placeholder.
            if relative == ".env.example":
                continue
            for pattern in _KEY_SHAPES:
                for match in pattern.finditer(line):
                    if not _is_obvious_placeholder(match.group(1)):
                        findings.append(
                            f"{relative}:{number}: kimlik bilgisi biçimli değer "
                            f"({match.group(0)[:6]}…)"
                        )
    return findings


def main() -> int:
    args = parse_args()

    files = collect_files()
    if not files:
        logger.error("Yüklenecek dosya bulunamadı.")
        return 1

    total_mb = sum(f.stat().st_size for f in files) / 1e6
    logger.info("Yüklenecek %s dosya (%.1f MB):", len(files), total_mb)
    for path in files:
        logger.info("  %s", path.relative_to(PROJECT_ROOT).as_posix())

    secrets = operator_secrets()
    findings = scan_for_secrets(files, [v for v in secrets.values() if v])
    if findings:
        logger.error("GÜVENLİK: yüklenecek dosyalarda kimlik bilgisi kalıbı bulundu, yükleme iptal edildi:")
        for finding in findings:
            logger.error("  %s", finding)
        return 2
    logger.info("Gizli bilgi taraması temiz.")

    # Explicit assertions on the things that must never ship.
    names = {f.relative_to(PROJECT_ROOT).as_posix() for f in files}
    assert ".env" not in names, ".env yükleme listesine girmiş!"
    assert not any(n.startswith(".venv/") for n in names)
    assert not any(n.startswith("chroma_db/") for n in names)

    if args.dry_run:
        logger.info("--dry-run: hiçbir şey yüklenmedi.")
        return 0

    token = secrets.get("HUGGINGFACE_TOKEN")
    if not token:
        logger.error("HUGGINGFACE_TOKEN bulunamadı (.env).")
        return 1

    from huggingface_hub import HfApi

    api = HfApi(token=token)
    api.create_repo(repo_id=args.repo, repo_type=args.repo_type,
                    private=args.private, exist_ok=True)
    logger.info("Depo hazır: %s (%s)", args.repo, args.repo_type)

    for path in files:
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        api.upload_file(
            path_or_fileobj=str(path),
            path_in_repo=relative,
            repo_id=args.repo,
            repo_type=args.repo_type,
            commit_message=f"Add {relative}",
        )
        logger.info("Yüklendi: %s", relative)

    remote = set(api.list_repo_files(repo_id=args.repo, repo_type=args.repo_type))

    leaked = {name for name in remote
              if is_denied(name) or name == ".env" or name.endswith("/.env")}
    if leaked:
        logger.error("GÜVENLİK: uzak depoda olmaması gereken dosyalar var: %s", sorted(leaked))
        return 2

    # The Hub silently drops files matched by the repo's .gitignore (the commit
    # still returns 200), so "upload_file did not raise" is not proof of
    # delivery. Compare the intended set against what is actually there.
    expected = {f.relative_to(PROJECT_ROOT).as_posix() for f in files}
    missing = sorted(expected - remote)
    if missing:
        logger.error("EKSİK: yüklendiği bildirilen ama uzak depoda bulunmayan dosyalar: %s", missing)
        logger.error("Muhtemel neden: .gitignore bu yolları kapsıyor (Hub 'shouldIgnore' döndürür).")
        return 3

    logger.info("Doğrulandı: uzak depoda %s dosya; %s beklenen dosyanın tamamı yerinde, "
                "sızdırılmış gizli dosya yok.", len(remote), len(expected))
    logger.info("https://huggingface.co/datasets/%s", args.repo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
