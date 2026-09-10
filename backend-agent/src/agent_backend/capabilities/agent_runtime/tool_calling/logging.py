from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_backend.capabilities.agent_runtime.tool_calling.contracts import (
    ToolCallMetadata,
    ToolCallRequest,
    ToolCallResult,
    ToolDefinition,
    ToolLogPolicy,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def summarize_input(args: dict[str, Any], policy: ToolLogPolicy) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in ("dataset_id", "normalized_relation_id", "relation_names", "chart_type", "max_rows", "max_points"):
        if key in args:
            summary[key] = args[key]
    if policy.record_sql and "sql" in args:
        summary["sql"] = args["sql"]
    if "file_ref" in args:
        summary["file_ref"] = args["file_ref"] if policy.record_file_path else Path(str(args["file_ref"])).name
    return summary


def summarize_output(data: Any, policy: ToolLogPolicy) -> dict[str, Any] | None:
    if not policy.record_output_summary or not isinstance(data, dict):
        return None

    summary: dict[str, Any] = {}
    for key in ("columns", "row_count", "truncated", "result_summary", "warnings"):
        if key in data:
            summary[key] = data[key]
    if policy.record_result_sample and isinstance(data.get("rows"), list):
        summary["sample_rows"] = data["rows"][: policy.result_sample_limit]
    if policy.record_full_result:
        summary["rows"] = data.get("rows")
    return summary


def metadata_for_result(
    request: ToolCallRequest,
    definition: ToolDefinition | None,
    *,
    latency_ms: int,
    data: Any = None,
) -> ToolCallMetadata:
    dataset_id = request.dataset_scope.dataset_id_for_args(request.args)
    dataset_type = request.dataset_scope.dataset_type_for_id(dataset_id)
    policy = definition.log_policy if definition else ToolLogPolicy()
    output_summary = summarize_output(data, policy) if data is not None else None
    row_count = data.get("row_count") if isinstance(data, dict) else None
    truncated = data.get("truncated") if isinstance(data, dict) else None
    return ToolCallMetadata(
        latency_ms=latency_ms,
        attempt=1,
        max_attempts=1,
        dataset_id=dataset_id,
        dataset_type=dataset_type,
        row_count=row_count if isinstance(row_count, int) else None,
        truncated=truncated if isinstance(truncated, bool) else None,
        input_hash=stable_hash(request.args),
        output_summary=output_summary,
    )


class ToolCallLogger:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def record_started(self, request: ToolCallRequest, definition: ToolDefinition | None = None) -> dict[str, Any]:
        dataset_id = request.dataset_scope.dataset_id_for_args(request.args)
        dataset_type = request.dataset_scope.dataset_type_for_id(dataset_id)
        policy = definition.log_policy if definition else ToolLogPolicy(record_sql=False)
        event = {
            "event_type": "tool_call_started",
            "tool_call_id": request.tool_call_id,
            "tool_name": request.tool_name,
            "tool_version": request.tool_version,
            "agent_name": request.agent_name,
            "agent_version": request.agent_version,
            "node_id": request.node_id,
            "task_id": request.task_id,
            "trace_id": request.trace_id,
            "session_id": request.session_id,
            "tenant_id": request.tenant_id,
            "user_id": request.user_id,
            "dataset_id": dataset_id,
            "dataset_type": dataset_type,
            "started_at": utc_now_iso(),
            "timeout_ms": request.timeout_ms,
            "args_hash": stable_hash(request.args),
            "input_summary": summarize_input(request.args, policy),
        }
        self.events.append(event)
        return event

    def record_finished(self, request: ToolCallRequest, result: ToolCallResult) -> dict[str, Any]:
        error = result.error
        event = {
            "event_type": "tool_call_finished",
            "tool_call_id": result.tool_call_id,
            "tool_name": result.tool_name,
            "tool_version": result.tool_version,
            "agent_name": request.agent_name,
            "agent_version": request.agent_version,
            "node_id": request.node_id,
            "task_id": request.task_id,
            "trace_id": request.trace_id,
            "session_id": request.session_id,
            "tenant_id": request.tenant_id,
            "user_id": request.user_id,
            "dataset_id": result.metadata.dataset_id,
            "dataset_type": result.metadata.dataset_type,
            "finished_at": utc_now_iso(),
            "latency_ms": result.metadata.latency_ms,
            "success": result.success,
            "status": result.status.value,
            "error_code": error.code.value if error else None,
            "error_message": error.message if error else None,
            "error_detail": error.detail if error else None,
            "retryable": error.retryable if error else False,
            "attempt": result.metadata.attempt,
            "max_attempts": result.metadata.max_attempts,
            "truncated": result.metadata.truncated,
            "row_count": result.metadata.row_count,
            "output_summary": result.metadata.output_summary,
        }
        self.events.append(event)
        return event
