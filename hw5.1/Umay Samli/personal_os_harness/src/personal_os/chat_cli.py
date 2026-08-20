"""Interactive command-line composition for the read-only Personal OS agent."""

from __future__ import annotations

import json
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Annotated, Protocol

import typer

from personal_os.agent import AgentRoundLimitError, AgentTurn, PersonalOsAgent, create_read_agent
from personal_os.config import ConfigurationError, Settings
from personal_os.db.memory import MemoryRepository
from personal_os.db.planning import PlanningRepository
from personal_os.db.postgres import (
    DatabasePool,
    DatabaseUnavailableError,
    create_memory_pool,
    create_planning_pool,
)
from personal_os.providers.ollama_http import ModelCapabilities, OllamaError, OllamaHttpClient
from personal_os.providers.weather import OpenMeteoWeatherProvider
from personal_os.providers.web import DirectHttpWebPageProvider
from personal_os.tools import external_read_tools

_EXIT_COMMANDS = frozenset({"/exit", "/quit", "exit", "quit"})

app = typer.Typer(
    help="Interactive read-only chat with the Personal OS planning agent.",
    add_completion=False,
    invoke_without_command=True,
    no_args_is_help=False,
)


class ChatAgent(Protocol):
    """Agent interface required by the terminal session."""

    def start(self) -> ModelCapabilities: ...

    def run(self, user_content: str) -> AgentTurn: ...


@app.callback()
def chat(
    message: Annotated[
        str | None,
        typer.Option(
            "--message",
            "-m",
            help="Run one message and exit instead of opening an interactive session.",
        ),
    ] = None,
) -> None:
    """Start the configured read-only planning agent."""
    if message is not None and not message.strip():
        raise typer.BadParameter("message cannot be empty", param_hint="--message")

    try:
        _run_configured_chat(message.strip() if message is not None else None)
    except ConfigurationError as error:
        typer.echo(f"Configuration error: {error}", err=True)
        raise typer.Exit(code=2) from error
    except (DatabaseUnavailableError, OllamaError, AgentRoundLimitError) as error:
        typer.echo(f"Chat error: {error}", err=True)
        raise typer.Exit(code=1) from error


def run_session(
    agent: ChatAgent,
    *,
    initial_message: str | None = None,
    read_message: Callable[[], str] | None = None,
) -> None:
    """Run either one message or an interactive terminal conversation."""
    capabilities = agent.start()
    if initial_message is not None:
        _render_turn(agent.run(initial_message), interactive=False)
        return

    typer.echo(f"Personal OS read-only chat ({capabilities.model})")
    typer.echo("Type /help for commands or /exit to leave.")
    reader = read_message or _read_message

    while True:
        try:
            user_content = reader()
        except EOFError:
            typer.echo("\nGoodbye.")
            return
        except KeyboardInterrupt:
            typer.echo("\nGoodbye.")
            return

        normalized = user_content.strip()
        if not normalized:
            continue
        if normalized.lower() in _EXIT_COMMANDS:
            typer.echo("Goodbye.")
            return
        if normalized.lower() == "/help":
            typer.echo("Commands: /help, /exit, /quit")
            typer.echo("The current agent can read planning and memory data but cannot write.")
            continue

        _render_turn(agent.run(normalized), interactive=True)


def _run_configured_chat(initial_message: str | None) -> None:
    settings = Settings.from_environment()
    with _configured_agent(settings) as agent:
        run_session(agent, initial_message=initial_message)


@contextmanager
def _configured_agent(settings: Settings) -> Generator[PersonalOsAgent, None, None]:
    planning_pool = create_planning_pool(settings)
    memory_pool = create_memory_pool(settings)
    opened_pools: list[DatabasePool] = []

    try:
        planning_pool.open()
        opened_pools.append(planning_pool)
        memory_pool.open()
        opened_pools.append(memory_pool)
        yield create_read_agent(
            OllamaHttpClient(settings.ollama),
            PlanningRepository(planning_pool),
            MemoryRepository(memory_pool),
            max_tool_rounds=settings.ollama.max_tool_rounds,
            additional_tools=external_read_tools(
                DirectHttpWebPageProvider(settings.external_context),
                OpenMeteoWeatherProvider(settings.external_context),
                default_timezone=settings.planning.timezone,
            ),
        )
    finally:
        # Close in reverse acquisition order, including when the second pool or
        # Ollama capability check fails during startup.
        for pool in reversed(opened_pools):
            pool.close()


def _read_message() -> str:
    return input("You> ")


def _render_turn(turn: AgentTurn, *, interactive: bool) -> None:
    for tool_call in turn.tool_calls:
        arguments = json.dumps(
            dict(tool_call.arguments),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        typer.echo(f"Tool> {tool_call.name}({arguments})")
    prefix = "Assistant> " if interactive else ""
    typer.echo(f"{prefix}{turn.content}")


def main() -> None:
    """Run the standalone chat console script."""
    app()
