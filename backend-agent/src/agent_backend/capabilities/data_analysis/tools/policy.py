from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pydantic import Field

from agent_backend.capabilities.agent_runtime.execution_control.policies import (
    ToolAccessPolicy,
)
from agent_backend.capabilities.agent_runtime.guardrails.sql import validate_sql
from agent_backend.capabilities.agent_runtime.tool_calling.contracts import (
    BusinessTool,
    ToolExecutionContext,
)
from agent_backend.capabilities.agent_runtime.tool_calling.errors import (
    ToolCallError,
)
from agent_backend.capabilities.data_analysis.tools.contracts import (
    DataAnalysisToolExecutionContext,
)

GuardrailsHook = Callable[[BusinessTool, dict[str, Any], ToolExecutionContext], bool]


class DataAnalysisToolAccessPolicy(ToolAccessPolicy):
    supported_dataset_types: list[str] = Field(default_factory=list)
    requires_readonly_sql: bool = False


class DataAnalysisToolPolicyChecker:
    """Apply the data-analysis access rules injected at runtime assembly."""

    def __init__(
        self,
        policies: Mapping[tuple[str, str], DataAnalysisToolAccessPolicy],
        *,
        guardrails_hook: GuardrailsHook | None = None,
    ) -> None:
        self._policies = policies
        self._guardrails_hook = guardrails_hook

    def get_policy(
        self, tool_name: str, tool_version: str | None = None
    ) -> DataAnalysisToolAccessPolicy:
        versions = [version for name, version in self._policies if name == tool_name]
        version = (
            tool_version if tool_version is not None else max(versions, default="")
        )
        policy = self._policies.get((tool_name, version))
        if policy is None:
            raise ToolCallError(
                "Tool access policy missing",
                "Tool access policy is not configured.",
                detail={"tool_name": tool_name, "tool_version": version},
            )
        return policy

    def check(
        self, tool: BusinessTool, args: dict[str, Any], context: ToolExecutionContext
    ) -> None:
        policy = self.get_policy(tool.name, context.tool_version)
        if not isinstance(context, DataAnalysisToolExecutionContext):
            if policy.supported_dataset_types or policy.requires_readonly_sql:
                raise ToolCallError(
                    "Dataset context missing",
                    "Tool requires a data-analysis execution context.",
                )
            return
        dataset_id = context.dataset_scope.dataset_id_for_args(args)
        if not dataset_id and policy.supported_dataset_types:
            raise ToolCallError(
                "Dataset not allowed", "Tool call does not include a dataset id."
            )
        if dataset_id and dataset_id not in context.dataset_scope.allowed_dataset_ids:
            raise ToolCallError(
                "Dataset not allowed",
                f"Dataset is not allowed: {dataset_id}",
                detail={"dataset_id": dataset_id},
            )
        dataset_type = context.dataset_scope.dataset_type_for_id(dataset_id)
        if (
            policy.supported_dataset_types
            and dataset_type not in policy.supported_dataset_types
        ):
            raise ToolCallError(
                "Dataset type unsupported",
                f"Dataset type is not supported: {dataset_type}",
                detail={
                    "dataset_id": dataset_id,
                    "dataset_type": dataset_type,
                    "supported_dataset_types": policy.supported_dataset_types,
                },
            )
        if policy.requires_readonly_sql:
            allowed = (
                self._guardrails_hook(tool, args, context)
                if self._guardrails_hook is not None
                else validate_sql(str(args.get("sql", "")))
            )
            if not allowed:
                raise ToolCallError(
                    "SQL guardrail rejected",
                    "Tool call was rejected by guardrails.",
                    detail={"tool_name": tool.name},
                )
