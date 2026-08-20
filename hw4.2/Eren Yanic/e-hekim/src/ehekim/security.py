"""Credential handling and output sanitisation.

The threat model for this project is narrow but strict: the user pastes a
provider API key into a browser form, it travels to the local backend, is used
for exactly one upstream call, and then disappears. It must never be written to
disk, to a log line, into a URL, or back into an HTTP response body.

Three concrete defences live here:

1. :func:`validate_api_key` — structural validation before the key is ever
   placed in an ``Authorization`` header, so a malformed value cannot be used
   to smuggle extra headers (CRLF injection).
2. :func:`redact` — a scrubber applied to *every* error string that leaves the
   process, because upstream providers and HTTP libraries habitually echo the
   credential (or part of it) back inside error payloads.
3. :class:`SecretStr`-style discipline — keys are passed as plain locals and
   never stored on module state, never attached to exceptions, and excluded
   from all Pydantic response models.
"""

from __future__ import annotations

import re

MAX_API_KEY_LENGTH = 512
MIN_API_KEY_LENGTH = 16

# Keys must be a single line of printable ASCII. This rejects newlines (header
# injection), NUL bytes, and non-ASCII paste artefacts in one check.
_API_KEY_RE = re.compile(r"^[\x21-\x7e]+$")


class InvalidApiKeyError(ValueError):
    """Raised when a user-supplied key is structurally unusable."""


def validate_api_key(raw: str | None) -> str:
    """Return a structurally valid key, or raise :class:`InvalidApiKeyError`.

    The error message never contains any part of the offending value.
    """
    if raw is None:
        raise InvalidApiKeyError("API anahtarı eksik.")
    key = raw.strip()
    if not key:
        raise InvalidApiKeyError("API anahtarı boş olamaz.")
    if len(key) < MIN_API_KEY_LENGTH:
        raise InvalidApiKeyError("API anahtarı beklenenden kısa.")
    if len(key) > MAX_API_KEY_LENGTH:
        raise InvalidApiKeyError("API anahtarı beklenenden uzun.")
    if not _API_KEY_RE.match(key):
        raise InvalidApiKeyError(
            "API anahtarı yalnızca tek satırlık yazdırılabilir ASCII karakterler içerebilir."
        )
    return key


# Patterns matched against any text on its way out of the process. Ordered from
# most specific to most general; all are replaced by a fixed marker.
_REDACTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Authorization headers in any casing, with or without the Bearer scheme.
    re.compile(r"(?i)\bauthorization\b\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bbearer\s+\S+"),
    # Provider-specific key shapes.
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"),          # OpenAI / DeepSeek
    re.compile(r"\bsk-or-v1-[A-Za-z0-9_\-]{8,}"),    # OpenRouter
    re.compile(r"\bhf_[A-Za-z0-9]{8,}"),             # Hugging Face
    re.compile(r"\bgsk_[A-Za-z0-9]{8,}"),            # Groq
    re.compile(r"\b(?:AIza)[A-Za-z0-9_\-]{20,}"),    # Google
    # JSON/kwarg spellings such as  api_key='...'  or  "apiKey": "..."
    re.compile(r"""(?i)\b(?:api[_-]?key|access[_-]?token|secret)\b["'\s:=]+["']?[A-Za-z0-9_\-]{8,}["']?"""),
)

REDACTION_MARKER = "[REDACTED]"


def redact(text: object) -> str:
    """Scrub anything that looks like a credential out of ``text``.

    Applied to every error message relayed to the client and to anything that
    reaches the application log.
    """
    out = str(text)
    for pattern in _REDACTION_PATTERNS:
        out = pattern.sub(REDACTION_MARKER, out)
    return out


def contains_secret(text: object) -> bool:
    """True if ``text`` still matches a credential pattern. Used by tests."""
    return redact(text) != str(text)
