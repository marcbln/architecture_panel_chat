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
