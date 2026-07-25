---
filename: "_ai/backlog/active/260725_1633__IMPLEMENTATION_PLAN__architecture_panel_chat.md"
title: "Multi-Agent Codebase Architecture Panel Chat"
createdAt: 2026-07-25 16:33
updatedAt: 2026-07-25 16:33
status: draft
priority: high
tags: [pydantic-ai-v2, multi-agent, architecture-review, typer, python]
estimatedComplexity: moderate
documentType: IMPLEMENTATION_PLAN
---

## 1. Problem Statement

When analyzing a large or complex software codebase, developer questions are rarely one-dimensional. They span across database schemas, protocol design, API routing, architectural patterns, separation of concerns, and clean code conventions. Relying on a single generalist AI agent often yields shallow answers or fails to present healthy dialectics (constructive debates regarding architectural tradeoffs). Developers must manually guide the AI through different architectural concerns, leading to an inefficient brainstorming process.

Furthermore, early multi-agent frameworks require complex tool registration and prompt duplication for every sub-agent, making multi-agent codebase analysis difficult to build, maintain, and execute cleanly within a single type-safe context.

## 2. Executive Summary

This plan introduces a type-safe **Multi-Agent Architecture Panel Chat** CLI using the **PydanticAI V2** agentic framework. 

The application utilizes a **Moderator-Expert (Orchestrator-Specialist)** pattern where a Lead Architect (Moderator Agent) coordinates specialized sub-agents:
1.  **Database Expert (`db_expert`)**: Focuses on data models, queries, indexes, and storage.
2.  **API & Integration Expert (`api_expert`)**: Focuses on protocols, serializers, web routing, and security.
3.  **Clean Code Expert (`clean_code_expert`)**: Focuses on SOLID design principles, modular boundaries, and code modularity.

We leverage **PydanticAI V2's core feature: the Capability primitive**. Rather than registering file system reading tools on every agent manually, we build a single `CodebaseInspector` capability that bundles file listing/reading tools. This capability is injected seamlessly into both the moderator and the specialists. 

The user interacts with a unified interactive chat session managed by the Moderator. The Moderator dynamically delegates analysis tasks using a custom `consult_expert` tool, which starts a type-safe sub-run, passing down the target project's `CodebaseContext` dependency seamlessly.

## 3. Project Environment Details

- Project Name: Python Project
- Frontend root: frontend
- Backend root: src

---

## 4. Multi-Phase Implementation Plan

### Phase 1: Dependency & Environment Setup
Ensure standard tooling and environment dependencies are configured using the `uv` package manager.

#### [MODIFY] `pyproject.toml`
Add required production dependencies (`pydantic-ai>=2.0.0`, `typer`, `rich`) and development testing dependencies (`pytest`, `ruff`, `mypy`).

```toml
# ... existing fields ...

[project]
name = "python-project"
version = "0.1.0"
description = "Multi-Agent Architecture Panel Chat Tool"
requires-python = ">=3.12"
dependencies = [
    "pydantic-ai>=2.0.0",
    "typer>=0.12.0",
    "rich>=13.7.0",
    "pyyaml>=6.0.1",
    "python-dotenv>=1.0.1",
]

[project.scripts]
arch-panel = "arch_panel.cli:app"

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",
    "black>=24.0.0",
    "mypy>=1.10.0",
    "ruff>=0.3.0",
]

# ... existing ruff or mypy configs ...
```

---

### Phase 2: Domain Context & Capabilities Architecture

Following clean, modular domain boundaries, we separate the dependencies and codebase inspection tools from the core agent execution loops.

#### [NEW FILE] `src/arch_panel/__init__.py`
Empty initializer file declaring `arch_panel` as a Python package.
```python
"""Multi-Agent Architecture Panel Chat Package."""
```

#### [NEW FILE] `src/arch_panel/core/__init__.py`
Empty package initializer for core systems.
```python
"""Core multi-agent models, state dependencies, and capabilities."""
```

