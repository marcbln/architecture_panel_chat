import os
from typing import Literal

import httpx
from pydantic_ai import Agent, RunContext

from .capabilities import codebase_inspector
from .context import CodebaseContext

LLM_MODEL = os.getenv("OPENAI_MODEL_NAME", "openai:gpt-4o")

EXPERT_STACK = [
    ("db_expert", "Database & State"),
    ("api_expert", "API & Protocols"),
    ("clean_code_expert", "Modularity & Clean Code"),
]

# --- Self-Hosted Mem0 REST API ---
MEM0_BASE_URL = os.getenv("MEM0_BASE_URL", "http://127.0.0.1:8888")
MEM0_API_KEY = os.getenv("MEM0_API_KEY", "")


def _mem0_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if MEM0_API_KEY:
        headers["X-API-Key"] = MEM0_API_KEY
    return headers


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


@moderator.tool
async def add_memory(
    ctx: RunContext[CodebaseContext],
    text: str,
) -> str:
    """Store a fact or decision in persistent long-term memory.

    Call this when the user agrees on a definitive rule, architectural decision,
    or coding convention that should persist across sessions.
    """
    project_id = ctx.deps.root_path.name
    user_id = os.getenv("MEM0_USER_ID", "default_user")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{MEM0_BASE_URL}/memories",
            headers=_mem0_headers(),
            json={
                "messages": [{"role": "user", "content": text}],
                "user_id": user_id,
                "agent_id": project_id,
                "infer": True,
            },
            timeout=30,
        )
        if resp.status_code == 401:
            return "Error: Mem0 API authentication failed. Set MEM0_API_KEY or configure auth on the server."
        resp.raise_for_status()
        return f"Memory stored: {text}"


@moderator.tool
async def search_memories(
    ctx: RunContext[CodebaseContext],
    query: str,
) -> str:
    """Search for relevant memories using semantic search.

    Call this on the user's first query to discover any previously saved
    decisions or coding styles for this project.
    """
    project_id = ctx.deps.root_path.name
    user_id = os.getenv("MEM0_USER_ID", "default_user")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{MEM0_BASE_URL}/search",
            headers=_mem0_headers(),
            json={
                "query": query,
                "user_id": user_id,
                "agent_id": project_id,
            },
            timeout=30,
        )
        if resp.status_code == 401:
            return "Error: Mem0 API authentication failed. Set MEM0_API_KEY or configure auth on the server."
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return "No relevant memories found."
        lines = ["Relevant memories:"]
        for r in results:
            score = r.get("score", 0)
            memory = r.get("memory", "")
            lines.append(f"  - [{score:.2f}] {memory}")
        return "\n".join(lines)


@moderator.system_prompt
def memory_instructions(ctx: RunContext[CodebaseContext]) -> str:
    project_id = ctx.deps.root_path.name
    user_id = os.getenv("MEM0_USER_ID", "default_user")

    return (
        f"\n--- LONG-TERM PERSISTENT MEMORY (SELF-HOSTED MEM0) ---\n"
        f"You can store and retrieve project facts using `add_memory` and `search_memories`.\n"
        f"Memories are automatically scoped to directory '{project_id}' and user '{user_id}'.\n\n"
        f"OPERATIONAL STRATEGY:\n"
        f"1. On the user's first query, call `search_memories` to check for existing context.\n"
        f"2. When a definitive rule or choice is agreed upon, persist it via `add_memory`."
    )
