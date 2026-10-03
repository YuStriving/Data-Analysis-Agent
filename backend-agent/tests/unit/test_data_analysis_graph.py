from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text

from agent_backend.capabilities.agent_runtime.tool_calling import (
    ToolCallingRuntime,
    ToolExecutionContext,
    ToolRegistry,
)
from agent_backend.capabilities.agent_runtime.tool_calling.errors import (
    ToolCallError,
)
from agent_backend.capabilities.data_analysis.tools.runtime import (
    build_data_analysis_tool_authorization_gate,
    build_data_analysis_tool_runtime,
    build_engine_resolver_from_dataset_metadata,
    build_file_resolver_from_dataset_metadata,
)
from agent_backend.foundation.access import AccessContext
from agent_backend.foundation.contracts.task import AnalysisTaskRequest
from agent_backend.foundation.llm.adapters.fake import FakeLlmClient
from agent_backend.orchestration.data_analysis.adapters import request_to_initial_state
from agent_backend.orchestration.data_analysis.graph import build_data_analysis_graph


def schema_runtime(registry: ToolRegistry) -> ToolCallingRuntime:
    gate = build_data_analysis_tool_authorization_gate()
    return ToolCallingRuntime(
        registry, authorize=gate.check, access_policy_resolver=gate.get_policy
    )


class FakeSchemaTool:
    name = "mysql.schema_reader"
    description = "Fake schema reader."

    def __init__(self) -> None:
        self.input_args = {
            "type": "object",
            "properties": {"dataset_id": {"type": "string"}},
            "required": ["dataset_id"],
            "additionalProperties": True,
        }

    def execute(
        self, args: dict[str, Any], context: ToolExecutionContext
    ) -> dict[str, Any]:
        return {
            "dataset_id": args["dataset_id"],
            "dataset_type": "mysql",
            "relations": [
                {
                    "relation_name": "sales",
                    "display_name": "sales",
                    "source_type": "mysql_table",
                    "source_name": "sales",
                    "columns": [
                        {"name": "order_month", "data_type": "TEXT"},
                        {"name": "revenue", "data_type": "INTEGER"},
                    ],
                }
            ],
        }


class FakeFileRelationNormalizerTool:
    name = "file.relation_normalizer"
    description = "Fake file relation normalizer."

    def __init__(self) -> None:
        self.input_args = {
            "type": "object",
            "properties": {"dataset_id": {"type": "string"}},
            "required": ["dataset_id"],
            "additionalProperties": True,
        }

    def execute(
        self, args: dict[str, Any], context: ToolExecutionContext
    ) -> dict[str, Any]:
        return {
            "dataset_id": args["dataset_id"],
            "dataset_type": "csv",
            "relations": [],
        }


def test_data_analysis_graph_injects_llm_client_into_generate_sql() -> None:
    model_client = FakeLlmClient(
        """
        {
          "status": "ok",
          "sql": "SELECT order_month, SUM(revenue) AS revenue FROM sales GROUP BY order_month",
          "reason": "Use monthly revenue aggregation.",
          "used_tables": ["sales"],
          "used_fields": ["order_month", "revenue"],
          "assumptions": [],
          "warnings": [],
          "clarification_questions": []
        }
        """
    )
    graph = build_data_analysis_graph(
        model_client=model_client,
        tool_runtime=schema_runtime(
            ToolRegistry([FakeSchemaTool(), FakeFileRelationNormalizerTool()])
        ),
    )
    state = request_to_initial_state(
        AnalysisTaskRequest(
            task_id="task-1",
            trace_id="trace-1",
            tenant_id="tenant-1",
            user_id="user-1",
            session_id="session-1",
            question="Show monthly revenue trend",
            dataset_ids=["dataset-sales"],
            access_context=AccessContext(
                tenant_id="tenant-1",
                user_id="user-1",
                allowed_dataset_ids=["dataset-sales"],
                readonly=True,
            ),
        )
    )
    state["context"]["dataset_metadata"] = {
        "dataset_id": "dataset-sales",
        "dataset_type": "mysql",
        "display_name": "Sales",
        "mysql": {"sqlalchemy_url": "sqlite:///:memory:"},
    }

    result = graph.invoke(state)

    assert result["error"]["has_error"] is False
    assert result["analysis"]["candidate_sql"].startswith("SELECT order_month")
    assert result["analysis"]["validated_sql"].startswith("SELECT order_month")
    assert result["analysis"]["sql_validation"]["passed"] is True
    assert result["analysis"]["sql_validation"]["referenced_relations"] == ["sales"]
    assert result["analysis"]["model"] == "fake-model"
    assert len(model_client.requests) == 1
    assert [message.role for message in model_client.requests[0].messages] == [
        "system",
        "user",
    ]
    assert "Show monthly revenue trend" in model_client.requests[0].messages[1].content


