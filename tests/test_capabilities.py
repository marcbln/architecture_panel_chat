import subprocess
from pathlib import Path

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
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=False)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "api.py").write_text("print('hello')")
    (tmp_path / "src" / "data.json").write_text("{}")
    (tmp_path / "Dockerfile").write_text("FROM python:3.12")
    (tmp_path / "generated").mkdir()
    (tmp_path / "generated" / "output.bin").write_text("binary")

    subprocess.run(
        ["git", "add", "src/", "Dockerfile"],
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        capture_output=True,
        timeout=10,
        check=False,
    )

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
