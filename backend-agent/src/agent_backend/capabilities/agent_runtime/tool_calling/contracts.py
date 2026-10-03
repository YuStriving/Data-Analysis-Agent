from __future__ import annotations

from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field, SerializeAsAny, field_validator

InputArgsDefinition = dict[str, Any]


class ToolExecutionOptions(BaseModel):
    """Execution settings supplied by assembly code, outside the business tool."""

    model_config = {"extra": "forbid"}

    version: str = "v1"
    output_schema: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = Field(default=10000, gt=0)


class BusinessTool(Protocol):
    """Minimal business tool: descriptive attributes and an execution method."""

    name: str
    description: str
    input_args: InputArgsDefinition

    def execute(self, args: dict[str, Any], context: ToolExecutionContext) -> Any: ...


class ToolExecutionContext(BaseModel):
    """Call identity and execution scope, separate from tool metadata and input."""

    model_config = {"extra": "forbid"}

    tool_call_id: str = Field(default_factory=lambda: f"tc-{uuid4().hex[:12]}")
    tool_version: str = "v1"
    agent_name: str
    agent_version: str
    node_id: str | None = None
    task_id: str
    trace_id: str
    session_id: str
    tenant_id: str
    user_id: str
    goal: str
    purpose: str
    permissions: list[str] = Field(default_factory=list)
    timeout_ms: int | None = Field(default=None, gt=0)

    @field_validator("goal", "purpose")
    @classmethod
    def require_nonblank_goal(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("tool goal and purpose must not be blank")
        return value


class ToolCallRequest(BaseModel):
    model_config = {"extra": "forbid"}

    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    context: SerializeAsAny[ToolExecutionContext]

    @property
    def tool_version(self) -> str:
        return self.context.tool_version


class ToolCallResult(BaseModel):
    """A successful tool result. Failures are raised as ToolCallError."""

    tool_call_id: str
    tool_name: str
    tool_version: str
    data: Any

    @field_validator("data")
    @classmethod
    def require_data(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("successful tool call result must include data")
        return value
