import asyncio
from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from ..core.context import CodebaseContext
from ..core.agents import moderator

console = Console()


def run_chat(target: Path) -> None:
    async def _async_loop():
        if not target.is_dir():
            console.print(f"[bold red]Error:[/bold red] '{target}' is not a valid directory.")
            raise typer.Exit(code=1)

        console.print(
            Panel(
                f"[green]Initialized Architecture Review Board[/green]\n"
                f"Target workspace: [bold blue]{target}[/bold blue]",
                title="PydanticAI V2 Panel",
            )
        )

        context = CodebaseContext(root_path=target)
        message_history = []

        while True:
            try:
                user_msg = Prompt.ask("\n[bold cyan]You[/bold cyan]")
                if user_msg.strip().lower() in {"exit", "quit"}:
                    console.print("[yellow]Review board adjourned.[/yellow]")
                    break

                if not user_msg.strip():
                    continue

                with console.status("[bold green]Panel discussing codebase files...[/bold green]"):
                    result = await moderator.run(
                        user_msg,
                        deps=context,
                        message_history=message_history,
                    )

                console.print(
                    Panel(
                        result.output,
                        title="[bold green]Lead Architect Synthesizer[/bold green]",
                        border_style="green",
                    )
                )

                message_history = result.all_messages()

            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Exited chat session.[/yellow]")
                break

    asyncio.run(_async_loop())


def chat_command(
    target_path: Path = typer.Option(
        Path("."),
        "--target",
        "-t",
        help="Path to the codebase workspace to analyze.",
    ),
) -> None:
    """Start an interactive review with multiple specialized AI architects."""
    run_chat(target_path.resolve())
