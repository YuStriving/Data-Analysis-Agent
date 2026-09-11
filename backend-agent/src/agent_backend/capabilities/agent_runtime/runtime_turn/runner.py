from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from agent_backend.capabilities.agent_runtime.context.builder import ContextBuilder
from agent_backend.capabilities.agent_runtime.context.contracts import (
    ContextIdentity,
    ContextSource,
    DatasetContext,
    RequestContext,
)
from agent_backend.capabilities.agent_runtime.context.policies import resolve_context_policy
from agent_backend.capabilities.agent_runtime.memory.contracts import (
    AnswerGeneratedPayload,
    MemoryEvent,
    QuestionReceivedPayload,
    SqlGeneratedPayload,
    TaskFailedPayload,
)
from agent_backend.capabilities.agent_runtime.memory.service import MemoryService
from agent_backend.capabilities.agent_runtime.prompt import (
    MissingPromptInputSectionsError,
    PromptBudgetGuard,
    PromptHubError,
    PromptInputAdapter,
    render_prompt,
)
from agent_backend.capabilities.agent_runtime.runtime_turn.contracts import (
    RuntimeEventSink,
    RuntimeModelClient,
    RuntimeSchemaProvider,
    RuntimeTurnEvent,
    RuntimeTurnEventType,
    RuntimeTurnResult,
    RuntimeTurnStatus,
)
from agent_backend.foundation.contracts.task import AnalysisTaskRequest


@dataclass
class RuntimeTurnDependencies:
    event_sink: RuntimeEventSink
    memory_service: MemoryService
    model_client: RuntimeModelClient
    schema_provider: RuntimeSchemaProvider
    context_builder: ContextBuilder | None = None
    prompt_input_adapter: PromptInputAdapter | None = None
    prompt_budget_guard: PromptBudgetGuard | None = None


