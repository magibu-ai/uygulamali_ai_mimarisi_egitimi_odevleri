"""chat_template.jinja render smoke testleri.

Şablonun tüm rolleri ve tool-calling bloklarını doğru sarmaladığını doğrular.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.render_template import render  # noqa: E402


def test_template_wraps_all_roles():
    output = render()
    # ChatML rol sınırlayıcıları mevcut olmalı.
    assert "<|im_start|>system" in output
    assert "<|im_start|>user" in output
    assert "<|im_start|>assistant" in output
    assert "<|im_start|>tool" in output
    assert "<|im_end|>" in output


def test_template_renders_tool_call_and_response():
    output = render()
    # Asistanın tool çağrısı ve tool sonucu doğru bloklara sarılmalı.
    assert "<tool_call>" in output and "</tool_call>" in output
    assert "<tool_response>" in output and "</tool_response>" in output
    assert '"name": "search_movies"' in output


def test_template_no_html_escaping():
    """tojson birleştirmesinden kaynaklı HTML-escape olmamalı."""
    output = render()
    assert "&lt;" not in output
    assert "&gt;" not in output


def test_template_generation_prompt_at_end():
    """add_generation_prompt=True iken çıktı asistan turu ile bitmeli."""
    output = render()
    assert output.rstrip().endswith("<|im_start|>assistant")
