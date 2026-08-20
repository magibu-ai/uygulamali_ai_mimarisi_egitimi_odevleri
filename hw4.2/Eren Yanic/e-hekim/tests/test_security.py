"""The security guarantees this project claims, asserted."""

from __future__ import annotations

import pytest

from ehekim.security import (
    InvalidApiKeyError,
    REDACTION_MARKER,
    contains_secret,
    redact,
    validate_api_key,
)

VALID = "sk-abcdef0123456789abcdef0123456789"


class TestValidateApiKey:
    def test_accepts_a_normal_key(self):
        assert validate_api_key(VALID) == VALID

    def test_strips_surrounding_whitespace(self):
        assert validate_api_key(f"  {VALID}\n") == VALID

    @pytest.mark.parametrize("bad", [None, "", "   ", "short", "x" * 513])
    def test_rejects_structurally_invalid_values(self, bad):
        with pytest.raises(InvalidApiKeyError):
            validate_api_key(bad)

    @pytest.mark.parametrize(
        "bad",
        [
            "sk-abc123456789012\nX-Injected: evil",   # CRLF header injection
            "sk-abc123456789012\r\nHost: evil.test",
            "sk-abc1234567890\x00trailing",           # NUL byte
            "sk-abc1234567890 with space",
        ],
    )
    def test_rejects_header_injection_attempts(self, bad):
        with pytest.raises(InvalidApiKeyError):
            validate_api_key(bad)

    def test_error_message_never_echoes_the_key(self):
        secret = "sk-supersecretvalue123456789"
        with pytest.raises(InvalidApiKeyError) as info:
            validate_api_key(secret + "\nX: y")
        assert secret not in str(info.value)


class TestRedact:
    @pytest.mark.parametrize(
        "text",
        [
            "Authentication Fails, Your api key: sk-abcdef0123456789 is invalid",
            "Authorization: Bearer sk-or-v1-abcdef0123456789",
            "authorization=sk-abcdef0123456789",
            '{"api_key": "sk-abcdef0123456789"}',
            "token hf_abcdefghijklmnopqrstuvwxyz012345",
            "gsk_abcdefghijklmnopqrstuvwx",
            "AIzaSyA1234567890abcdefghijklmnopqrstu",
            "apiKey='sk-abcdef0123456789'",
        ],
    )
    def test_scrubs_credential_shapes(self, text):
        assert REDACTION_MARKER in redact(text)
        assert contains_secret(text) is True

    def test_leaves_ordinary_text_alone(self):
        text = "Sağlayıcı hız sınırına ulaşıldı."
        assert redact(text) == text
        assert contains_secret(text) is False

    def test_scrubs_the_real_deepseek_error_shape(self):
        """DeepSeek echoes the submitted key back inside its 401 body."""
        secret = "sk-0123456789abcdef0123456789abcdef"
        raw = f'Authentication Fails, Your api key: {secret} is invalid'
        cleaned = redact(raw)
        assert secret not in cleaned
        assert REDACTION_MARKER in cleaned

    def test_handles_non_string_input(self):
        assert redact(ValueError("Bearer sk-abcdef0123456789")) == f"{REDACTION_MARKER}"
