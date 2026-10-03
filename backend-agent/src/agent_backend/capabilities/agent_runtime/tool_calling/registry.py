from __future__ import annotations

from agent_backend.capabilities.agent_runtime.tool_calling.contracts import (
    BusinessTool,
    ToolExecutionOptions,
)
from agent_backend.capabilities.agent_runtime.tool_calling.errors import (
    ToolCallError,
)


class ToolRegistry:
    def __init__(self, tools: list[BusinessTool] | None = None) -> None:
        self._tools: dict[tuple[str, str], BusinessTool] = {}
        self._options: dict[tuple[str, str], ToolExecutionOptions] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: BusinessTool, *, options: ToolExecutionOptions | None = None) -> None:
        options = options or ToolExecutionOptions()
        key = (tool.name, options.version)
        self._tools[key] = tool
        self._options[key] = options

    def get(self, name: str, version: str | None = None) -> BusinessTool:
        return self._tools[self._resolve_key(name, version)]

    def get_options(self, name: str, version: str | None = None) -> ToolExecutionOptions:
        return self._options[self._resolve_key(name, version)]

    def list(self) -> list[BusinessTool]:
        return list(self._tools.values())

    def _resolve_key(self, name: str, version: str | None) -> tuple[str, str]:
        if version is not None and (name, version) in self._tools:
            return name, version
        known_versions = [candidate_version for tool_name, candidate_version in self._tools if tool_name == name]
        if not known_versions:
            raise ToolCallError(
                "Tool not found",
                f"Tool not found: {name}",
                detail={"tool_name": name},
            )
        if version is not None:
            raise ToolCallError(
                "Tool version not found",
                f"Tool version not found: {name}@{version}",
                detail={"tool_name": name, "tool_version": version, "known_versions": known_versions},
            )
        return name, max(known_versions)
