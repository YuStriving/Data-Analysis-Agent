from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text

from agent_backend.capabilities.agent_runtime.tool_calling import (
    ToolCallingRuntime,
    ToolDefinition,
    ToolRegistry,
)
from agent_backend.capabilities.agent_runtime.tool_calling.errors import (
    ToolCallingException,
)
from agent_backend.capabilities.data_analysis.tools.runtime import (
    build_data_analysis_tool_runtime,
    build_engine_resolver_from_dataset_metadata,
    build_file_resolver_from_dataset_metadata,
)
from agent_backend.foundation.access import AccessContext
from agent_backend.foundation.contracts.task import AnalysisTaskRequest
from agent_backend.foundation.llm.adapters.fake import FakeLlmClient
from agent_backend.orchestration.data_analysis.adapters import request_to_initial_state
from agent_backend.orchestration.data_analysis.graph import build_data_analysis_graph


class FakeSchemaTool:
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="mysql.schema_reader",
            version="v1",
            description="Fake schema reader.",
            input_schema={
                "type": "object",
                "properties": {"dataset_id": {"type": "string"}},
                "required": ["dataset_id"],
                "additionalProperties": True,
            },
            output_schema={
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string"},
                    "dataset_type": {"type": "string"},
                    "relations": {"type": "array"},
                },
                "required": ["dataset_id", "dataset_type", "relations"],
            },
            allowed_agents=["data_analysis_agent"],
            allowed_nodes=["build_context"],
            supported_dataset_types=["mysql"],
            required_permissions=["dataset:read"],
            timeout_ms=1000,
        )

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
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
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="file.relation_normalizer",
            version="v1",
            description="Fake file relation normalizer.",
            input_schema={
                "type": "object",
                "properties": {"dataset_id": {"type": "string"}},
                "required": ["dataset_id"],
                "additionalProperties": True,
            },
            output_schema={
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string"},
                    "dataset_type": {"type": "string"},
                    "relations": {"type": "array"},
                },
                "required": ["dataset_id", "dataset_type", "relations"],
            },
            allowed_agents=["data_analysis_agent"],
            allowed_nodes=["build_context"],
            supported_dataset_types=["csv", "xls", "xlsx"],
            required_permissions=["dataset:read"],
            timeout_ms=1000,
        )

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
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
        tool_runtime=ToolCallingRuntime(ToolRegistry([FakeSchemaTool(), FakeFileRelationNormalizerTool()])),
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
    }

    result = graph.invoke(state)

    assert result["error"]["has_error"] is False
    assert result["analysis"]["candidate_sql"].startswith("SELECT order_month")
    assert result["analysis"]["model"] == "fake-model"
    assert len(model_client.requests) == 1
    assert "Show monthly revenue trend" in model_client.requests[0].messages[0].content


def test_data_analysis_graph_reads_schema_then_generates_sql(tmp_path: Path) -> None:
    db_path = tmp_path / "sales.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE sales (order_month TEXT, revenue INTEGER)"))
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
    assert "sales(order_month TEXT, revenue INTEGER)" in result["context"]["schema_context"]["schema_summary"]
    assert result["analysis"]["candidate_sql"].startswith("SELECT order_month")
    assert len(model_client.requests) == 1


def test_data_analysis_graph_rejects_runtime_missing_required_schema_tools() -> None:
    with pytest.raises(ToolCallingException):
        build_data_analysis_graph(
            model_client=FakeLlmClient("{}"),
            tool_runtime=ToolCallingRuntime(ToolRegistry()),
        )


def test_data_analysis_graph_normalizes_file_schema_then_generates_sql(tmp_path: Path) -> None:
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
    assert len(model_client.requests) == 1


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
