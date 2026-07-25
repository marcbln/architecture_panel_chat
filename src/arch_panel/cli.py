from pathlib import Path

import typer

from .commands.chat_cmd import run_chat
from .config import CLI_CONTEXT_SETTINGS

app = typer.Typer(
    name="arch-panel",
    context_settings=CLI_CONTEXT_SETTINGS,
    no_args_is_help=True,
    help="Interactive multi-agent panel CLI to analyze codebase architecture.",
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    target: Path = typer.Option(  # noqa: B008
        Path("."),
        "--target",
        "-t",
        help="Path to the codebase workspace to analyze.",
    ),
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    run_chat(target.resolve())
