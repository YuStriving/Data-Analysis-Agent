from __future__ import annotations

import hashlib
import json
from typing import Protocol

from agent_backend.agent_runtime.execution_control.contracts import (
    AgentSpec,
    TerminationDecision,
    ToolCallFingerprint,
)
from agent_backend.agent_runtime.execution_control.policies import (
    ToolAccessPolicy,
)
from agent_backend.agent_runtime.tool_calling.contracts import (
    ToolCallRequest,
)
from agent_backend.agent_runtime.tool_calling.errors import (
    ToolCallError,
)


class ToolAccessPolicyResolver(Protocol):
    def get_tool_policy(self, tool_name: str, tool_version: str | None = None) -> ToolAccessPolicy: ...


class ToolGuard:
    def __init__(
        self,
        agent_spec: AgentSpec,
        *,
        tool_resolver: ToolAccessPolicyResolver | None = None,
    ) -> None:
        self.agent_spec = agent_spec
        self.tool_resolver = tool_resolver

    def check_allowed_tool(
        self,
        node_id: str,
        tool_name: str,
        tool_version: str | None,
    ) -> TerminationDecision:
        node_spec = self.agent_spec.node_specs.get(node_id)
        if node_spec is None:
            return TerminationDecision.stop(
                "failed",
                failure_code="unknown_node",
                failure_message=f"Node is not declared in AgentSpec: {node_id}",
            )
        if tool_name not in node_spec.allowed_tools:
            return TerminationDecision.stop(
                "guardrail_rejected",
                failure_code="tool_not_allowed_for_node",
                failure_message=f"Tool is not allowed for node: {node_id}:{tool_name}",
            )

        if self.tool_resolver is None:
            return TerminationDecision.continue_to()

        try:
            policy = self.tool_resolver.get_tool_policy(tool_name, tool_version)
        except ToolCallError as exc:
            return TerminationDecision.stop(
                "guardrail_rejected",
                failure_code="tool_call_failed",
                failure_message=f"{exc.reason}: {exc.message}",
            )

        return self.check_tool_policy(policy, tool_name)

    def check_tool_policy(self, policy: ToolAccessPolicy, tool_name: str) -> TerminationDecision:
        if policy.requires_review:
            return TerminationDecision.stop(
                "guardrail_rejected",
                failure_code="tool_review_required",
                failure_message=f"Tool requires review: {tool_name}",
            )
        if policy.risk_level and policy.risk_level not in self.agent_spec.tool_policy.allowed_risk_levels:
            return TerminationDecision.stop(
                "guardrail_rejected",
                failure_code="tool_risk_level_not_allowed",
                failure_message=f"Tool risk level is not allowed: {policy.risk_level}",
            )
        return TerminationDecision.continue_to()

    def build_fingerprint(self, request: ToolCallRequest) -> ToolCallFingerprint:
        normalized_args = json.dumps(
            request.args,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return ToolCallFingerprint(
            node_id=request.context.node_id,
            tool_name=request.tool_name,
            tool_version=request.tool_version,
            normalized_args_hash=hashlib.sha256(normalized_args.encode("utf-8")).hexdigest(),
        )
