"""Typer entry point for the currently implemented harness commands."""

from __future__ import annotations

import json

import typer

from personal_os import __version__
from personal_os.config import ConfigurationError, Settings

app = typer.Typer(
    help="Experimental local harness for the Personal OS planning assistant.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def root(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the application version and exit.",
    ),
) -> None:
    """Run Personal OS Harness commands."""


@app.command("config")
def show_config() -> None:
    """Display effective non-secret configuration."""
    try:
        settings = Settings.from_environment()
    except ConfigurationError as error:
        typer.echo(f"Configuration error: {error}", err=True)
        raise typer.Exit(code=2) from error

    typer.echo(json.dumps(settings.public_summary(), indent=2, sort_keys=True))


def main() -> None:
    app()
