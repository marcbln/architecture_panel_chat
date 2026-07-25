---
filename: "_ai/backlog/active/260726_0102__IMPLEMENTATION_PLAN__gitignore-based-file-listing.md"
title: "Replace extension whitelist with gitignore-aware file listing"
createdAt: 2026-07-26 01:02
updatedAt: 2026-07-26 01:02
status: draft
priority: medium
tags: [capabilities, file-listing, gitignore, codebase-inspection]
estimatedComplexity: moderate
documentType: IMPLEMENTATION_PLAN
---

## 1. Problem Statement

The `list_files` tool in `core/capabilities.py` uses a hardcoded whitelist of file extensions (`.py`, `.ts`, `.json`, etc.) to decide which files to show the AI agents. This gives an incomplete picture — it misses `Dockerfile`, `Makefile`, `.sh`, `.env.example`, `Procfile`, `Cargo.toml` (if `.toml` weren't listed), `CMakeLists.txt`, and any other file type the project actually uses. The whitelist must be manually maintained and inevitably lags behind what real projects contain.

A whitelist also violates the principle of "the project knows itself best" — every project already defines what is meaningful vs. generated/ignored via `.gitignore`.

## 2. Executive Summary

Replace the extension whitelist with a **gitignore-aware listing strategy**:

- **Git repos**: Use `git ls-files --cached --others --exclude-standard` to list all tracked + untracked non-ignored files. This automatically respects `.gitignore` and surfaces every meaningful file in the project regardless of extension.
- **Non-git dirs**: Fall back to a simplified `rglob` scan that only skips common build/artifact directories (no extension whitelist), plus a binary-file guard to avoid unreadable noise.

The 80-file cap is preserved to keep context windows reasonable. The `read_file` tool is unchanged — it already has no extension restrictions.

## 3. Project Environment Details

- Project Name: Python Project
- Frontend root: frontend
- Backend root: src

---

## 4. Multi-Phase Implementation Plan

### Phase 1: Core Implementation — `src/arch_panel/core/capabilities.py`

#### [MODIFY] `src/arch_panel/core/capabilities.py`

Replace the monolithic `list_files` with three internal helpers and a dispatch function:

1. `_is_git_repo(root: Path) -> bool` — checks for `.git` directory.
2. `_list_files_git(root: Path) -> list[str]` — shells out to `git ls-files`.
3. `_list_files_fallback(root: Path) -> list[str]` — directory-blacklist-only `rglob` scan with a text-file heuristic.
4. `list_files` delegates to `_list_files_git` or `_list_files_fallback`.

```python
import subprocess
from pathlib import Path

from pydantic_ai import RunContext
from pydantic_ai.capabilities import Capability

from .context import CodebaseContext


IGNORE_DIRS = {
    ".git", "node_modules", "venv", "__pycache__", ".venv",
    "dist", "build", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".git", ".hg", ".svn",
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
```

**Design notes:**
- `BINARY_EXTENSIONS` is a safety net for the fallback only — git-aware listing defers to `.gitignore` entirely.
- `IGNORE_DIRS` prevents descending into massive artifact trees (e.g. `node_modules`) on fallback.
- If `git ls-files` fails (no git installed, timeout, etc.), we fall through to the rglob fallback rather than returning an empty list.

---

### Phase 2: Tests — `tests/test_capabilities.py`

#### [MODIFY] `tests/test_capabilities.py`

Replace the single test with three targeted tests covering both code paths:

```python
from pathlib import Path
import shutil
import subprocess

from pydantic_ai import RunContext

from arch_panel.core.capabilities import list_files, read_file
from arch_panel.core.context import CodebaseContext


def test_list_files_fallback(tmp_path: Path) -> None:
    (tmp_path / "venv").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "assets").mkdir()

    (tmp_path / "venv" / "some_lib.py").write_text("dummy")
    (tmp_path / "src" / "api.py").write_text("print('hello')")
    (tmp_path / "src" / "schema.json").write_text("{}")
    (tmp_path / "Dockerfile").write_text("FROM python:3.12")
    (tmp_path / "Makefile").write_text("all:\n\techo hi")
    (tmp_path / "script.sh").write_text("echo hi")
    (tmp_path / "assets" / "logo.png").write_text("PNG-header")

    context = CodebaseContext(root_path=tmp_path)

    class MockRunContext(RunContext[CodebaseContext]):
        def __init__(self, deps: CodebaseContext):
            self.deps = deps

    ctx = MockRunContext(deps=context)
    files = list_files(ctx)

    assert "src/api.py" in files
    assert "src/schema.json" in files
    assert "Dockerfile" in files
    assert "Makefile" in files
    assert "script.sh" in files
    assert "venv/some_lib.py" not in files
    assert "assets/logo.png" not in files


def test_list_files_git_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "api.py").write_text("print('hello')")
    (tmp_path / "src" / "data.json").write_text("{}")
    (tmp_path / "Dockerfile").write_text("FROM python:3.12")
    (tmp_path / "generated").mkdir()
    (tmp_path / "generated" / "output.bin").write_text("binary")

    subprocess.run(["git", "add", "src/", "Dockerfile"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, timeout=10)

    (tmp_path / "README.md").write_text("# Project")
    (tmp_path / ".gitignore").write_text("generated/")
    (tmp_path / "generated" / "output2.bin").write_text("more-binary")

    context = CodebaseContext(root_path=tmp_path)

    class MockRunContext(RunContext[CodebaseContext]):
        def __init__(self, deps: CodebaseContext):
            self.deps = deps

    ctx = MockRunContext(deps=context)
    files = list_files(ctx)

    assert "src/api.py" in files
    assert "src/data.json" in files
    assert "Dockerfile" in files
    assert "README.md" in files
    assert "generated/output.bin" not in files
    assert "generated/output2.bin" not in files


def test_read_file_boundary_security(tmp_path: Path) -> None:
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    sensitive_file = outside_dir / "secrets.env"
    sensitive_file.write_text("SECRET_KEY=123")

    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()

    context = CodebaseContext(root_path=sandbox_dir)

    class MockRunContext(RunContext[CodebaseContext]):
        def __init__(self, deps: CodebaseContext):
            self.deps = deps

    ctx = MockRunContext(deps=context)

    result = read_file(ctx, "../outside/secrets.env")
    assert "Access denied" in result
```

**Key test assertions:**
- **Fallback test**: No git repo → `Dockerfile`, `Makefile`, `.sh` are now listed (they were missed by the old whitelist). Binary `.png` is still excluded.
- **Git test**: Tracked files (`src/api.py`, `Dockerfile`) and untracked non-ignored (`README.md`) appear. The `generated/` dir is gitignored so neither its tracked file from an earlier commit nor its untracked file shows up. This validates `.gitignore` is respected.

---

### Phase 3: Project Housekeeping

#### [MODIFY] `CHANGELOG.md`

Add an entry under `[0.2.0]` (or increment as appropriate):

```markdown
## [0.2.0] - 2026-07-26

### Changed
- `list_files` now uses `git ls-files` for git repositories, respecting `.gitignore` instead of a hardcoded extension whitelist. Non-git directories fall back to a directory-blacklist scan with binary-extension filtering.
- `Dockerfile`, `Makefile`, shell scripts, and other extension-less files are now visible to agents.
```

No changes needed to `.gitignore` or `README.md` — the project structure and usage instructions are unchanged. The CLI interface is identical.

---

### Phase 4: Implementation Report

#### [NEW FILE] `_ai/backlog/reports/260726_0102__IMPLEMENTATION_REPORT__gitignore-based-file-listing.md`

After implementation, write the report. (Template constructed below for reference; actual reporting will be done after implementation.)

```markdown
---
filename: "_ai/backlog/reports/260726_0102__IMPLEMENTATION_REPORT__gitignore-based-file-listing.md"
title: "Report: Replace extension whitelist with gitignore-aware file listing"
createdAt: 2026-07-26 01:02
updatedAt: 2026-07-26 01:02
planFile: "_ai/backlog/active/260726_0102__IMPLEMENTATION_PLAN__gitignore-based-file-listing.md"
project: "Python Project"
status: completed
filesCreated: 1
filesModified: 2
filesDeleted: 0
tags: [capabilities, file-listing, gitignore, codebase-inspection]
documentType: IMPLEMENTATION_REPORT
---

### 1. Summary

Replaced the hardcoded file-extension whitelist in `list_files` with a gitignore-aware strategy. Git repositories now use `git ls-files` to discover all tracked + untracked non-ignored files; non-git directories fall back to a directory-blacklist scan with binary-extension filtering. This surfaces previously invisible files (`Dockerfile`, `Makefile`, `.sh`, etc.) to the AI agents while still respecting artifact/build directory exclusion.

### 2. Files Changed

- **New Files**:
  - `_ai/backlog/reports/260726_0102__IMPLEMENTATION_REPORT__gitignore-based-file-listing.md` — This report.
- **Modified Files**:
  - `src/arch_panel/core/capabilities.py` — Replaced monolithic `list_files` with git-aware dispatch + fallback.
  - `tests/test_capabilities.py` — Replaced single test with three targeted tests (fallback, git, security).
- **Deleted Files**: None.

### 3. Key Changes

- Added `_is_git_repo()` helper — checks for `.git` directory.
- Added `_list_files_git()` — runs `git ls-files --cached --others --exclude-standard` to get the canonical project file list.
- Added `_list_files_fallback()` — `rglob` with directory blacklist + binary extension guard, no extension whitelist.
- Added `BINARY_EXTENSIONS` set for fallback binary filtering.
- Renamed `ignore_dirs` → `IGNORE_DIRS` (module-level constant) and expanded it.
- Updated tests: fallback test verifies `Dockerfile`/`Makefile`/`.sh` are now listed; git test verifies `.gitignore` is respected; security test unchanged.

### 4. Deviations from Plan

None.

### 5. Technical Decisions

- **`BINARY_EXTENSIONS` over magic bytes**: Checking file headers for binary detection would be expensive on large repos. A conservative extension set covers common unreadable formats. The whitelist was removed entirely — the binary set only blocks known-unreadable types.
- **Fallthrough on git failure**: If `git ls-files` fails (no git, timeout, permissions), we degrade to the fallback instead of returning an empty list. This ensures the tool always produces output.

### 6. Testing Notes

```bash
# Run all capability tests
uv run pytest tests/test_capabilities.py -v
```

Expected: 3 passed.

### 7. Usage Examples

No CLI changes — the `arch-panel chat` interface is identical. Internally, running against a git repo now shows all project files:

```
src/api.py
src/data.json
Dockerfile
README.md
```

Previously only `.py` and `.json` would have appeared; `Dockerfile` and `README.md` were invisible.

### 8. Documentation Updates

- `CHANGELOG.md`: Added `[0.2.0]` entry describing the change.

### 9. Next Steps

None.
```

