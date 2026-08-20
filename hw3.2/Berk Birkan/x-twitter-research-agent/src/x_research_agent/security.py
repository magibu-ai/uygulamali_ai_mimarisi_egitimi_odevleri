import hashlib
import hmac
import secrets
from typing import Any

SENSITIVE_KEYS = {"authorization", "x-api-key", "api_key", "openrouter_key", "xquik_key"}


def generate_session_id() -> str:
    return f"ses_{secrets.token_urlsafe(18)}"


def generate_thread_id() -> str:
    return f"thr_{secrets.token_urlsafe(16)}"


def generate_access_code() -> str:
    raw = secrets.token_hex(4).upper()
    return f"{raw[:4]}-{raw[4:]}"


def hash_access_code(code: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        code.strip().upper().encode(),
        salt.encode(),
        310_000,
    ).hex()


def verify_access_code(code: str, salt: str, expected_hash: str) -> bool:
    actual = hash_access_code(code, salt)
    return hmac.compare_digest(actual, expected_hash)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***REDACTED***" if key.lower() in SENSITIVE_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value
