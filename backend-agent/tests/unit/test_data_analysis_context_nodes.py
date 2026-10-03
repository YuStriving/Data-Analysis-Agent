from __future__ import annotations

from typing import Any

import pytest

from agent_backend.capabilities.agent_runtime.prompt import (
    PromptBudgetGuard,
    PromptBudgetPolicy,
)
from agent_backend.capabilities.agent_runtime.tool_calling import (
    ToolCallingRuntime,
    ToolExecutionContext,
    ToolRegistry,
)
from agent_backend.capabilities.agent_runtime.tool_calling.errors import ToolCallError
from agent_backend.capabilities.data_analysis.tools.runtime import (
    build_data_analysis_tool_authorization_gate,
)
from agent_backend.foundation.access import AccessContext
from agent_backend.foundation.contracts.task import AnalysisTaskRequest
from agent_backend.foundation.llm.adapters.fake import FakeLlmClient
from agent_backend.orchestration.data_analysis.adapters import request_to_initial_state
from agent_backend.orchestration.data_analysis.nodes._shared import fail_node
from agent_backend.orchestration.data_analysis.nodes.build_context import build_context
from agent_backend.orchestration.data_analysis.nodes.fail_task import fail_task
from agent_backend.orchestration.data_analysis.nodes.generate_sql import generate_sql
from agent_backend.orchestration.data_analysis.nodes.load_task_context import (
    load_task_context,
)
from agent_backend.orchestration.data_analysis.nodes.validate_sql import validate_sql


def schema_runtime(registry: ToolRegistry) -> ToolCallingRuntime:
    gate = build_data_analysis_tool_authorization_gate()
    return ToolCallingRuntime(
        registry, authorize=gate.check, access_policy_resolver=gate.get_policy
    )


@pytest.mark.parametrize("field", ["tenant_id", "user_id"])
def test_build_context_rejects_task_and_java_identity_mismatch(field: str) -> None:
    class UnreachableTool(FakeSchemaTool):
        def execute(
            self, args: dict[str, Any], context: ToolExecutionContext
        ) -> dict[str, Any]:
            raise AssertionError(
                "Identity mismatch must be rejected before business execution."
            )

    state = load_task_context(request_to_initial_state(make_request()))
    state["context"]["dataset_metadata"] = _mysql_metadata()
    state["task"]["access_context"][field] = "another-scope"
    result = build_context(
        state, tool_runtime=schema_runtime(ToolRegistry([UnreachableTool()]))
    )
    assert result["error"]["tool_error"]["reason"] == "Task identity mismatch"


def test_build_context_delivers_goal_purpose_and_typed_business_scope() -> None:
    from agent_backend.capabilities.data_analysis.tools.contracts import (
        DataAnalysisToolExecutionContext,
    )

    observed = []

    class CapturingTool(FakeSchemaTool):
        def execute(
            self, args: dict[str, Any], context: ToolExecutionContext
        ) -> dict[str, Any]:
            observed.append(context)
            return super().execute(args, context)

    state = load_task_context(request_to_initial_state(make_request()))
    state["context"]["dataset_metadata"] = _mysql_metadata()
    result = build_context(
        state, tool_runtime=schema_runtime(ToolRegistry([CapturingTool()]))
    )
    assert not result["error"]["has_error"]
    assert isinstance(observed[0], DataAnalysisToolExecutionContext)
    assert observed[0].goal == make_request().question
    assert observed[0].purpose
    assert observed[0].permissions == ["dataset:read"]
    assert observed[0].dataset_scope.allowed_dataset_ids == ["dataset-sales"]


class FakeSchemaTool:
    def __init__(self, *, relations: list[dict[str, Any]] | None = None) -> None:
        self.input_args = {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string"},
                "include_sample_values": {"type": "boolean"},
                "sample_rows": {"type": "integer"},
            },
            "required": ["dataset_id"],
            "additionalProperties": True,
        }
        self.relations = (
            relations
            if relations is not None
            else [
                {
                    "relation_name": "sales",
                    "display_name": "sales",
                    "source_type": "mysql_table",
                    "source_name": "sales",
                    "columns": [
                        {
                            "name": "order_month",
                            "data_type": "TEXT",
                            "display_name": "order_month",
                        },
                        {
                            "name": "revenue",
                            "data_type": "INTEGER",
                            "display_name": "revenue",
                        },
                    ],
                }
            ]
        )

    name = "mysql.schema_reader"
    description = "Fake schema reader."

    def execute(
        self, args: dict[str, Any], context: ToolExecutionContext
    ) -> dict[str, Any]:
        return {
            "dataset_id": args["dataset_id"],
            "dataset_type": "mysql",
            "relations": self.relations,
        }


