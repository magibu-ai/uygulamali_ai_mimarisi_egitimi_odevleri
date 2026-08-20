import os

import pytest

from odev2_beehive_assistant.llm import HFRouterClient
from odev2_beehive_assistant.tools import TOOL_SCHEMAS


@pytest.mark.skipif(not os.getenv("HF_TOKEN"), reason="HF_TOKEN is not configured")
def test_optional_live_router_smoke():
    response = HFRouterClient().complete(
        [{"role": "user", "content": "Kovanları listele."}],
        TOOL_SCHEMAS,
        tool_choice="required",
    )
    assert response["role"] == "assistant"
    assert response.get("tool_calls"), response
