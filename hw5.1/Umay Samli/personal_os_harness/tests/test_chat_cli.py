from __future__ import annotations

from collections.abc import Callable

import pytest
from typer.testing import CliRunner

from personal_os.agent import AgentTurn
from personal_os.chat_cli import app, run_session
from personal_os.providers.ollama_http import ModelCapabilities, ToolCall

runner = CliRunner()


class FakeAgent:
    def __init__(self) -> None:
        self.start_count = 0
        self.messages: list[str] = []

    def start(self) -> ModelCapabilities:
        self.start_count += 1
        return ModelCapabilities("test-model", frozenset({"tools"}))

    def run(self, user_content: str) -> AgentTurn:
        self.messages.append(user_content)
        return AgentTurn(
            content=f"reply: {user_content}",
            tool_rounds=0,
            history=(),
        )


class ToolCallingFakeAgent(FakeAgent):
    def run(self, user_content: str) -> AgentTurn:
        turn = super().run(user_content)
        return AgentTurn(
            content=turn.content,
            tool_rounds=1,
            history=(),
            tool_calls=(ToolCall("time.get_current_date", {"timezone": "Europe/Istanbul"}),),
        )


def _reader(*values: str) -> Callable[[], str]:
    messages = iter(values)
    return lambda: next(messages)


def test_one_shot_session_prints_only_the_answer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    agent = FakeAgent()

    run_session(agent, initial_message="Read settings")

    captured = capsys.readouterr()
    assert captured.out == "reply: Read settings\n"
    assert agent.start_count == 1
    assert agent.messages == ["Read settings"]


def test_session_prints_tool_calls_before_the_answer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_session(ToolCallingFakeAgent(), initial_message="What date is it?")

    captured = capsys.readouterr()
    assert captured.out == (
        'Tool> time.get_current_date({"timezone":"Europe/Istanbul"})\nreply: What date is it?\n'
    )


def test_interactive_session_handles_help_empty_input_and_exit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    agent = FakeAgent()

    run_session(
        agent,
        read_message=_reader("/help", "  ", "Hello", "/exit"),
    )

    captured = capsys.readouterr()
    assert "Personal OS read-only chat (test-model)" in captured.out
    assert "Commands: /help, /exit, /quit" in captured.out
    assert "Assistant> reply: Hello" in captured.out
    assert captured.out.endswith("Goodbye.\n")
    assert agent.messages == ["Hello"]


def test_interactive_session_handles_eof(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def end_of_input() -> str:
        raise EOFError

    run_session(FakeAgent(), read_message=end_of_input)

    captured = capsys.readouterr()
    assert captured.out.endswith("Goodbye.\n")


def test_command_supports_one_shot_message(monkeypatch: pytest.MonkeyPatch) -> None:
    received: list[str | None] = []
    monkeypatch.setattr(
        "personal_os.chat_cli._run_configured_chat",
        received.append,
    )

    result = runner.invoke(app, ["--message", "Hello"])

    assert result.exit_code == 0
    assert received == ["Hello"]


def test_command_rejects_empty_one_shot_message() -> None:
    result = runner.invoke(app, ["--message", "   "])

    assert result.exit_code == 2
    assert "message cannot be empty" in result.stderr
