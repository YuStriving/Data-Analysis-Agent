from __future__ import annotations

from agent_backend.agent_runtime.execution_control.policies import (
    ToolAccessPolicy,
    ToolAccessPolicyResolver,
)
from agent_backend.agent_runtime.tool_calling.contracts import (
    BusinessTool,
    ToolCallRequest,
    ToolCallResult,
)
from agent_backend.agent_runtime.tool_calling.executor import (
    AuthorizationCheck,
    ToolExecutor,
)
from agent_backend.agent_runtime.tool_calling.registry import ToolRegistry


class ToolCallingRuntime:
    def __init__(
        self,
        registry: ToolRegistry | None = None,
        *,
        authorize: AuthorizationCheck,
        access_policy_resolver: ToolAccessPolicyResolver,
    ) -> None:
        self.registry = registry or ToolRegistry()
        if not callable(authorize) or not callable(access_policy_resolver):
            raise TypeError(
                "ToolCallingRuntime requires authorization and policy resolvers"
            )
        self.authorize = authorize
        self.access_policy_resolver = access_policy_resolver

    def list_tools(self, agent_name: str | None = None) -> list[BusinessTool]:
        tools = self.registry.list()
        if agent_name is None:
            return tools
        return [
            tool
            for tool in tools
            if not (policy := self.get_tool_policy(tool.name)).allowed_agents
            or agent_name in policy.allowed_agents
        ]

    def get_tool(self, tool_name: str, tool_version: str | None = None) -> BusinessTool:
        return self.registry.get(tool_name, tool_version)

    def get_tool_policy(
        self, tool_name: str, tool_version: str | None = None
    ) -> ToolAccessPolicy:
        self.registry.get(tool_name, tool_version)
        version = self.registry.get_options(tool_name, tool_version).version
        return self.access_policy_resolver(tool_name, version)

    async def call(self, request: ToolCallRequest) -> ToolCallResult:
        tool = self.registry.get(request.tool_name, request.tool_version)
        options = self.registry.get_options(request.tool_name, request.tool_version)
        executor = ToolExecutor(options=options, authorize=self.authorize)
        return await executor.execute(tool, request.args, request.context)
