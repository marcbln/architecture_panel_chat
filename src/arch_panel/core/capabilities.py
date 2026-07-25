import subprocess
from pathlib import Path

from pydantic_ai import RunContext
from pydantic_ai.capabilities import Capability

from .context import CodebaseContext

IGNORE_DIRS = {
    ".git", "node_modules", "venv", "__pycache__", ".venv",
    "dist", "build", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".hg", ".svn",
}

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pyc", ".pyo", ".so", ".dll", ".dylib",
    ".zip", ".tar", ".gz", ".bz2", ".xz",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".mp3", ".mp4", ".avi", ".mov",
    ".o", ".a", ".lib",
    ".db", ".sqlite", ".sqlite3",
}


def _is_git_repo(root: Path) -> bool:
    return (root / ".git").is_dir()


def _list_files_git(root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.splitlines() if f.strip()][:80]


def _list_files_fallback(root: Path) -> list[str]:
    file_list: list[str] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in IGNORE_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in BINARY_EXTENSIONS:
            continue
        try:
            file_list.append(str(p.relative_to(root)))
        except ValueError:
            continue
    return file_list[:80]


def list_files(ctx: RunContext[CodebaseContext]) -> list[str]:
    root = ctx.deps.root_path
    if _is_git_repo(root):
        files = _list_files_git(root)
        if files:
            return files
    return _list_files_fallback(root)


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