#### [NEW FILE] `src/arch_panel/core/context.py`
Define the context dependencies that will be shared among all agents in our execution loop.
```python
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CodebaseContext:
    """Dependency container containing root path of target codebase.
    
    This is passed through the PydanticAI execution context using RunContext.
    """
    root_path: Path
```

#### [NEW FILE] `src/arch_panel/core/capabilities.py`
Build a reusable PydanticAI V2 `Capability` to inspect codebase files, complete with directory traversal protections.
```python
from typing import List
from pathlib import Path

from pydantic_ai import RunContext
from pydantic_ai.capabilities import Capability

from .context import CodebaseContext


def list_files(ctx: RunContext[CodebaseContext]) -> List[str]:
    """Recursively list all matching code files in the target repository.
    
    Excludes typical environment directories, binaries, and build files.
    """
    root = ctx.deps.root_path
    file_list: List[str] = []
    
    # Common ignore boundaries to prevent token flood
    ignore_dirs = {
        ".git", "node_modules", "venv", "__pycache__", ".venv", 
        "dist", "build", ".mypy_cache", ".pytest_cache", ".ruff_cache"
    }
    allowed_extensions = {".py", ".ts", ".js", ".go", ".rs", ".java", ".json", ".yaml", ".yml", ".md"}
    
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in allowed_extensions:
            if not any(part in ignore_dirs for part in p.parts):
                try:
                    file_list.append(str(p.relative_to(root)))
                except ValueError:
                    continue
                    
    # Cap output files to keep context windows reasonable
    return file_list[:80]


def read_file(ctx: RunContext[CodebaseContext], file_path: str) -> str:
    """Read the content of a specific file inside the target repository path."""
    root = ctx.deps.root_path
    target = (root / file_path).resolve()
    
    # Security block: Directory Traversal Mitigation
    if not target.is_relative_to(root.resolve()):
        return "Access denied: Request path lies outside target codebase root."
        
    try:
        return target.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading target file: {str(e)}"


# Define our custom PydanticAI V2 Capability
codebase_inspector = Capability(
    id="codebase_inspector",
    description="Provides tools to scan the repository structure and read specific source files.",
    tools=[list_files, read_file]
)
```

---

### Phase 3: Specialist Agents & Orchestration Layer

We design the expert agents and coordinate them through our moderator agent using nested sub-runs.

#### [NEW FILE] `src/arch_panel/core/agents.py`
Configure specialized architect roles and define type-safe moderator orchestration loops.
```python
import os
from pydantic_ai import Agent, RunContext
from .context import CodebaseContext
from .capabilities import codebase_inspector

# Retrieve model dynamically or default to OpenAI's GPT-4o
LLM_MODEL = os.getenv("OPENAI_MODEL_NAME", "openai:gpt-4o")

# Database Specialist
db_expert = Agent(
    LLM_MODEL,
    deps_type=CodebaseContext,
    system_prompt=(
        "You are an expert Database & State Architect. "
        "Your role is to analyze schemas, database calls, data structures, and persistent layers. "
        "Identify inefficiencies, scaling bottlenecks, index problems, and query antipatterns."
    ),
    capabilities=[codebase_inspector]
)

# API Specialist
api_expert = Agent(
    LLM_MODEL,
    deps_type=CodebaseContext,
    system_prompt=(
        "You are an expert API & Protocols Architect. "
        "Your role is to analyze web interfaces, data serializations, authentication flows, "
        "and integration protocols (REST, GraphQL, gRPC, WebSocket, or message brokers). "
        "Focus on protocol security, edge configurations, and schema validation."
    ),
    capabilities=[codebase_inspector]
)

# Clean Code Specialist
clean_code_expert = Agent(
    LLM_MODEL,
    deps_type=CodebaseContext,
    system_prompt=(
        "You are a Modularity, SOLID, and Clean Code Architect. "
        "Your role is to analyze separation of concerns, modular coupling, "
        "structural scaffolding, readabilities, and code hygiene patterns. "
        "Apply standard SOLID and clean code rules strictly."
    ),
    capabilities=[codebase_inspector]
)

# Moderator (Orchestration Agent)
moderator = Agent(
    LLM_MODEL,
    deps_type=CodebaseContext,
    system_prompt=(
        "You are the Lead Software Architect and Moderator of a collaborative design review. "
        "Your objective is to coordinate with specialized sub-agents to analyze user codebase queries.\n\n"
        "Operations:\n"
        "1. Identify files relevant to the query using the codebase_inspector capability.\n"
        "2. Consult specialists using the `consult_expert` tool for highly deep-dive areas.\n"
        "3. Synthesize the reports into a cohesive response, resolving any architectural trade-offs."
    ),
    capabilities=[codebase_inspector]
)


@moderator.tool
async def consult_expert(
    ctx: RunContext[CodebaseContext],
    expert_name: str,
    consultation_request: str
) -> str:
    """Delegates a specific sub-investigation to a specialized architect panel member.
    
    Valid values for expert_name: 'db_expert', 'api_expert', 'clean_code_expert'
    """
    experts = {
        "db_expert": db_expert,
        "api_expert": api_expert,
        "clean_code_expert": clean_code_expert
    }
    
    if expert_name not in experts:
        return f"Error: Expert '{expert_name}' is not recognized. Choose from: {list(experts.keys())}"
        
    expert_agent = experts[expert_name]
    
    # Run the subagent asynchronously with thread-safe deps passing
    result = await expert_agent.run(consultation_request, deps=ctx.deps)
    return f"\n=== {expert_name.upper()} ANALYSIS ===\n{result.data}\n=========================="
```