def make_request(
    *, dataset_ids: list[str] | None = None, readonly: bool = True
) -> AnalysisTaskRequest:
    return AnalysisTaskRequest(
        task_id="task-1",
        trace_id="trace-1",
        tenant_id="tenant-1",
        user_id="user-1",
        session_id="session-1",
        question="Show monthly revenue trend",
        dataset_ids=dataset_ids if dataset_ids is not None else ["dataset-sales"],
        access_context=AccessContext(
            tenant_id="tenant-1",
            user_id="user-1",
            allowed_dataset_ids=["dataset-sales"],
            readonly=readonly,
        ),
    )


def _mysql_metadata(*, display_name: str | None = None) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "dataset_id": "dataset-sales",
        "dataset_type": "mysql",
        "mysql": {"sqlalchemy_url": "sqlite:///:memory:"},
    }
    if display_name is not None:
        metadata["display_name"] = display_name
    return metadata


def test_request_to_initial_state_maps_nested_and_flat_fields() -> None:
    state = request_to_initial_state(make_request(), request_source="http")

    assert state["task"]["task_id"] == "task-1"
    assert state["task_id"] == "task-1"
    assert state["task"]["request_source"] == "http"
    assert state["context"]["dataset_selection_source"] == "none"
    assert state["analysis"] == {}
    assert state["error"]["has_error"] is False


def test_load_task_context_selects_authorized_dataset() -> None:
    state = request_to_initial_state(make_request())

    result = load_task_context(state)

    assert result["context"]["selected_dataset_id"] == "dataset-sales"
    assert result["context"]["inferred_dataset"] is False
    assert result["context"]["dataset_selection_source"] == "explicit"
    assert result["graph"]["next_node"] == "build_context"
    assert result["graph"]["events"][-1]["event_type"] == "task_context_loaded"


def test_load_task_context_can_infer_recent_dataset() -> None:
    state = request_to_initial_state(make_request(dataset_ids=[]))
    state["context"]["recent_dataset_id"] = "dataset-sales"

    result = load_task_context(state)

    assert result["context"]["selected_dataset_id"] == "dataset-sales"
    assert result["context"]["inferred_dataset"] is True
    assert result["context"]["dataset_selection_source"] == "session"


def test_load_task_context_rejects_unsupported_multi_dataset() -> None:
    state = request_to_initial_state(
        make_request(dataset_ids=["dataset-sales", "dataset-other"])
    )

    result = load_task_context(state)

    assert result["error"]["has_error"] is True
    assert result["error"]["error_code"] == "unsupported_multi_dataset"
    assert result["graph"]["next_node"] == "fail_task"


def test_load_task_context_rejects_non_readonly_context() -> None:
    state = request_to_initial_state(make_request(readonly=False))

    result = load_task_context(state)

    assert result["error"]["has_error"] is True
    assert result["error"]["error_code"] == "readonly_required"


def test_build_context_calls_schema_tool_and_builds_context_bundle() -> None:
    state = load_task_context(request_to_initial_state(make_request()))
    state["context"]["dataset_metadata"] = _mysql_metadata(display_name="Sales")
    runtime = schema_runtime(ToolRegistry([FakeSchemaTool()]))

    result = build_context(state, tool_runtime=runtime)

    assert result["error"]["has_error"] is False
    assert result["context"]["dataset_context"]["dataset_type"] == "mysql"
    assert (
        "sales(order_month TEXT, revenue INTEGER)"
        in result["context"]["schema_context"]["schema_summary"]
    )
    assert result["context"]["context_bundle"]["schema"]["schema_summary"]
    assert result["graph"]["next_node"] == "generate_sql"
    assert result["graph"]["events"][-1]["event_type"] == "context_built"


def test_build_context_rejects_empty_schema() -> None:
    state = load_task_context(request_to_initial_state(make_request()))
    state["context"]["dataset_metadata"] = _mysql_metadata()
    runtime = schema_runtime(ToolRegistry([FakeSchemaTool(relations=[])]))

    result = build_context(state, tool_runtime=runtime)

    assert result["error"]["has_error"] is True
    assert result["error"]["error_code"] == "schema_context_empty"


