import asyncio
import json
from pathlib import Path

import typer
from pydantic_ai.messages import ModelMessage, ModelResponse, ThinkingPart, ToolCallPart
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from ..core.agents import EXPERT_STACK, LLM_MODEL, moderator
from ..core.context import CodebaseContext

console = Console()

TOOL_TO_CAPABILITY: dict[str, str] = {
    "consult_expert": "Orchestration",
    "list_files": "Codebase Inspector",
    "read_file": "Codebase Inspector",
}

EXPERT_NAME_LABEL: dict[str, str] = dict(EXPERT_STACK)

CAPABILITY_STYLE: dict[str, str] = {
    "Orchestration": "cyan",
    "Codebase Inspector": "blue",
    "Database & State": "green",
    "API & Protocols": "yellow",
    "Modularity & Clean Code": "magenta",
    "Thinking": "white",
}

CAPABILITY_STACK = ["Orchestration", "Codebase Inspector"] + [label for _, label in EXPERT_STACK]


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


def _fmt_args(part: ToolCallPart) -> str:
    args = part.args
    if isinstance(args, dict):
        items = []
        for k, v in args.items():
            if not k.startswith("_"):
                items.append(f"{k}={v!r}")
        return ", ".join(items)
    return str(args)


def _capabilities_used(new_messages: list[ModelMessage]) -> list[tuple[str, str]]:
    used: list[tuple[str, str]] = []
    thought = False
    for msg in new_messages:
        if not isinstance(msg, ModelResponse):
            continue
        for part in msg.parts:
            if isinstance(part, ToolCallPart):
                base_cap = TOOL_TO_CAPABILITY.get(part.tool_name, part.tool_name)
                if part.tool_name == "consult_expert":
                    args = part.args
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            pass
                    expert_name = args.get("expert_name", "") if isinstance(args, dict) else ""
                    label = EXPERT_NAME_LABEL.get(expert_name, base_cap)
                    used.append((label, f"consult_expert({_fmt_args(part)})"))
                else:
                    used.append((base_cap, f"{part.tool_name}({_fmt_args(part)})"))
            elif isinstance(part, ThinkingPart):
                thought = True
    if thought:
        used.append(("Thinking", "reasoned before answering"))
    return used


def _render_used(used: list[tuple[str, str]]) -> Panel:
    body = Table.grid(padding=(0, 1))
    body.add_column()

    fired = {cap for cap, _ in used}
    header = Text()
    header.append(f"composed from {len(CAPABILITY_STACK)} ", style="dim")
    header.append("capabilities", style="dim")
    header.append(":  ", style="dim")
    for i, cap in enumerate(CAPABILITY_STACK):
        style = CAPABILITY_STYLE.get(cap, "white")
        header.append(cap, style=style if cap in fired else "dim")
        if cap in fired:
            header.append(" \u25cf", style=style)
        if i < len(CAPABILITY_STACK) - 1:
            header.append("   ")
    body.add_row(header)

    if used:
        body.add_row("")
        for cap, detail in used:
            style = CAPABILITY_STYLE.get(cap, "white")
            row = Text()
            row.append(f"\u25aa {cap}  ", style=f"bold {style}")
            row.append(detail, style="dim")
            body.add_row(row)
    else:
        body.add_row(Text("\u25aa answered directly, no tools this turn", style="dim"))

    return Panel(
        body,
        title="[bold]capabilities used this turn[/bold]",
        title_align="left",
        border_style="blue",
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

                used = _capabilities_used(result.new_messages())
                console.print(_render_used(used))

                message_history = result.all_messages()

            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Exited chat session.[/yellow]")
                break

    asyncio.run(_async_loop())