---

### Phase 4: CLI Command & Application Configuration

Create our command structure using Typer, complying with contextual CLI helper settings.

#### [NEW FILE] `src/arch_panel/config.py`
Configure contextual help settings for Typer to support standard default arguments and standard short `-h` help configurations.
```python
CLI_CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
}
```

#### [NEW FILE] `src/arch_panel/commands/__init__.py`
Empty package initializer for command scripts.
```python
"""Typer subcommands."""
```

#### [NEW FILE] `src/arch_panel/commands/chat_cmd.py`
Create the interactive cli loop using the Rich package to stream output and present beautiful panels.
```python
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
    """Internal loop executor handling the async interactive session."""
    async def _async_loop():
        if not target.is_dir():
            console.print(f"[bold red]Error:[/bold red] '{target}' is not a valid directory.")
            raise typer.Exit(code=1)
            
        console.print(
            Panel(
                f"[green]Initialized Architecture Review Board[/green]\n"
                f"Target workspace: [bold blue]{target}[/bold blue]",
                title="PydanticAI V2 Panel"
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
                        message_history=message_history
                    )
                
                console.print(
                    Panel(
                        result.data, 
                        title="[bold green]Lead Architect Synthesizer[/bold green]", 
                        border_style="green"
                    )
                )
                
                # Persist context history
                message_history = result.new_messages()
                
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Exited chat session.[/yellow]")
                break
                
    asyncio.run(_async_loop())


def chat_command(
    target_path: Path = typer.Option(
        Path("."),
        "--target",
        "-t",
        help="Path to the codebase workspace to analyze."
    )
) -> None:
    """Start an interactive review with multiple specialized AI architects."""
    run_chat(target_path.resolve())
```

#### [NEW FILE] `src/arch_panel/cli.py`
Assemble our commands inside the central `cli.py` application file.
```python
import typer
from .config import CLI_CONTEXT_SETTINGS
from .commands.chat_cmd import chat_command

# Initialize Typer with standardized help configurations
app = typer.Typer(
    name="arch-panel",
    context_settings=CLI_CONTEXT_SETTINGS,
    no_args_is_help=True,
    help="Interactive multi-agent panel CLI to analyze codebase architecture."
)

app.command(name="chat")(chat_command)


def main() -> None:
    """Application CLI entry point."""
    app()


if __name__ == "__main__":
    main()
```

---

### Phase 5: Testing and Integration

