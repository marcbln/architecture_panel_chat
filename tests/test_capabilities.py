from pathlib import Path
import pytest
from pydantic_ai import RunContext

from arch_panel.core.context import CodebaseContext
from arch_panel.core.capabilities import list_files, read_file


def test_list_files_filtering(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "venv").mkdir()
    (tmp_path / "src").mkdir()

    (tmp_path / ".git" / "config").write_text("dummy")
    (tmp_path / "venv" / "some_lib.py").write_text("dummy")
    (tmp_path / "src" / "api.py").write_text("print('hello')")
    (tmp_path / "src" / "schema.json").write_text("{}")
    (tmp_path / "src" / "unsupported.bin").write_text("binary-data")

    context = CodebaseContext(root_path=tmp_path)

    class MockRunContext(RunContext[CodebaseContext]):
        def __init__(self, deps: CodebaseContext):
            self.deps = deps

    ctx = MockRunContext(deps=context)
    files = list_files(ctx)

    assert "src/api.py" in files
    assert "src/schema.json" in files
    assert ".git/config" not in files
    assert "venv/some_lib.py" not in files
    assert "src/unsupported.bin" not in files


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