def test_data_analysis_graph_reads_schema_then_generates_sql(tmp_path: Path) -> None:
    db_path = tmp_path / "sales.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE sales (order_month TEXT, revenue INTEGER)")
        )
    model_client = FakeLlmClient(
        """
        {
          "status": "ok",
          "sql": "SELECT order_month, SUM(revenue) AS revenue FROM sales GROUP BY order_month",
          "reason": "Use the sales table from schema context.",
          "used_tables": ["sales"],
          "used_fields": ["order_month", "revenue"],
          "assumptions": [],
          "warnings": [],
          "clarification_questions": []
        }
        """
    )
    graph = build_data_analysis_graph(model_client=model_client)
    state = request_to_initial_state(_request())
    state["context"]["dataset_metadata_by_id"] = {
        "dataset-sales": {
            "dataset_id": "dataset-sales",
            "dataset_type": "mysql",
            "display_name": "Sales",
            "mysql": {"sqlalchemy_url": f"sqlite:///{db_path.as_posix()}"},
        }
    }

    result = graph.invoke(state)

    assert result["error"]["has_error"] is False
    assert (
        "sales(order_month TEXT, revenue INTEGER)"
        in result["context"]["schema_context"]["schema_summary"]
    )
    assert result["analysis"]["candidate_sql"].startswith("SELECT order_month")
    assert result["analysis"]["validated_sql"].startswith("SELECT order_month")
    assert result["analysis"]["sql_validation"]["passed"] is True
    assert len(model_client.requests) == 1


def test_data_analysis_graph_rejects_runtime_missing_required_schema_tools() -> None:
    with pytest.raises(ToolCallError):
        build_data_analysis_graph(
            model_client=FakeLlmClient("{}"),
            tool_runtime=schema_runtime(ToolRegistry()),
        )


def test_data_analysis_graph_routes_tool_exception_to_failed_terminal_event() -> None:
    error = ToolCallError(
        reason="schema_read_failed",
        message="Schema inspection is unavailable.",
        retryable=True,
        detail={"dataset_id": "dataset-sales", "table_name": "sales"},
    )

    class UnavailableSchemaTool(FakeSchemaTool):
        def execute(
            self, args: dict[str, Any], context: ToolExecutionContext
        ) -> dict[str, Any]:
            raise error

    model_client = FakeLlmClient("{}")
    graph = build_data_analysis_graph(
        model_client=model_client,
        tool_runtime=schema_runtime(
            ToolRegistry([UnavailableSchemaTool(), FakeFileRelationNormalizerTool()])
        ),
    )
    state = request_to_initial_state(_request())
    state["context"]["dataset_metadata"] = {
        "dataset_id": "dataset-sales",
        "dataset_type": "mysql",
        "mysql": {"sqlalchemy_url": "sqlite:///:memory:"},
    }

    result = graph.invoke(state)

    assert result["graph"]["node_id"] == "fail_task"
    assert result["error"]["has_error"] is True
    assert result["error"]["failure_stage"] == "build_context"
    assert result["error"]["tool_error"] == error.to_payload()
    assert result["output"]["final_answer"] == error.message
    assert model_client.requests == []
    terminal_event = result["graph"]["events"][-1]
    assert terminal_event["event_type"] == "task_failed"
    assert terminal_event["payload"]["tool_error"] == error.to_payload()
    assert terminal_event["task_id"] == "task-1"
    assert terminal_event["trace_id"] == "trace-1"