Verify implementation code correctness using Pytest. We will write mock test cases to ensure the capability structure and delegation loops execute without logic errors.

#### [NEW FILE] `src/arch_panel/utils/__init__.py`
Empty package utility initializer.
```python
"""Helper and debugging utility functions."""
```

#### [NEW FILE] `tests/__init__.py`
Empty package initializer for tests.
```python
"""Tests package."""
```

#### [NEW FILE] `tests/test_capabilities.py`
Ensure our `list_files` and `read_file` tools operate cleanly and security safeguards remain active.
```python
from pathlib import Path
import pytest
from pydantic_ai import RunContext

from arch_panel.core.context import CodebaseContext
from arch_panel.core.capabilities import list_files, read_file


def test_list_files_filtering(tmp_path: Path) -> None:
    """Verify code list ignores typical directories and includes only matching extensions."""
    # Setup dummy directory layout
    (tmp_path / ".git").mkdir()
    (tmp_path / "venv").mkdir()
    (tmp_path / "src").mkdir()
    
    (tmp_path / ".git" / "config").write_text("dummy")
    (tmp_path / "venv" / "some_lib.py").write_text("dummy")
    (tmp_path / "src" / "api.py").write_text("print('hello')")
    (tmp_path / "src" / "schema.json").write_text("{}")
    (tmp_path / "src" / "unsupported.bin").write_text("binary-data")
    
    context = CodebaseContext(root_path=tmp_path)
    
    # Mock RunContext
    class MockRunContext(RunContext[CodebaseContext]):
        def __init__(self, deps: CodebaseContext):
            self.deps = deps
            
    ctx = MockRunContext(deps=context)
    files = list_files(ctx)
    
    # Assertions
    assert "src/api.py" in files
    assert "src/schema.json" in files
    assert ".git/config" not in files
    assert "venv/some_lib.py" not in files
    assert "src/unsupported.bin" not in files


def test_read_file_boundary_security(tmp_path: Path) -> None:
    """Verify reading path traversal outputs standard security error blocks."""
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
    
    # Traverse outside of boundary
    result = read_file(ctx, "../outside/secrets.env")
    assert "Access denied" in result
```

---

### Phase 6: Project Housekeeping & User Documentation

We will update the core tracking structures, build ignores, setup manuals, and logs.

#### [MODIFY] `.gitignore`
Add python dependency artifacts and testing workspace directories to avoid tracking temporary files.
```
# ... existing fields ...

# PydanticAI & Multi-agent review build artifacts
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
_ai/backlog/reports/
```

#### [MODIFY] `README.md`
Provide complete instructions for installation, API key configuration, and execution instructions.
```markdown
# Python Project: Multi-Agent Architecture Panel Chat

An interactive, multi-agent terminal chat application utilizing **PydanticAI V2** to analyze local codebase architecture. It engages specialized AI architects (Database, API, and Modularity specialists) to collaborate and evaluate code structures, schemas, and clean architectural principles.

## Prerequisites & Installation

Ensure you have [uv](https://github.com/astral-sh/uv) installed.

1. Create and activate the virtual environment:
   ```bash
   uv venv
   source .venv/bin/activate
   ```
2. Install the package in editable mode with development configurations:
   ```bash
   uv pip install -e ".[dev]"
   ```

## Configuration

Set your model provider's API key. By default, the application runs on `openai:gpt-4o`:
```bash
export OPENAI_API_KEY="your-api-key"
```
To run a different model, set:
```bash
export OPENAI_MODEL_NAME="openai:gpt-4o-mini"
```

## Running the Application

Analyze code structure in the current directory:
```bash
uv run arch-panel chat
```

Analyze code structure in a specific folder path:
```bash
uv run arch-panel chat --target /path/to/your/codebase
```

## Running Quality Checks and Tests

Run quality suites locally using pytest:
```bash
uv run pytest
```
```

