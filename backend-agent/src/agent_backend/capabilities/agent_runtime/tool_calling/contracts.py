from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ToolStatus(str, Enum):
    SUCCEEDED = "succeeded"
    VALIDATION_FAILED = "validation_failed"
    PERMISSION_DENIED = "permission_denied"
    GUARDRAIL_REJECTED = "guardrail_rejected"
    TIMEOUT = "timeout"
    FAILED = "failed"


class ToolErrorCode(str, Enum):
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    TOOL_VERSION_NOT_FOUND = "TOOL_VERSION_NOT_FOUND"
    TOOL_ARGUMENT_INVALID = "TOOL_ARGUMENT_INVALID"
    TOOL_RESULT_INVALID = "TOOL_RESULT_INVALID"
    TOOL_PERMISSION_DENIED = "TOOL_PERMISSION_DENIED"
    TOOL_AGENT_NOT_ALLOWED = "TOOL_AGENT_NOT_ALLOWED"
    TOOL_NODE_NOT_ALLOWED = "TOOL_NODE_NOT_ALLOWED"
    TOOL_DATASET_NOT_ALLOWED = "TOOL_DATASET_NOT_ALLOWED"
    TOOL_DATASET_TYPE_UNSUPPORTED = "TOOL_DATASET_TYPE_UNSUPPORTED"
    TOOL_REVIEW_REQUIRED = "TOOL_REVIEW_REQUIRED"
    GUARDRAIL_REJECTED = "GUARDRAIL_REJECTED"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"


ERROR_STATUS_MAP: dict[ToolErrorCode, ToolStatus] = {
    ToolErrorCode.TOOL_NOT_FOUND: ToolStatus.VALIDATION_FAILED,
    ToolErrorCode.TOOL_VERSION_NOT_FOUND: ToolStatus.VALIDATION_FAILED,
    ToolErrorCode.TOOL_ARGUMENT_INVALID: ToolStatus.VALIDATION_FAILED,
    ToolErrorCode.TOOL_RESULT_INVALID: ToolStatus.VALIDATION_FAILED,
    ToolErrorCode.TOOL_PERMISSION_DENIED: ToolStatus.PERMISSION_DENIED,
    ToolErrorCode.TOOL_AGENT_NOT_ALLOWED: ToolStatus.PERMISSION_DENIED,
    ToolErrorCode.TOOL_NODE_NOT_ALLOWED: ToolStatus.PERMISSION_DENIED,
    ToolErrorCode.TOOL_DATASET_NOT_ALLOWED: ToolStatus.PERMISSION_DENIED,
    ToolErrorCode.TOOL_DATASET_TYPE_UNSUPPORTED: ToolStatus.PERMISSION_DENIED,
    ToolErrorCode.TOOL_REVIEW_REQUIRED: ToolStatus.PERMISSION_DENIED,
    ToolErrorCode.GUARDRAIL_REJECTED: ToolStatus.GUARDRAIL_REJECTED,
    ToolErrorCode.TOOL_TIMEOUT: ToolStatus.TIMEOUT,
    ToolErrorCode.TOOL_EXECUTION_FAILED: ToolStatus.FAILED,
}


class RetryPolicy(BaseModel):
    max_attempts: int = Field(default=0, ge=0)
    retryable_error_codes: list[str] = Field(default_factory=list)


class ToolLogPolicy(BaseModel):
    record_sql: bool = True
    record_sql_redacted: bool = True
    record_args: bool = False
    record_args_hash: bool = True
    record_result_sample: bool = True
    result_sample_limit: int = Field(default=20, ge=0)
    record_full_result: bool = False
    record_output_summary: bool = True
    record_file_path: bool = False
    record_connection_info: bool = False


class ToolDefinition(BaseModel):
    name: str
    version: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    allowed_agents: list[str] = Field(default_factory=list)
    allowed_nodes: list[str] = Field(default_factory=list)
    supported_dataset_types: list[str] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)
    timeout_ms: int = Field(default=10000, gt=0)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    log_policy: ToolLogPolicy = Field(default_factory=ToolLogPolicy)
    requires_review: bool = False
    tags: list[str] = Field(default_factory=list)
    risk_level: str | None = None


class DatasetScope(BaseModel):
    selected_dataset_id: str | None = None
    allowed_dataset_ids: list[str] = Field(default_factory=list)
    dataset_types: dict[str, str] = Field(default_factory=dict)
    permissions: list[str] = Field(default_factory=list)
    normalized_relation_datasets: dict[str, str] = Field(default_factory=dict)

    def dataset_id_for_args(self, args: dict[str, Any]) -> str | None:
        dataset_id = args.get("dataset_id")
        if isinstance(dataset_id, str):
            return dataset_id
        normalized_relation_id = args.get("normalized_relation_id")
        if isinstance(normalized_relation_id, str):
            return self.normalized_relation_datasets.get(normalized_relation_id)
        return self.selected_dataset_id

    def dataset_type_for_id(self, dataset_id: str | None) -> str | None:
        if dataset_id is None:
            return None
        return self.dataset_types.get(dataset_id)


class ToolCallRequest(BaseModel):
    tool_call_id: str
    tool_name: str
    tool_version: str
    agent_name: str
    agent_version: str
    node_id: str | None = None
    task_id: str
    trace_id: str
    session_id: str
    tenant_id: str
    user_id: str
    dataset_scope: DatasetScope
    args: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = Field(gt=0)


class ToolCallError(BaseModel):
    code: ToolErrorCode
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False


class ToolCallMetadata(BaseModel):
    latency_ms: int | None = None
    attempt: int = 1
    max_attempts: int = 1
    dataset_id: str | None = None
    dataset_type: str | None = None
    row_count: int | None = None
    truncated: bool | None = None
    input_hash: str | None = None
    output_summary: dict[str, Any] | None = None


class ToolCallResult(BaseModel):
    tool_call_id: str
    tool_name: str
    tool_version: str
    success: bool
    status: ToolStatus
    data: Any = None
    error: ToolCallError | None = None
    metadata: ToolCallMetadata = Field(default_factory=ToolCallMetadata)

    @model_validator(mode="after")
    def validate_success_error_shape(self) -> "ToolCallResult":
        if self.success:
            if self.data is None:
                raise ValueError("successful tool call result must include data")
            if self.error is not None:
                raise ValueError("successful tool call result must not include error")
        else:
            if self.data is not None:
                raise ValueError("failed tool call result must not include data")
            if self.error is None:
                raise ValueError("failed tool call result must include error")
        return self

    @classmethod
    def succeeded(
        cls,
        request: ToolCallRequest,
        data: Any,
        metadata: ToolCallMetadata | None = None,
    ) -> "ToolCallResult":
        return cls(
            tool_call_id=request.tool_call_id,
            tool_name=request.tool_name,
            tool_version=request.tool_version,
            success=True,
            status=ToolStatus.SUCCEEDED,
            data=data,
            error=None,
            metadata=metadata or ToolCallMetadata(),
        )

    @classmethod
    def failed(
        cls,
        request: ToolCallRequest,
        error: ToolCallError,
        metadata: ToolCallMetadata | None = None,
    ) -> "ToolCallResult":
        return cls(
            tool_call_id=request.tool_call_id,
            tool_name=request.tool_name,
            tool_version=request.tool_version,
            success=False,
            status=ERROR_STATUS_MAP[error.code],
            data=None,
            error=error,
            metadata=metadata or ToolCallMetadata(),
        )
