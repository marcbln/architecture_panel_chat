import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from ..core.agents import EXPERT_STACK, LLM_MODEL, moderator
from ..core.context import CodebaseContext

console = Console()


def _print_banner(target: Path) -> None:
    grid = Table.grid(padding=(0, 1))
    grid.add_column(justify="right", style="dim")
    grid.add_column()
    grid.add_row("panel", "[bold]Architecture Review Board[/bold]")
    grid.add_row("model", f"[bold]{LLM_MODEL}[/bold]")
    grid.add_row("workspace", f"[bold blue]{target}[/bold blue]")
    for i, (key, label) in enumerate(EXPERT_STACK):
        prefix = "experts" if i == 0 else ""
        grid.add_row(prefix, f"▪ {label}")
    console.print(
        Panel(
            grid,
            title="[bold magenta]Multi-Agent Architecture Panel[/bold magenta]",
            subtitle="[dim]/help for commands · /exit to quit[/dim]",
            border_style="magenta",
        )
    )


def run_chat(target: Path) -> None:
    async def _async_loop():
        if not target.is_dir():
            console.print(f"[bold red]Error:[/bold red] '{target}' is not a valid directory.")
            raise typer.Exit(code=1)

        _print_banner(target)

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