def test_build_context_handles_runtime_exception_as_workflow_failure() -> None:
    error = ToolCallError(
        reason="schema_access_denied",
        message="Schema access was denied.",
        retryable=False,
        detail={"dataset_id": "dataset-sales"},
    )

    class DeniedSchemaTool(FakeSchemaTool):
        def execute(
            self, args: dict[str, Any], context: ToolExecutionContext
        ) -> dict[str, Any]:
            raise error

    state = load_task_context(request_to_initial_state(make_request()))
    state["context"]["dataset_metadata"] = _mysql_metadata()
    runtime = schema_runtime(ToolRegistry([DeniedSchemaTool()]))

    result = build_context(state, tool_runtime=runtime)

    assert result["error"]["has_error"] is True
    assert result["error"]["error_code"] == "schema_context_not_found"
    assert result["error"]["error_message"] == error.message
    assert result["error"]["recoverable"] is True
    assert result["error"]["tool_error"] == error.to_payload()
    assert result["graph"]["next_node"] == "fail_task"
    assert result["graph"]["events"][-1]["payload"]["tool_error"] == error.to_payload()


def test_tool_failure_details_survive_node_and_terminal_events() -> None:
    state = load_task_context(request_to_initial_state(make_request()))
    tool_error: dict[str, Any] = {
        "reason": "schema_access_denied",
        "message": "Schema access was denied.",
        "retryable": False,
        "detail": {"dataset_id": "dataset-sales"},
    }

    result = fail_node(
        state,
        code="schema_context_not_found",
        message=tool_error["message"],
        failure_stage="build_context",
        user_action_required=False,
        recoverable=True,
        tool_error=tool_error,
    )

    assert result["error"]["tool_error"] == tool_error
    assert result["error"]["recoverable"] is True
    assert result["graph"]["events"][-1]["payload"]["tool_error"] == tool_error

    terminal = fail_task(result)

    assert terminal["graph"]["node_id"] == "fail_task"
    assert terminal["graph"]["events"][-1]["event_type"] == "task_failed"
    assert terminal["graph"]["events"][-1]["payload"]["tool_error"] == tool_error


def test_non_tool_failure_events_keep_existing_payload() -> None:
    state = load_task_context(request_to_initial_state(make_request()))

    result = fail_node(
        state,
        code="schema_context_empty",
        message="Schema context is empty.",
        failure_stage="build_context",
        user_action_required=True,
        recoverable=True,
    )

    assert "tool_error" not in result["error"]
    assert "tool_error" not in result["graph"]["events"][-1]["payload"]
    assert "tool_error" not in fail_task(result)["graph"]["events"][-1]["payload"]


def test_build_context_rejects_invalid_dataset_metadata() -> None:
    state = load_task_context(request_to_initial_state(make_request()))
    state["context"]["dataset_metadata"] = {
        "dataset_id": "dataset-sales",
        "dataset_type": "mysql",
    }
    runtime = schema_runtime(ToolRegistry([FakeSchemaTool()]))

    result = build_context(state, tool_runtime=runtime)

    assert result["error"]["has_error"] is True
    assert result["error"]["error_code"] == "invalid_dataset_metadata"
    assert result["error"]["failure_stage"] == "build_context"


def test_generate_sql_builds_prompt_and_routes_to_validate_sql() -> None:
    state = load_task_context(request_to_initial_state(make_request()))
    state["context"]["dataset_metadata"] = _mysql_metadata()
    state = build_context(
        state, tool_runtime=schema_runtime(ToolRegistry([FakeSchemaTool()]))
    )
    model_client = FakeLlmClient(
        """
        {
          "status": "ok",
          "sql": "SELECT order_month, SUM(revenue) AS revenue FROM sales GROUP BY order_month",
          "reason": "Use monthly revenue aggregation.",
          "used_tables": ["sales"],
          "used_fields": ["order_month", "revenue"],
          "assumptions": ["Monthly revenue uses order_month."],
          "warnings": ["Generated SQL still requires validation."],
          "clarification_questions": []
        }
        """
    )

    result = generate_sql(state, model_client=model_client)

    assert result["error"]["has_error"] is False
    assert result["analysis"]["candidate_sql"].startswith("SELECT order_month")
    assert result["analysis"]["sql_dialect"] == "mysql"
    assert result["analysis"]["sql_reasoning"] == "Use monthly revenue aggregation."
    assert result["analysis"]["used_tables"] == ["sales"]
    assert result["analysis"]["used_fields"] == ["order_month", "revenue"]
    assert result["analysis"]["assumptions"] == ["Monthly revenue uses order_month."]
    assert result["analysis"]["sql_generation_warnings"] == [
        "Generated SQL still requires validation."
    ]
    assert result["analysis"]["model"] == "fake-model"
    assert result["graph"]["next_node"] == "validate_sql"
    assert result["graph"]["events"][-1]["event_type"] == "sql_generated"
    assert len(model_client.requests) == 1
    assert [message.role for message in model_client.requests[0].messages] == [
        "system",
        "user",
    ]
    assert "Show monthly revenue trend" in model_client.requests[0].messages[1].content