def test_data_analysis_graph_normalizes_file_schema_then_generates_sql(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("order_month,revenue\n2026-01,100\n", encoding="utf-8")
    metadata_by_id = {
        "dataset-file": {
            "dataset_id": "dataset-file",
            "dataset_type": "csv",
            "display_name": "sales.csv",
            "file_ref": "oss://bucket/sales.csv",
            "local_path": str(csv_path),
            "header_row": 1,
            "sample_rows": 20,
            "max_rows_to_inspect": 1000,
        }
    }
    model_client = FakeLlmClient(
        """
        {
          "status": "ok",
          "sql": "SELECT col_1, SUM(col_2) AS revenue FROM relation_1 GROUP BY col_1",
          "reason": "Use normalized CSV relation columns.",
          "used_tables": ["relation_1"],
          "used_fields": ["col_1", "col_2"],
          "assumptions": [],
          "warnings": [],
          "clarification_questions": []
        }
        """
    )
    graph = build_data_analysis_graph(
        model_client=model_client,
        tool_runtime=build_data_analysis_tool_runtime(
            engine_resolver=build_engine_resolver_from_dataset_metadata({}),
            file_resolver=build_file_resolver_from_dataset_metadata(metadata_by_id),
        ),
    )
    state = request_to_initial_state(
        AnalysisTaskRequest(
            task_id="task-1",
            trace_id="trace-1",
            tenant_id="tenant-1",
            user_id="user-1",
            session_id="session-1",
            question="Show monthly revenue trend",
            dataset_ids=["dataset-file"],
            access_context=AccessContext(
                tenant_id="tenant-1",
                user_id="user-1",
                allowed_dataset_ids=["dataset-file"],
                readonly=True,
            ),
        )
    )
    state["context"]["dataset_metadata_by_id"] = metadata_by_id

    result = graph.invoke(state)

    assert result["error"]["has_error"] is False
    schema_summary = result["context"]["schema_context"]["schema_summary"]
    assert schema_summary.startswith("relation_1(col_1 ")
    assert "col_2 int64" in schema_summary
    assert result["context"]["normalized_relation_id"].startswith("nr_")
    assert result["analysis"]["candidate_sql"].startswith("SELECT col_1")
    assert result["analysis"]["validated_sql"].startswith("SELECT col_1")
    assert result["analysis"]["sql_validation"]["passed"] is True
    assert result["analysis"]["sql_validation"]["referenced_relations"] == [
        "relation_1"
    ]
    assert len(model_client.requests) == 1


def test_data_analysis_graph_rejects_unsafe_sql_before_execution() -> None:
    model_client = FakeLlmClient(
        """
        {
          "status": "ok",
          "sql": "DELETE FROM sales",
          "reason": "Unsafe mutation.",
          "used_tables": ["sales"],
          "used_fields": ["order_month"],
          "assumptions": [],
          "warnings": [],
          "clarification_questions": []
        }
        """
    )
    graph = build_data_analysis_graph(
        model_client=model_client,
        tool_runtime=schema_runtime(
            ToolRegistry([FakeSchemaTool(), FakeFileRelationNormalizerTool()])
        ),
    )
    state = request_to_initial_state(_request())
    state["context"]["dataset_metadata"] = {
        "dataset_id": "dataset-sales",
        "dataset_type": "mysql",
        "display_name": "Sales",
        "mysql": {"sqlalchemy_url": "sqlite:///:memory:"},
    }

    result = graph.invoke(state)

    assert result["error"]["has_error"] is True
    assert result["error"]["error_code"] == "SQL_FORBIDDEN_TOKEN"
    assert result["error"]["failure_stage"] == "validate_sql"
    assert result["analysis"]["sql_validation"]["passed"] is False
    assert result["graph"]["node_id"] == "fail_task"


def _request() -> AnalysisTaskRequest:
    return AnalysisTaskRequest(
        task_id="task-1",
        trace_id="trace-1",
        tenant_id="tenant-1",
        user_id="user-1",
        session_id="session-1",
        question="Show monthly revenue trend",
        dataset_ids=["dataset-sales"],
        access_context=AccessContext(
            tenant_id="tenant-1",
            user_id="user-1",
            allowed_dataset_ids=["dataset-sales"],
            readonly=True,
        ),
    )
