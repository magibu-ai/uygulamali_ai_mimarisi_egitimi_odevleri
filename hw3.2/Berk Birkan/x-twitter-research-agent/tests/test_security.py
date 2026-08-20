from x_research_agent.security import hash_access_code, redact, verify_access_code


def test_access_code_hash_is_salted_and_verifiable():
    code = "ABCD-1234"
    first = hash_access_code(code, "salt-one")
    second = hash_access_code(code, "salt-two")

    assert first != second
    assert verify_access_code("abcd-1234", "salt-one", first)
    assert not verify_access_code("WRONG", "salt-one", first)


def test_redact_hides_nested_secrets():
    payload = {
        "query": "openrouter",
        "headers": {"Authorization": "Bearer secret", "x-api-key": "xq_secret"},
        "items": [{"api_key": "secret"}],
    }

    redacted = redact(payload)

    assert redacted["query"] == "openrouter"
    assert redacted["headers"]["Authorization"] == "***REDACTED***"
    assert redacted["headers"]["x-api-key"] == "***REDACTED***"
    assert redacted["items"][0]["api_key"] == "***REDACTED***"