def test_generate_sql_rejects_invalid_model_output() -> None:
    state = load_task_context(request_to_initial_state(make_request()))
    state["context"]["dataset_metadata"] = _mysql_metadata()
    state = build_context(
        state, tool_runtime=schema_runtime(ToolRegistry([FakeSchemaTool()]))
    )

    result = generate_sql(state, model_client=FakeLlmClient("not-json"))

    assert result["error"]["has_error"] is True
    assert result["error"]["error_code"] == "model_output_invalid"
    assert result["graph"]["next_node"] == "fail_task"
    assert [event["event_type"] for event in result["graph"]["events"]][-2:] == [
        "model_output_invalid",
        "task_failed",
    ]


def test_generate_sql_rejects_ok_result_without_sql() -> None:
    state = load_task_context(request_to_initial_state(make_request()))
    state["context"]["dataset_metadata"] = _mysql_metadata()
    state = build_context(
        state, tool_runtime=schema_runtime(ToolRegistry([FakeSchemaTool()]))
    )
    model_client = FakeLlmClient(
        """
        {
          "status": "ok",
          "sql": "",
          "reason": "No SQL was produced.",
          "used_tables": [],
          "used_fields": [],
          "warnings": [],
          "clarification_questions": []
        }
        """
    )

    result = generate_sql(state, model_client=model_client)

    assert result["error"]["has_error"] is True
    assert result["error"]["error_code"] == "model_output_invalid"
    assert result["graph"]["next_node"] == "fail_task"


def test_generate_sql_blocks_for_clarification_required() -> None:
    state = load_task_context(request_to_initial_state(make_request()))
    state["context"]["dataset_metadata"] = _mysql_metadata()
    state = build_context(
        state, tool_runtime=schema_runtime(ToolRegistry([FakeSchemaTool()]))
    )
    model_client = FakeLlmClient(
        """
        {
          "status": "clarification_required",
          "sql": "",
          "reason": "The requested metric is ambiguous.",
          "used_tables": [],
          "used_fields": [],
          "warnings": ["Metric name is ambiguous."],
          "clarification_questions": ["Which metric should be analyzed?"]
        }
        """
    )

    result = generate_sql(state, model_client=model_client)

    assert result["error"]["has_error"] is True
    assert result["error"]["error_code"] == "clarification_required"
    assert result["error"]["user_action_required"] is True
    assert result["analysis"]["clarification_questions"] == [
        "Which metric should be analyzed?"
    ]
    assert result["analysis"]["sql_generation_warnings"] == [
        "Metric name is ambiguous."
    ]
    assert [event["event_type"] for event in result["graph"]["events"]][-2:] == [
        "sql_generation_blocked",
        "task_failed",
    ]


def test_generate_sql_blocks_when_cannot_generate() -> None:
    state = load_task_context(request_to_initial_state(make_request()))
    state["context"]["dataset_metadata"] = _mysql_metadata()
    state = build_context(
        state, tool_runtime=schema_runtime(ToolRegistry([FakeSchemaTool()]))
    )
    model_client = FakeLlmClient(
        """
        {
          "status": "cannot_generate",
          "sql": "",
          "reason": "The required field is not available in schema context.",
          "used_tables": [],
          "used_fields": [],
          "warnings": [],
          "clarification_questions": []
        }
        """
    )

    result = generate_sql(state, model_client=model_client)

    assert result["error"]["has_error"] is True
    assert result["error"]["error_code"] == "cannot_generate"
    assert result["error"]["user_action_required"] is False
    assert result["graph"]["next_node"] == "fail_task"
    assert result["graph"]["events"][-2]["event_type"] == "sql_generation_blocked"


def test_generate_sql_rejects_missing_context_bundle() -> None:
    state = load_task_context(request_to_initial_state(make_request()))

    result = generate_sql(state, model_client=FakeLlmClient("{}"))

    assert result["error"]["has_error"] is True
    assert result["error"]["error_code"] == "missing_required_context"
    assert result["graph"]["next_node"] == "fail_task"


def test_generate_sql_rejects_unsupported_status() -> None:
    state = load_task_context(request_to_initial_state(make_request()))
    state["context"]["dataset_metadata"] = _mysql_metadata()
    state = build_context(
        state, tool_runtime=schema_runtime(ToolRegistry([FakeSchemaTool()]))
    )
    model_client = FakeLlmClient(
        """
        {
          "status": "partial",
          "sql": "SELECT order_month FROM sales",
          "reason": "Unsupported status.",
          "used_tables": ["sales"],
          "used_fields": ["sales.order_month"],
          "warnings": [],
          "clarification_questions": []
        }
        """
    )

    result = generate_sql(state, model_client=model_client)

    assert result["error"]["has_error"] is True
    assert result["error"]["error_code"] == "model_output_invalid"
    assert result["graph"]["events"][-2]["event_type"] == "model_output_invalid"


