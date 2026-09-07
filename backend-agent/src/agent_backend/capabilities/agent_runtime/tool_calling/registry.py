from dataclasses import dataclass


@dataclass(slots=True)
class ToolDefinition:
    name: str
    description: str
    requires_review: bool = False


DEFAULT_TOOLS = [
    ToolDefinition(name="schema_inspector", description="Inspect allowed schemas"),
    ToolDefinition(name="sql_guard", description="Validate read-only SQL"),
    ToolDefinition(name="query_runner", description="Run approved SQL"),
]

