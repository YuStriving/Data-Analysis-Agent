from __future__ import annotations

from agent_backend.capabilities.agent_runtime.tool_calling.contracts import ToolDefinition, ToolErrorCode
from agent_backend.capabilities.agent_runtime.tool_calling.errors import ToolCallingException
from agent_backend.capabilities.agent_runtime.tool_calling.protocols import Tool


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[tuple[str, str], Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        definition = tool.definition()
        self._tools[(definition.name, definition.version)] = tool

    def get(self, name: str, version: str | None = None) -> Tool:
        if version is not None:
            tool = self._tools.get((name, version))
            if tool is not None:
                return tool
            known_versions = [candidate_version for tool_name, candidate_version in self._tools if tool_name == name]
            if known_versions:
                raise ToolCallingException(
                    ToolErrorCode.TOOL_VERSION_NOT_FOUND,
                    f"Tool version not found: {name}@{version}",
                    detail={"tool_name": name, "tool_version": version, "known_versions": known_versions},
                )
            raise ToolCallingException(
                ToolErrorCode.TOOL_NOT_FOUND,
                f"Tool not found: {name}",
                detail={"tool_name": name},
            )

        versions = [(tool_version, tool) for (tool_name, tool_version), tool in self._tools.items() if tool_name == name]
        if not versions:
            raise ToolCallingException(
                ToolErrorCode.TOOL_NOT_FOUND,
                f"Tool not found: {name}",
                detail={"tool_name": name},
            )
        return sorted(versions, key=lambda item: item[0])[-1][1]

    def list(self) -> list[ToolDefinition]:
        return [tool.definition() for tool in self._tools.values()]
