from __future__ import annotations

from typing import Any, Protocol

from agent_backend.capabilities.agent_runtime.tool_calling.contracts import ToolDefinition


class Tool(Protocol):
    def definition(self) -> ToolDefinition:
        ...

    def execute(self, args: dict[str, Any]) -> Any:
        ...