#### [MODIFY] `CHANGELOG.md`
Documenting version 0.1.0 changes.
```markdown
# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-07-25

### Added
- Multi-Agent Architecture Panel Chat application built on PydanticAI V2.
- Interactive Typer CLI with console interface supported by Rich panels and spinners.
- Reusable `codebase_inspector` capability for safe local file reading and listing.
- Specialized architect sub-agents (`db_expert`, `api_expert`, `clean_code_expert`) and automated delegation tool under `moderator` agent.
- Unit testing configuration using pytest for capabilities scanning.
```

---

### Phase 7: Verification & Report Logging

Once modifications and additions are complete, write the implementation report detailing performance, test statistics, and modular configurations.

#### [NEW FILE] `_ai/backlog/reports/260725_1633__IMPLEMENTATION_REPORT__architecture_panel_chat.md`
Generate the finalized execution output tracking files, test verifications, and design reviews.

```yaml
---
filename: "_ai/backlog/reports/260725_1633__IMPLEMENTATION_REPORT__architecture_panel_chat.md"
title: "Report: Multi-Agent Codebase Architecture Panel Chat"
createdAt: 2026-07-25 16:33
updatedAt: 2026-07-25 16:33
planFile: "_ai/backlog/active/260725_1633__IMPLEMENTATION_PLAN__architecture_panel_chat.md"
project: "Python Project"
status: completed
filesCreated: 11
filesModified: 4
filesDeleted: 0
tags: [pydantic-ai-v2, multi-agent, architecture-review, typer, python]
documentType: IMPLEMENTATION_REPORT
---
```

### 1. Summary
We have successfully implemented the Multi-Agent Architecture Panel Chat CLI using **PydanticAI V2**. The system utilizes a central Orchestrator Agent (Moderator) that dynamically delegates deeply technical tasks to specialized sub-agents. These sub-agents have direct codebase access thanks to a shared, custom-built V2 `Capability` called `codebase_inspector`, keeping tools and system contexts clean and decoupled.

### 2. Files Changed
- **New Files Created**:
  - `src/arch_panel/__init__.py`: Package initialization.
  - `src/arch_panel/config.py`: Central Typer context configurations.
  - `src/arch_panel/core/__init__.py`: Core layer metadata.
  - `src/arch_panel/core/context.py`: State dependency definitions.
  - `src/arch_panel/core/capabilities.py`: Shared file inspection capabilities.
  - `src/arch_panel/core/agents.py`: Specialized agents and delegation tools.
  - `src/arch_panel/commands/__init__.py`: Typer command metadata.
  - `src/arch_panel/commands/chat_cmd.py`: Rich terminal chat rendering loops.
  - `src/arch_panel/cli.py`: Main Typer entry point.
  - `tests/test_capabilities.py`: Automated safety and validation suites.
  - `_ai/backlog/reports/260725_1633__IMPLEMENTATION_REPORT__architecture_panel_chat.md`: Finalized implementation tracking.
- **Modified Files**:
  - `pyproject.toml`: Installed `pydantic-ai`, `typer`, `rich`. Added `arch-panel` project script entry.
  - `.gitignore`: Added local test caches and agentic directories.
  - `README.md`: Documented package details and execution procedures.
  - `CHANGELOG.md`: Added version 0.1.0 modifications.

### 3. Key Technical Decisions
- **Custom Capabilities over `@agent.tool`**: Direct reuse of tool parameters across all four agents is enabled cleanly by PydanticAI V2's `Capability` model. This completely eliminates code redundancy.
- **Type-Safe Context Flow**: The `CodebaseContext` is initialized once in the CLI command, injected into the moderator agent run, and passed down directly during specialized sub-runs with `await expert_agent.run(..., deps=ctx.deps)`.
- **Directory Traversal Security**: Built-in path validation ensures agents cannot execute `read_file` commands targeting parent folders (`../`) or external file boundaries.

### 4. Testing Notes
The changes can be verified running automated checks in your virtual environment:
```bash
uv run pytest
```
Verify the interface manually by running a mock review chat:
```bash
uv run arch-panel chat --target ./src
```
```
