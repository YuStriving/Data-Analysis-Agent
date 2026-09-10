from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any, Callable

from agent_backend.capabilities.agent_runtime.guardrails.sql import validate_sql
from agent_backend.capabilities.agent_runtime.tool_calling.contracts import (
    ToolCallRequest,
    ToolCallResult,
    ToolDefinition,
    ToolErrorCode,
)
from agent_backend.capabilities.agent_runtime.tool_calling.errors import ToolCallingException
from agent_backend.capabilities.agent_runtime.tool_calling.logging import ToolCallLogger, metadata_for_result
from agent_backend.capabilities.agent_runtime.tool_calling.protocols import Tool
from agent_backend.capabilities.agent_runtime.tool_calling.registry import ToolRegistry
from agent_backend.capabilities.agent_runtime.tool_calling.validation import validate_value


GuardrailsHook = Callable[[ToolDefinition, ToolCallRequest], bool]


class ToolCallingRuntime:
    def __init__(
        self,
        registry: ToolRegistry | None = None,
        *,
        logger: ToolCallLogger | None = None,
        guardrails_hook: GuardrailsHook | None = None,
    ) -> None:
        self.registry = registry or ToolRegistry()
        self.logger = logger or ToolCallLogger()
        self.guardrails_hook = guardrails_hook or self._default_guardrails_hook

    def list_tools(self, agent_name: str | None = None) -> list[ToolDefinition]:
        definitions = self.registry.list()
        if agent_name is None:
            return definitions
        return [definition for definition in definitions if agent_name in definition.allowed_agents]

    def get_tool(self, tool_name: str, tool_version: str | None = None) -> ToolDefinition:
        return self.registry.get(tool_name, tool_version).definition()

    async def call(self, request: ToolCallRequest) -> ToolCallResult:
        started = time.perf_counter()
        definition: ToolDefinition | None = None
        self.logger.record_started(request)
        try:
            tool = self.registry.get(request.tool_name, request.tool_version)
            definition = tool.definition()
            self._check_permission(definition, request)
            validate_value(definition.input_schema, request.args, ToolErrorCode.TOOL_ARGUMENT_INVALID)
            self._check_guardrails(definition, request)
            data = await asyncio.wait_for(
                self._execute_tool(tool, request.args),
                timeout=request.timeout_ms / 1000,
            )
            validate_value(definition.output_schema, data, ToolErrorCode.TOOL_RESULT_INVALID)
            result = ToolCallResult.succeeded(
                request,
                data=data,
                metadata=metadata_for_result(
                    request,
                    definition,
                    latency_ms=self._elapsed_ms(started),
                    data=data,
                ),
            )
        except asyncio.TimeoutError:
            result = self._failure(
                request,
                ToolCallingException(ToolErrorCode.TOOL_TIMEOUT, "Tool execution timed out.", retryable=True),
                definition,
                started,
            )
        except ToolCallingException as exc:
            result = self._failure(request, exc, definition, started)
        except Exception as exc:
            result = self._failure(
                request,
                ToolCallingException(
                    ToolErrorCode.TOOL_EXECUTION_FAILED,
                    str(exc),
                    detail={"exception_type": type(exc).__name__},
                ),
                definition,
                started,
            )

        self.logger.record_finished(request, result)
        return result

    async def _execute_tool(self, tool: Tool, args: dict[str, Any]) -> Any:
        if inspect.iscoroutinefunction(tool.execute):
            return await tool.execute(args)
        return await asyncio.to_thread(tool.execute, args)

    def _check_permission(self, definition: ToolDefinition, request: ToolCallRequest) -> None:
        if definition.requires_review:
            raise ToolCallingException(
                ToolErrorCode.TOOL_REVIEW_REQUIRED,
                f"Tool requires review: {definition.name}",
            )
        if definition.allowed_agents and request.agent_name not in definition.allowed_agents:
            raise ToolCallingException(
                ToolErrorCode.TOOL_AGENT_NOT_ALLOWED,
                f"Agent is not allowed to call tool: {request.agent_name}",
                detail={"agent_name": request.agent_name, "tool_name": definition.name},
            )
        if request.node_id and definition.allowed_nodes and request.node_id not in definition.allowed_nodes:
            raise ToolCallingException(
                ToolErrorCode.TOOL_NODE_NOT_ALLOWED,
                f"Node is not allowed to call tool: {request.node_id}",
                detail={"node_id": request.node_id, "tool_name": definition.name},
            )
        missing_permissions = set(definition.required_permissions) - set(request.dataset_scope.permissions)
        if missing_permissions:
            raise ToolCallingException(
                ToolErrorCode.TOOL_PERMISSION_DENIED,
                "Tool required permissions are missing.",
                detail={"missing_permissions": sorted(missing_permissions)},
            )

        dataset_id = request.dataset_scope.dataset_id_for_args(request.args)
        if not dataset_id and definition.supported_dataset_types:
            raise ToolCallingException(
                ToolErrorCode.TOOL_DATASET_NOT_ALLOWED,
                "Tool call does not include a dataset id.",
            )
        if dataset_id and dataset_id not in request.dataset_scope.allowed_dataset_ids:
            raise ToolCallingException(
                ToolErrorCode.TOOL_DATASET_NOT_ALLOWED,
                f"Dataset is not allowed: {dataset_id}",
                detail={"dataset_id": dataset_id},
            )
        dataset_type = request.dataset_scope.dataset_type_for_id(dataset_id)
        if definition.supported_dataset_types and dataset_type not in definition.supported_dataset_types:
            raise ToolCallingException(
                ToolErrorCode.TOOL_DATASET_TYPE_UNSUPPORTED,
                f"Dataset type is not supported: {dataset_type}",
                detail={
                    "dataset_id": dataset_id,
                    "dataset_type": dataset_type,
                    "supported_dataset_types": definition.supported_dataset_types,
                },
            )

    def _check_guardrails(self, definition: ToolDefinition, request: ToolCallRequest) -> None:
        if "sql" not in request.args:
            return
        if "query_executor" not in definition.name:
            return
        if not self.guardrails_hook(definition, request):
            raise ToolCallingException(
                ToolErrorCode.GUARDRAIL_REJECTED,
                "Tool call was rejected by guardrails.",
                detail={"tool_name": definition.name},
                retryable=False,
            )

    def _default_guardrails_hook(self, definition: ToolDefinition, request: ToolCallRequest) -> bool:
        return validate_sql(str(request.args.get("sql", "")))

    def _failure(
        self,
        request: ToolCallRequest,
        exc: ToolCallingException,
        definition: ToolDefinition | None,
        started: float,
    ) -> ToolCallResult:
        return ToolCallResult.failed(
            request,
            error=exc.error,
            metadata=metadata_for_result(
                request,
                definition,
                latency_ms=self._elapsed_ms(started),
            ),
        )

    def _elapsed_ms(self, started: float) -> int:
        return int((time.perf_counter() - started) * 1000)
