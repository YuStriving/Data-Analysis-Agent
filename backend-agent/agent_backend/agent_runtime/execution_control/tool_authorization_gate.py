from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agent_backend.agent_runtime.execution_control.contracts import (
    AgentSpec,
)
from agent_backend.agent_runtime.execution_control.policies import (
    ToolAccessPolicy,
    ToolAccessPolicyResolver,
)
from agent_backend.agent_runtime.tool_calling.contracts import (
    BusinessTool,
    ToolExecutionContext,
)
from agent_backend.agent_runtime.tool_calling.errors import ToolCallError
from agent_backend.agent_runtime.tool_calling.executor import (
    AuthorizationCheck,
    run_authorization_check,
)

AgentSpecResolver = Callable[[str, str], AgentSpec | None]


class ToolAuthorizationGate:
    """Enforce declared capabilities and injected authorization before execution."""

    def __init__(
        self,
        *,
        agent_spec_resolver: AgentSpecResolver,
        policy_resolver: ToolAccessPolicyResolver,
        business_check: AuthorizationCheck | None = None,
    ) -> None:
        self._agent_spec_resolver = agent_spec_resolver
        self._policy_resolver = policy_resolver
        self._business_check = business_check

    def get_policy(
        self, tool_name: str, tool_version: str | None = None
    ) -> ToolAccessPolicy:
        policy = self._policy_resolver(tool_name, tool_version)
        if policy is None:
            raise ToolCallError(
                "Tool access policy missing", "Tool access policy is not configured."
            )
        return policy

    def check(
        self, tool: BusinessTool, args: dict[str, Any], context: ToolExecutionContext
    ) -> None:
        policy = self.get_policy(tool.name, context.tool_version)
        spec = self._agent_spec_resolver(context.agent_name, context.agent_version)
        if spec is None or spec.agent_id != context.agent_name:
            raise ToolCallError(
                "Agent not allowed", "Agent capability is not configured."
            )
        if policy.allowed_agents and context.agent_name not in policy.allowed_agents:
            raise ToolCallError(
                "Agent not allowed", "Agent is not allowed to call tool."
            )
        node = spec.node_specs.get(context.node_id) if context.node_id else None
        if node is None or tool.name not in node.allowed_tools:
            raise ToolCallError(
                "Node not allowed", "Tool is not declared for this node."
            )
        if policy.allowed_nodes and context.node_id not in policy.allowed_nodes:
            raise ToolCallError("Node not allowed", "Node is not allowed to call tool.")
        missing = set(policy.required_permissions) - set(context.permissions)
        if missing:
            raise ToolCallError(
                "Missing permissions",
                "Tool required permissions are missing.",
                detail={"missing_permissions": sorted(missing)},
            )
        if policy.requires_review:
            raise ToolCallError("Tool review required", "Tool requires review.")
        if (
            policy.risk_level
            and policy.risk_level not in spec.tool_policy.allowed_risk_levels
        ):
            raise ToolCallError(
                "Tool risk level not allowed", "Tool risk level is not allowed."
            )
        if self._business_check is not None:
            run_authorization_check(self._business_check, tool, args, context)
