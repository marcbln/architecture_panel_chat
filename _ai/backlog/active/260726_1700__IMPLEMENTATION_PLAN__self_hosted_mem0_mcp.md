---
filename: "_ai/backlog/active/260726_1700__IMPLEMENTATION_PLAN__self_hosted_mem0_mcp.md"
title: "Self-Hosted Mem0 MCP Persistent Memory Integration"
createdAt: 2026-07-26 17:00
updatedAt: 2026-07-26 17:00
status: draft
priority: high
tags: [mem0, mcp, agents, memory, isolation, python]
estimatedComplexity: moderate
documentType: IMPLEMENTATION_PLAN
---

## 1. Problem Description

The multi-agent codebase architecture panel chat lacks persistent memory across interactive CLI runs. Currently, when a user restarts the CLI or targets a different repository, any context about chosen design paradigms, specific framework guidelines, deployment models, database constraints, or local developer preferences is lost. 

Without long-term memory, the moderator agent must be repeatedly re-instructed on context. Furthermore, memories must be kept strictly isolated between separate repositories to prevent architectural guidelines from project A bleeding into the analysis of project B.

## 2. Executive Summary

This plan introduces support for persistent, project-isolated long-term memory using a **self-hosted Mem0 backend** and the **Model Context Protocol (MCP)**. 

By leveraging Pydantic AI's `MCPToolset` and fastmcp Stdio transport client, the application will automatically spawn and communicate with `mem0-mcp-server` as a subprocess. Scoped project isolation is achieved dynamically: the moderator agent is dynamically instructed to map the target codebase's directory name to the `app_id` parameter of all memory tool calls (e.g., `add_memory` and `search_memories`). 

The command loop in `chat_cmd.py` will be updated to manage the MCP connection lifecycle utilizing Pydantic AI's `async with moderator` context manager, while the terminal UI will highlight active memory transactions in real time.

## 3. Project Environment Details

- Project Name: Python Project
- Frontend root: frontend
- Backend root: src

---

## Phase 1: Dependency Integration

In this phase, we add the required libraries to `pyproject.toml` to support the Model Context Protocol (MCP) clients and dependencies. We explicitly install the `mcp` extra on `pydantic-ai`.

### 1.1 Update `pyproject.toml` [MODIFY]

```toml
# ... existing content ...
[project]
name = "python-project"
version = "0.1.0"
description = "Multi-Agent Architecture Panel Chat Tool"
requires-python = ">=3.12"
dependencies = [
    "pydantic-ai[mcp]>=2.0.0",
    "typer>=0.12.0",
    "rich>=13.7.0",
]
# ... rest of content ...
```

---

## Phase 2: Agent Memory Integration

In this phase, we import the MCP tooling directly at the top level of `agents.py` so that environment/dependency failures fail loudly and transparently on startup. We then initialize the `mem0-mcp-server` toolset directed at the local self-hosted API (by default `http://127.0.0.1:8888`), register it to the moderator agent, and append dynamic scoping instructions to partition memory by workspace directory.

### 2.1 Update `src/arch_panel/core/agents.py` [MODIFY]

