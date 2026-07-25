import typer
from .config import CLI_CONTEXT_SETTINGS
from .commands.chat_cmd import chat_command

app = typer.Typer(
    name="arch-panel",
    context_settings=CLI_CONTEXT_SETTINGS,
    no_args_is_help=True,
    help="Interactive multi-agent panel CLI to analyze codebase architecture.",
)

app.command(name="chat")(chat_command)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
