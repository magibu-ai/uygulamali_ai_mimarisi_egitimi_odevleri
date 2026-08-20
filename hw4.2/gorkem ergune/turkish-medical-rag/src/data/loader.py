"""Dataset loading (Phase 1).

Loads the configured Hugging Face dataset and normalizes each record into a
flat document dict with the fields required by the project schema:

    {"url": str, "title": str, "text": str, "source": str}

The ``source`` field records the originating Hugging Face split (a hospital
name for the ``turkish-hospital-medical-articles`` dataset). Field *names* are
read from configuration rather than assumed, so a different dataset can be
supported by editing ``configs/config.yaml`` alone.
"""
from __future__ import annotations

from typing import Any

from datasets import get_dataset_split_names, load_dataset


def _clean(value: Any) -> str:
    """Coerce a possibly-``None`` cell to a stripped string."""
    if value is None:
        return ""
    return str(value).strip()


def resolve_splits(config: dict[str, Any]) -> list[str]:
    """Return the list of splits to load.

    ``dataset.split`` may be a specific split name, or ``null`` to mean
    "pool every available split into one corpus".
    """
    name = config["dataset"]["name"]
    configured = config["dataset"].get("split")
    if configured:
        return [configured]
    return list(get_dataset_split_names(name))


def load_documents(config: dict[str, Any]) -> list[dict[str, str]]:
    """Load and normalize all documents from the configured dataset.

    Returns a list of dicts with keys ``url``, ``title``, ``text``, ``source``.
    No filtering, deduplication, or selection happens here — that is the
    selector's responsibility, so that raw counts remain observable.
    """
    ds_cfg = config["dataset"]
    name = ds_cfg["name"]
    text_field = ds_cfg["text_field"]
    url_field = ds_cfg.get("url_field")
    title_field = ds_cfg.get("title_field")

    documents: list[dict[str, str]] = []
    for split in resolve_splits(config):
        split_ds = load_dataset(name, split=split)
        for row in split_ds:
            documents.append(
                {
                    "url": _clean(row.get(url_field)) if url_field else "",
                    "title": _clean(row.get(title_field)) if title_field else "",
                    "text": _clean(row.get(text_field)),
                    "source": split,
                }
            )
    return documents
