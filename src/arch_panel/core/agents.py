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
MEM0_BASE_URL = os.getenv("MEM0_BASE_URL", "http://127.0.0.1:8888")
MEM0_API_KEY = os.getenv("MEM0_API_KEY", "none")

mem0_transport = StdioTransport(
    command="uvx",
    args=["mem0-mcp-server"],
    env={
        **os.environ,
        "MEM0_BASE_URL": MEM0_BASE_URL,
        "MEM0_API_KEY": MEM0_API_KEY,
    },
)
mem0_toolset = MCPToolset(mem0_transport)

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


@moderator.system_prompt
def memory_instructions(ctx: RunContext[CodebaseContext]) -> str:
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
