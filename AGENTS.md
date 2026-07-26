# AGENTS.md — Architecture Panel Chat

## Project

Multi-agent terminal chat app using **PydanticAI v2** that analyzes codebase architecture. Three specialist agents (`db_expert`, `api_expert`, `clean_code_expert`) are orchestrated by a `moderator` agent.

## Quick start

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Prerequisites

- **Self-hosted Mem0 backend** (for persistent memory) — Docker compose with PostgreSQL + Neo4j.
  See [docs](https://docs.mem0.ai) for setup. The API server must be reachable at `MEM0_BASE_URL`.

## Commands

| Action | Command |
|---|---|
| Run app | `uv run arch-panel chat` |
| Target dir | `uv run arch-panel chat --target /path` |
| Run tests | `uv run pytest` |
| Format | `uv run black src/ tests/` |
| Lint | `uv run ruff check src/ tests/` |
| Typecheck | `uv run mypy src/` |

Run lint → typecheck → test in that order before committing.

## Environment

- `OPENAI_API_KEY` — **required**
- `OPENAI_MODEL_NAME` — default `openai:gpt-4o`
- `MEM0_BASE_URL` — default `http://127.0.0.1:8888` (Points to self-hosted Mem0 container mapping)
- `MEM0_API_KEY` — default `""` (API key or JWT for server authentication)
- `MEM0_USER_ID` — default `default_user` (Scopes memories to a developer identity)

## Structure

```
src/arch_panel/
├── cli.py              — Typer entrypoint (arch-panel)
├── commands/chat_cmd.py — interactive chat loop
├── core/
│   ├── agents.py       — moderator + 3 specialist agents, consult_expert tool, Mem0 REST API integration
│   ├── capabilities.py — list_files, read_file (sandboxed to root)
│   └── context.py      — CodebaseContext dataclass (root_path only)
├── config.py
tests/
└── test_capabilities.py
```

## Gotchas

- Tests use `tmp_path` fixtures, no external services.
- `list_files` caps output at **80 files** and only allows configured extensions (`.py`, `.ts`, `.json`, etc.). Ignores `.git`, `venv`, `__pycache__`, etc.
- `read_file` blocks path traversal outside `root_path`.
- Install must use `uv pip install -e ".[dev]"` (not `uv sync` — no lockfile for dev extras).