```python
import os
from typing import Literal

from fastmcp.client.transports import StdioTransport
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPToolset

from .capabilities import codebase_inspector
from .context import CodebaseContext

LLM_MODEL = os.getenv("OPENAI_MODEL_NAME", "openai:gpt-4o")

EXPERT_STACK = [
    ("db_expert", "Database & State"),
    ("api_expert", "API & Protocols"),
    ("clean_code_expert", "Modularity & Clean Code"),
]

# --- Self-Hosted Mem0 Setup ---
# Directs API calls to the local container's port map "127.0.0.1:8888:8000"
MEM0_BASE_URL = os.getenv("MEM0_BASE_URL", "http://127.0.0.1:8888")
# If the self-hosted instance has auth disabled, default to a placeholder
MEM0_API_KEY = os.getenv("MEM0_API_KEY", "none")

# Launch the official mem0-mcp-server via stdio subprocess using uvx on-demand
mem0_transport = StdioTransport(
    command="uvx",
    args=["mem0-mcp-server"],
    env={
        **os.environ,  # Keep environmental context (PATH, system parameters, etc.)
        "MEM0_BASE_URL": MEM0_BASE_URL,
        "MEM0_API_KEY": MEM0_API_KEY,
    }
)
mem0_toolset = MCPToolset(mem0_transport)

# --- Specialist Agents ---
db_expert = Agent(
    LLM_MODEL,
    deps_type=CodebaseContext,
    system_prompt=(
        "You are an expert Database & State Architect. "
        "Your role is to analyze schemas, database calls, data structures, and persistent layers. "
        "Identify inefficiencies, scaling bottlenecks, index problems, and query antipatterns."
    ),
    capabilities=[codebase_inspector],
)

api_expert = Agent(
    LLM_MODEL,
    deps_type=CodebaseContext,
    system_prompt=(
        "You are an expert API & Protocols Architect. "
        "Your role is to analyze web interfaces, data serializations, authentication flows, "
        "and integration protocols (REST, GraphQL, gRPC, WebSocket, or message brokers). "
        "Focus on protocol security, edge configurations, and schema validation."
    ),
    capabilities=[codebase_inspector],
)

clean_code_expert = Agent(
    LLM_MODEL,
    deps_type=CodebaseContext,
    system_prompt=(
        "You are a Modularity, SOLID, and Clean Code Architect. "
        "Your role is to analyze separation of concerns, modular coupling, "
        "structural scaffolding, readabilities, and code hygiene patterns. "
        "Apply standard SOLID and clean code rules strictly."
    ),
    capabilities=[codebase_inspector],
)

# --- Moderator Agent ---
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
    capabilities=[codebase_inspector],
    toolsets=[mem0_toolset],
)


@moderator.tool
async def consult_expert(
    ctx: RunContext[CodebaseContext],
    expert_name: Literal["db_expert", "api_expert", "clean_code_expert"],
    consultation_request: str,
) -> str:
    experts = {
        "db_expert": db_expert,
        "api_expert": api_expert,
        "clean_code_expert": clean_code_expert,
    }

    if expert_name not in experts:
        return f"Error: Expert '{expert_name}' is not recognized. Choose from: {list(experts.keys())}"

    expert_agent = experts[expert_name]
    result = await expert_agent.run(consultation_request, deps=ctx.deps)
    return f"\n=== {expert_name.upper()} ANALYSIS ===\n{result.output}\n=========================="


# --- Scoped Project Memories Dynamic Instructions ---
@moderator.system_prompt
def memory_instructions(ctx: RunContext[CodebaseContext]) -> str:
    # Dynamically determine the target directory's folder name to partition workspace memory
    project_id = ctx.deps.root_path.name
    user_id = os.getenv("MEM0_USER_ID", "default_user")

    return (
        f"\n--- LONG-TERM PERSISTENT MEMORY (SELF-HOSTED MEM0) ---\n"
        f"You are connected to a private self-hosted Mem0 instance (on port 8888) via MCP.\n"
        f"You have tools like `add_memory` and `search_memories` to retrieve and store project facts.\n\n"
        f"STRICT DIRECTORY-ISOLATION POLICY:\n"
        f"To keep codebase memories isolated per workspace, you MUST pass these exact parameters "
        f"on every call to memory management tools:\n"
        f"  - `app_id`: '{project_id}'\n"
        f"  - `user_id`: '{user_id}'\n\n"
        f"OPERATIONAL STRATEGY:\n"
        f"1. On the user's first query, proactively call `search_memories` with the `app_id` "
        f"set to '{project_id}' to discover any previously saved decisions or coding styles.\n"
        f"2. When a definitive rule or choice is agreed upon (e.g. 'We use PostgreSQL with SQLAlchemy', "
        f"or 'Use fastAPI for all endpoints'), persist it immediately via `add_memory` so it is "
        f"available in the next terminal session."
    )
```

---

## Phase 3: CLI Command and Lifecycle Management

To run an agent using stdio-based MCP servers, Pydantic AI requires wrapping the active execution segment in an `async with moderator` block. This orchestrates client startup, registers the dynamic tools, and cleans up background child processes correctly.

In this phase, we update `chat_cmd.py` to support this context manager, register the memory tools to the rendering subsystem, and update capability panel visuals.

### 3.1 Update `src/arch_panel/commands/chat_cmd.py` [MODIFY]

```python
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
    "add_memory": "Mem0 Memory Layer",
    "search_memories": "Mem0 Memory Layer",
    "get_memories": "Mem0 Memory Layer",
    "update_memory": "Mem0 Memory Layer",
    "delete_memory": "Mem0 Memory Layer",
}

EXPERT_NAME_LABEL: dict[str, str] = dict(EXPERT_STACK)

CAPABILITY_STYLE: dict[str, str] = {
    "Orchestration": "cyan",
    "Codebase Inspector": "blue",
    "Database & State": "green",
    "API & Protocols": "yellow",
    "Modularity & Clean Code": "magenta",
    "Thinking": "white",
    "Mem0 Memory Layer": "purple",
}

CAPABILITY_STACK = ["Orchestration", "Codebase Inspector", "Mem0 Memory Layer"] + [
    label for _, label in EXPERT_STACK
]


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
                    async with moderator:
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
```

---

## Phase 4: Verification and Quality Checks

In this phase, we run validation scripts and make sure tests continue to work correctly without needing an active connection to Mem0. The capability unit tests in `tests/test_capabilities.py` do not execute any LLM or agent runs directly, so they should not make any subprocess or internet calls.

### 4.1 Execute Tests
Ensure tests pass without network or subprocess requirements:
```bash
uv run pytest
```

### 4.2 Linter and Type Check verification
Verify that formatting, linting, and typecheck constraints are met:
```bash
uv run black src/ tests/
uv run ruff check src/ tests/
uv run mypy src/
```

---

## Phase 5: Housekeeping & Documentation Updates

We update files to document the dependency requirements and explain how to boot and configure the CLI client to interact with the self-hosted container instance.

### 5.1 Update `AGENTS.md` [MODIFY]