def test_generate_sql_rejects_prompt_budget_exceeded() -> None:
    state = load_task_context(request_to_initial_state(make_request()))
    state["context"]["dataset_metadata"] = _mysql_metadata()
    state = build_context(
        state, tool_runtime=schema_runtime(ToolRegistry([FakeSchemaTool()]))
    )

    result = generate_sql(
        state,
        model_client=FakeLlmClient("{}"),
        prompt_budget_guard=PromptBudgetGuard(
            PromptBudgetPolicy(max_rendered_prompt_chars=100, warn_at_ratio=0.8)
        ),
    )

    assert result["error"]["has_error"] is True
    assert result["error"]["error_code"] == "context_budget_exceeded"
    assert result["graph"]["events"][-2]["event_type"] == "context_budget_exceeded"


def test_validate_sql_writes_validation_and_routes_to_execute_sql() -> None:
    state = load_task_context(request_to_initial_state(make_request()))
    state["context"]["dataset_metadata"] = _mysql_metadata()
    state = build_context(
        state, tool_runtime=schema_runtime(ToolRegistry([FakeSchemaTool()]))
    )
    state["analysis"]["candidate_sql"] = (
        "SELECT order_month, SUM(revenue) AS revenue FROM sales GROUP BY order_month"
    )

    result = validate_sql(state)

    assert result["error"]["has_error"] is False
    assert result["analysis"]["validated_sql"].startswith("SELECT order_month")
    assert result["analysis"]["sql_validation"]["passed"] is True
    assert result["analysis"]["sql_validation"]["referenced_relations"] == ["sales"]
    assert result["analysis"]["sql_validation"]["referenced_fields"] == [
        "order_month",
        "revenue",
    ]
    assert result["graph"]["next_node"] == "execute_sql"
    assert result["graph"]["events"][-1]["event_type"] == "sql_validated"


def test_validate_sql_rejects_missing_candidate_sql() -> None:
    state = load_task_context(request_to_initial_state(make_request()))
    state["context"]["dataset_metadata"] = _mysql_metadata()
    state = build_context(
        state, tool_runtime=schema_runtime(ToolRegistry([FakeSchemaTool()]))
    )

    result = validate_sql(state)

    assert result["error"]["has_error"] is True
    assert result["error"]["error_code"] == "SQL_EMPTY"
    assert result["error"]["recoverable"] is True
    assert result["analysis"]["sql_validation"]["passed"] is False
    assert result["graph"]["next_node"] == "fail_task"
    assert result["graph"]["events"][-2]["event_type"] == "sql_rejected"


def test_validate_sql_rejects_unknown_relation_as_non_recoverable() -> None:
    state = load_task_context(request_to_initial_state(make_request()))
    state["context"]["dataset_metadata"] = _mysql_metadata()
    state = build_context(
        state, tool_runtime=schema_runtime(ToolRegistry([FakeSchemaTool()]))
    )
    state["analysis"]["candidate_sql"] = "SELECT order_month FROM secret_sales"

    result = validate_sql(state)

    assert result["error"]["has_error"] is True
    assert result["error"]["error_code"] == "SQL_UNAUTHORIZED_RELATION"
    assert result["error"]["recoverable"] is False
    assert result["analysis"]["sql_validation"]["referenced_relations"] == [
        "secret_sales"
    ]


def test_validate_sql_allows_file_relation_schema() -> None:
    state = load_task_context(request_to_initial_state(make_request()))
    state["context"]["schema_context"] = {
        "schema_summary": "relation_1(col_1 object, col_2 int64)",
        "field_summary": {
            "relation_1": {
                "columns": [
                    {"name": "col_1", "data_type": "object"},
                    {"name": "col_2", "data_type": "int64"},
                ]
            }
        },
        "truncated": False,
    }
    state["analysis"]["candidate_sql"] = (
        "SELECT col_1, SUM(col_2) AS revenue FROM relation_1 GROUP BY col_1"
    )

    result = validate_sql(state)

    assert result["error"]["has_error"] is False
    assert result["analysis"]["sql_validation"]["referenced_relations"] == [
        "relation_1"
    ]
    assert result["analysis"]["sql_validation"]["referenced_fields"] == [
        "col_1",
        "col_2",
    ]
    assert result["graph"]["next_node"] == "execute_sql"