class RuntimeTurnRunner:
    agent_id = "data_analysis_agent"
    node_id = "generate_sql"

    def __init__(self, dependencies: RuntimeTurnDependencies) -> None:
        self.dependencies = dependencies
        self.context_builder = dependencies.context_builder or ContextBuilder()
        self.prompt_input_adapter = dependencies.prompt_input_adapter or PromptInputAdapter()
        self.prompt_budget_guard = dependencies.prompt_budget_guard or PromptBudgetGuard()
        self._event_seq = 0

    def run(self, request: AnalysisTaskRequest) -> RuntimeTurnResult:
        self._event_seq = 0
        memory_event_ids: list[str] = []
        prompt_version: str | None = None
        rendered_prompt_hash: str | None = None
        warnings: list[str] = []

        try:
            self._publish(request, "task_started", "Task execution started.")
            memory_event_ids.append(self._record_question_received(request))
            self._publish(
                request,
                "memory_recorded",
                "Question received event recorded.",
                {"memory_event_type": "question_received"},
            )

            self._publish(request, "context_building", "Building prompt context.")
            source = self._build_context_source(request)
            policy = resolve_context_policy(self.agent_id, self.node_id)
            context_result = self.context_builder.build(source, policy)
            if context_result.status == "missing_required_context":
                message = "Required context is missing."
                self._publish(
                    request,
                    "context_missing_required",
                    message,
                    {"missing_sections": context_result.missing_sections},
                )
                self._record_task_failed(
                    request,
                    failure_stage="build_context",
                    error_message=message,
                    event_seq=self._event_seq + 1,
                    memory_event_ids=memory_event_ids,
                )
                self._publish(request, "task_failed", message)
                return self._result(
                    request,
                    status="missing_required_context",
                    failure_code="missing_required_context",
                    failure_message=message,
                    memory_event_ids=memory_event_ids,
                    prompt_version=prompt_version,
                    rendered_prompt_hash=rendered_prompt_hash,
                    warnings=warnings,
                )

            assert context_result.bundle is not None
            included_sections = (
                context_result.bundle.meta.included_sections
                if context_result.bundle.meta is not None
                else []
            )
            self._publish(
                request,
                "context_built",
                "Prompt context built.",
                {"included_sections": included_sections},
            )

            self._publish(request, "prompt_rendering", "Rendering prompt.")
            prompt_request = self.prompt_input_adapter.build_prompt_request(
                agent_id=self.agent_id,
                node_id=self.node_id,
                bundle=context_result.bundle,
            )
            prompt_result = render_prompt(prompt_request)
            prompt_version = prompt_result.template_version
            rendered_prompt_hash = prompt_result.rendered_hash
            budget_result = self.prompt_budget_guard.check_rendered_prompt(
                prompt_result.rendered_text
            )
            warnings.extend(budget_result.warnings)
            if budget_result.status == "exceeded":
                message = "Rendered prompt exceeded budget."
                self._publish(
                    request,
                    "context_budget_exceeded",
                    message,
                    budget_result.model_dump(mode="json"),
                )
                self._record_task_failed(
                    request,
                    failure_stage="prompt_budget",
                    error_message=message,
                    event_seq=self._event_seq + 1,
                    memory_event_ids=memory_event_ids,
                )
                self._publish(request, "task_failed", message)
                return self._result(
                    request,
                    status="context_budget_exceeded",
                    failure_code="context_budget_exceeded",
                    failure_message=message,
                    memory_event_ids=memory_event_ids,
                    prompt_version=prompt_version,
                    rendered_prompt_hash=rendered_prompt_hash,
                    warnings=warnings,
                )

            self._publish(
                request,
                "prompt_rendered",
                "Prompt rendered.",
                {
                    "prompt_version": prompt_version,
                    "rendered_prompt_hash": rendered_prompt_hash,
                    "budget_status": budget_result.status,
                },
            )

            self._publish(request, "model_call_started", "Calling model.")
            raw_output = self.dependencies.model_client.complete(prompt_result.rendered_text)
            self._publish(request, "model_call_finished", "Model call finished.")
            model_output = self._parse_model_output(raw_output)
            if model_output is None:
                message = "Model output is not valid JSON."
                self._publish(request, "model_output_invalid", message)
                self._record_task_failed(
                    request,
                    failure_stage="parse_model_output",
                    error_message=message,
                    event_seq=self._event_seq + 1,
                    memory_event_ids=memory_event_ids,
                )
                self._publish(request, "task_failed", message)
                return self._result(
                    request,
                    status="model_output_invalid",
                    failure_code="model_output_invalid",
                    failure_message=message,
                    memory_event_ids=memory_event_ids,
                    prompt_version=prompt_version,
                    rendered_prompt_hash=rendered_prompt_hash,
                    warnings=warnings,
                )

            memory_event_ids.append(
                self._record_generate_sql_result(
                    request,
                    model_output=model_output,
                    prompt_version=prompt_version,
                )
            )
            self._publish(
                request,
                "memory_recorded",
                "Model result event recorded.",
                {"memory_event_ids": memory_event_ids},
            )

            final_answer = self._final_answer(model_output)
            self._publish(request, "task_completed", "Task execution completed.")
            return self._result(
                request,
                status="completed",
                final_answer=final_answer,
                memory_event_ids=memory_event_ids,
                prompt_version=prompt_version,
                rendered_prompt_hash=rendered_prompt_hash,
                warnings=warnings,
            )
        except (MissingPromptInputSectionsError, PromptHubError) as exc:
            message = str(exc)
            self._publish(
                request,
                "prompt_render_failed",
                message,
                {"error_type": exc.__class__.__name__},
            )
            self._record_task_failed(
                request,
                failure_stage="render_prompt",
                error_message=message,
                event_seq=self._event_seq + 1,
                memory_event_ids=memory_event_ids,
            )
            self._publish(request, "task_failed", message)
            return self._result(
                request,
                status="prompt_render_failed",
                failure_code="prompt_render_failed",
                failure_message=message,
                memory_event_ids=memory_event_ids,
                prompt_version=prompt_version,
                rendered_prompt_hash=rendered_prompt_hash,
                warnings=warnings,
            )
        except Exception as exc:
            message = str(exc)
            self._record_task_failed(
                request,
                failure_stage="runtime_turn",
                error_message=message,
                event_seq=self._event_seq + 1,
                memory_event_ids=memory_event_ids,
            )
            self._publish(request, "task_failed", message)
            return self._result(
                request,
                status="failed",
                failure_code="runtime_turn_failed",
                failure_message=message,
                memory_event_ids=memory_event_ids,
                prompt_version=prompt_version,
                rendered_prompt_hash=rendered_prompt_hash,
                warnings=warnings,
            )

    def _build_context_source(self, request: AnalysisTaskRequest) -> ContextSource:
        selected_dataset_id = self._select_dataset_id(request)
        schema_context = (
            self.dependencies.schema_provider.load_schema(selected_dataset_id)
            if selected_dataset_id is not None
            else None
        )
        return ContextSource(
            identity=ContextIdentity(
                task_id=request.task_id,
                trace_id=request.trace_id,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                session_id=request.session_id,
            ),
            request=RequestContext(question=request.question),
            access=request.access_context,
            dataset=DatasetContext(
                available_dataset_ids=list(request.access_context.allowed_dataset_ids),
                selected_dataset_id=selected_dataset_id,
            ),
            schema=schema_context,
        )

    def _select_dataset_id(self, request: AnalysisTaskRequest) -> str | None:
        allowed_dataset_ids = set(request.access_context.allowed_dataset_ids)
        for dataset_id in request.dataset_ids:
            if dataset_id in allowed_dataset_ids:
                return dataset_id
        return None

    def _publish(
        self,
        request: AnalysisTaskRequest,
        event_type: RuntimeTurnEventType,
        message: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        self._event_seq += 1
        self.dependencies.event_sink.publish(
            RuntimeTurnEvent(
                task_id=request.task_id,
                trace_id=request.trace_id,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                session_id=request.session_id,
                event_type=event_type,
                event_seq=self._event_seq,
                message=message,
                payload=payload or {},
            )
        )

    def _record_question_received(self, request: AnalysisTaskRequest) -> str:
        event = MemoryEvent(
            event_id=f"{request.task_id}:memory:question_received",
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            session_id=request.session_id,
            task_id=request.task_id,
            trace_id=request.trace_id,
            event_type="question_received",
            event_seq=1,
            payload=QuestionReceivedPayload(
                question=request.question,
                dataset_ids=list(request.dataset_ids),
                selected_dataset_id=self._select_dataset_id(request),
            ),
            created_at=datetime.now(timezone.utc),
        )
        self.dependencies.memory_service.record_event(event)
        return event.event_id

    def _record_generate_sql_result(
        self,
        request: AnalysisTaskRequest,
        *,
        model_output: dict[str, Any],
        prompt_version: str,
    ) -> str:
        if model_output.get("status") == "ok" and model_output.get("sql"):
            event = MemoryEvent(
                event_id=f"{request.task_id}:memory:sql_generated",
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                session_id=request.session_id,
                task_id=request.task_id,
                trace_id=request.trace_id,
                event_type="sql_generated",
                event_seq=2,
                payload=SqlGeneratedPayload(
                    sql=str(model_output["sql"]),
                    dataset_ids=list(request.dataset_ids),
                    selected_dataset_id=self._select_dataset_id(request) or "",
                    prompt_version=prompt_version,
                    model=self.dependencies.model_client.model_name,
                ),
                created_at=datetime.now(timezone.utc),
            )
        else:
            event = MemoryEvent(
                event_id=f"{request.task_id}:memory:answer_generated",
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                session_id=request.session_id,
                task_id=request.task_id,
                trace_id=request.trace_id,
                event_type="answer_generated",
                event_seq=2,
                payload=AnswerGeneratedPayload(answer=self._final_answer(model_output)),
                created_at=datetime.now(timezone.utc),
            )
        self.dependencies.memory_service.record_event(event)
        return event.event_id

    def _record_task_failed(
        self,
        request: AnalysisTaskRequest,
        *,
        failure_stage: str,
        error_message: str,
        event_seq: int,
        memory_event_ids: list[str],
    ) -> None:
        event = MemoryEvent(
            event_id=f"{request.task_id}:memory:task_failed:{failure_stage}",
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            session_id=request.session_id,
            task_id=request.task_id,
            trace_id=request.trace_id,
            event_type="task_failed",
            event_seq=event_seq,
            payload=TaskFailedPayload(
                failure_stage=failure_stage,
                error_message=error_message,
            ),
            created_at=datetime.now(timezone.utc),
        )
        self.dependencies.memory_service.record_event(event)
        memory_event_ids.append(event.event_id)

    def _parse_model_output(self, raw_output: str) -> dict[str, Any] | None:
        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        if parsed.get("status") not in {"ok", "clarification_required", "cannot_generate"}:
            return None
        return parsed

    def _final_answer(self, model_output: dict[str, Any]) -> str:
        status = model_output.get("status")
        reason = str(model_output.get("reason") or "")
        if status == "ok":
            return "已完成 SQL 生成节点，候选 SQL 已进入后续校验准备。"
        if status == "clarification_required":
            return reason or "当前问题需要补充信息后才能生成 SQL。"
        return reason or "当前上下文不足，暂时无法生成可靠 SQL。"

    def _result(
        self,
        request: AnalysisTaskRequest,
        *,
        status: RuntimeTurnStatus,
        final_answer: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
        prompt_version: str | None,
        rendered_prompt_hash: str | None,
        memory_event_ids: list[str],
        warnings: list[str],
    ) -> RuntimeTurnResult:
        return RuntimeTurnResult(
            task_id=request.task_id,
            trace_id=request.trace_id,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            session_id=request.session_id,
            status=status,
            final_answer=final_answer,
            failure_code=failure_code,
            failure_message=failure_message,
            prompt_version=prompt_version,
            rendered_prompt_hash=rendered_prompt_hash,
            memory_event_ids=list(memory_event_ids),
            runtime_event_count=self._event_seq,
            warnings=list(warnings),
        )