```markdown
# ... existing content ...

## Environment

- `OPENAI_API_KEY` — **required**
- `OPENAI_MODEL_NAME` — default `openai:gpt-4o`
- `MEM0_BASE_URL` — default `http://127.0.0.1:8888` (Points to self-hosted Mem0 container mapping)
- `MEM0_API_KEY` — default `none` (Set if self-hosted instance has authentication configured)
- `MEM0_USER_ID` — default `default_user` (Scopes memories to a developer identity)

## Structure

```
src/arch_panel/
├── cli.py              — Typer entrypoint (arch-panel)
├── commands/chat_cmd.py — interactive chat loop
├── core/
│   ├── agents.py       — moderator + 3 specialist agents, consult_expert tool, Mem0 MCP integration
│   ├── capabilities.py — list_files, read_file (sandboxed to root)
│   └── context.py      — CodebaseContext dataclass (root_path only)
├── config.py
tests/
└── test_capabilities.py
```

# ... rest of content ...
```

### 5.2 Update `CHANGELOG.md` [MODIFY]

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-07-26

### Added
- Long-term persistent memory support using a self-hosted Mem0 API backend.
- Scoped project isolation mapping the directory name to memory queries as `app_id`.
- Standard MCP integration utilizing `pydantic-ai[mcp]` and `fastmcp`.
- Visual memory capability updates in the Rich CLI terminal interface.

# ... rest of content ...
```

---

## Phase 6: Report Generation

Write an implementation report reflecting these architectural changes.

### 6.1 Create `_ai/backlog/reports/260726_1700__IMPLEMENTATION_REPORT__self_hosted_mem0_mcp.md` [NEW FILE]

```markdown
---
filename: "_ai/backlog/reports/260726_1700__IMPLEMENTATION_REPORT__self_hosted_mem0_mcp.md"
title: "Report: Self-Hosted Mem0 MCP Persistent Memory Integration"
createdAt: 2026-07-26 17:00
updatedAt: 2026-07-26 17:00
planFile: "_ai/backlog/active/260726_1700__IMPLEMENTATION_PLAN__self_hosted_mem0_mcp.md"
project: "Python Project"
status: completed
filesCreated: 1
filesModified: 4
filesDeleted: 0
tags: [mem0, mcp, agents, memory, isolation, python]
documentType: IMPLEMENTATION_REPORT
---

## 1. Summary
We have successfully implemented project-isolated long-term memory support for the `arch-panel` CLI. By connecting the CLI with a self-hosted Mem0 instance using Model Context Protocol (MCP) clients, the moderator agent now records and retrieves architectural decisions on a per-project basis.

## 2. Files Changed

### New Files Created:
- `_ai/backlog/reports/260726_1700__IMPLEMENTATION_REPORT__self_hosted_mem0_mcp.md`: The active implementation summary report.

### Modified Files:
- `pyproject.toml`: Added the `pydantic-ai[mcp]` dependency extra.
- `src/arch_panel/core/agents.py`: Integrated `MCPToolset` with Mem0 parameters and dynamic directory scoping logic.
- `src/arch_panel/commands/chat_cmd.py`: Wrapped model execution inside the `async with moderator` context manager, and updated capability layout visuals.
- `AGENTS.md`: Outlined Mem0 configuration environments.
- `CHANGELOG.md`: Notated the version update details.

## 3. Key Changes
- Added `pydantic-ai[mcp]` configuration to the project dependencies.
- Added top-level imports of `fastmcp.client.transports.StdioTransport` and `pydantic_ai.mcp.MCPToolset` in `agents.py` to ensure dependency problems fail fast.
- Configured dynamic system prompts on the `moderator` agent to automatically inject `app_id` and `user_id` context into memory operations, ensuring directory isolation.
- Integrated the `async with moderator` context block to control the launch and destruction of the child `mem0-mcp-server` process.
- Updated Rich terminal UI panels to render active `add_memory` and `search_memories` actions during discussions.

## 4. Deviations from Plan
There were no deviations; the execution was implemented directly as planned. Defensive try-except handlers on imports were intentionally excluded to maintain robust environment checks and avoid silent error states.

## 5. Technical Decisions
- **Dynamic Isolation Mapping**: Using the targeted workspace directory name `ctx.deps.root_path.name` as `app_id` was chosen because it does not require additional user inputs, maintaining an effortless isolation layer.
- **Fail-Fast Imports**: Moving the MCP client imports to the top level forces immediate, understandable traceback logs if the user environment lacks the required tools.

## 6. Testing Notes
Verify functionality by:
1. Booting your local self-hosted Mem0 container via `docker compose up -d`.
2. Launching the panel `uv run arch-panel chat` and informing the agent of an architectural rule.
3. Exiting the terminal, returning to the CLI, and checking if the memory persists across runs.
4. Ensuring tests run locally without side effects: `uv run pytest`.

## 7. Usage Examples
Configure environments:
```bash
export OPENAI_API_KEY="sk-..."
export MEM0_BASE_URL="http://127.0.0.1:8888"
export MEM0_API_KEY="none"
export MEM0_USER_ID="dev_lead"
```

Start analyzing a specific repository:
```bash
uv run arch-panel chat --target /path/to/some_workspace
```

