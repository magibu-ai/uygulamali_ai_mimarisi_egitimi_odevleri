from rich.console import Console

console = Console()


def log_info(message: str) -> None:
    console.print(
        f"[bold cyan]ℹ {message}[/bold cyan]"
    )


def log_planner(message: str = "Planner çalıştırılıyor...") -> None:
    console.print(
        f"[bold magenta]🧠 {message}[/bold magenta]"
    )


def log_tool_start(
    tool_name: str,
    arguments: dict,
) -> None:
    console.print(
        f"[bold yellow]🔍 {tool_name}[/bold yellow] "
        f"[dim]{arguments}[/dim]"
    )


def log_success(message: str) -> None:
    console.print(
        f"[bold green]✅ {message}[/bold green]"
    )


def log_error(message: str) -> None:
    console.print(
        f"[bold red]❌ {message}[/bold red]"
    )