import os

from pydantic_ai import Agent, RunContext

from .capabilities import codebase_inspector
from .context import CodebaseContext
from typing import Literal

LLM_MODEL = os.getenv("OPENAI_MODEL_NAME", "openai:gpt-4o")

EXPERT_STACK = [
    ("db_expert", "Database & State"),
    ("api_expert", "API & Protocols"),
    ("clean_code_expert", "Modularity & Clean Code"),
]

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
