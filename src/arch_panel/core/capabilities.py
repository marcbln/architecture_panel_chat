
from pydantic_ai import RunContext
from pydantic_ai.capabilities import Capability

from .context import CodebaseContext


def list_files(ctx: RunContext[CodebaseContext]) -> list[str]:
    root = ctx.deps.root_path
    file_list: list[str] = []

    ignore_dirs = {
        ".git", "node_modules", "venv", "__pycache__", ".venv",
        "dist", "build", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    }
    allowed_extensions = {
        ".py", ".ts", ".js", ".go", ".rs", ".java", ".json", ".yaml", ".yml", ".md",
        ".php", ".xml", ".twig", ".vue", ".scss", ".css", ".html", ".csv", ".toml",
    }

    for p in root.rglob("*"):
        if p.is_file() and p.suffix in allowed_extensions and not any(part in ignore_dirs for part in p.parts):
            try:
                file_list.append(str(p.relative_to(root)))
            except ValueError:
                continue

    return file_list[:80]


def read_file(ctx: RunContext[CodebaseContext], file_path: str) -> str:
    root = ctx.deps.root_path
    target = (root / file_path).resolve()

    if not target.is_relative_to(root.resolve()):
        return "Access denied: Request path lies outside target codebase root."

    try:
        return target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return f"Error reading target file: {e!s}"


codebase_inspector = Capability(
    id="codebase_inspector",
    description="Provides tools to scan the repository structure and read specific source files.",
    tools=[list_files, read_file],
)
