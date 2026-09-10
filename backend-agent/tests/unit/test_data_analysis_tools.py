from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from agent_backend.capabilities.agent_runtime.tool_calling import DatasetScope, ToolCallRequest, ToolCallingRuntime, ToolRegistry
from agent_backend.capabilities.data_analysis.tools.chart import ChartSpecBuilderTool
from agent_backend.capabilities.data_analysis.tools.mysql import MySQLQueryExecutorTool, MySQLSchemaReaderTool
from agent_backend.capabilities.data_analysis.tools.relation import (
    FileRelationNormalizerTool,
    InMemoryRelationStore,
    RelationQueryExecutorTool,
)


def test_mysql_schema_reader_returns_relation_schema() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE sales (region TEXT, amount INTEGER)"))
        connection.execute(text("INSERT INTO sales VALUES ('east', 10)"))
    tool = MySQLSchemaReaderTool(lambda dataset_id: engine)

    result = tool.execute({"dataset_id": "dataset-1", "include_sample_values": True, "sample_rows": 1})

    assert result["relations"][0]["relation_name"] == "sales"
    assert result["relations"][0]["columns"][0]["name"] == "region"
    assert result["relations"][0]["columns"][0]["sample_values"] == ["east"]


def test_mysql_query_executor_enforces_max_rows() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE sales (region TEXT, amount INTEGER)"))
        connection.execute(text("INSERT INTO sales VALUES ('east', 10), ('west', 20)"))
    tool = MySQLQueryExecutorTool(lambda dataset_id: engine)

    result = tool.execute({"dataset_id": "dataset-1", "sql": "SELECT * FROM sales", "max_rows": 1})

    assert result["row_count"] == 1
    assert result["truncated"]


def test_file_relation_normalizer_maps_csv_to_safe_names(tmp_path: Path) -> None:
    path = tmp_path / "sales.csv"
    path.write_text("地区,销售金额(元)\n华东,120\n", encoding="utf-8")
    store = InMemoryRelationStore()
    tool = FileRelationNormalizerTool(store=store)

    result = tool.execute({"dataset_id": "dataset-1", "dataset_type": "csv", "file_ref": str(path)})

    relation = result["relations"][0]
    assert relation["relation_name"] == "relation_1"
    assert relation["display_name"] == "sales.csv"
    assert relation["columns"][0]["name"] == "col_1"
    assert relation["columns"][0]["display_name"] == "地区"


def test_relation_query_executor_uses_duckdb(tmp_path: Path) -> None:
    pytest.importorskip("duckdb")
    path = tmp_path / "sales.csv"
    path.write_text("地区,销售金额(元)\n华东,120\n华北,90\n", encoding="utf-8")
    store = InMemoryRelationStore()
    normalizer = FileRelationNormalizerTool(store=store)
    normalized = normalizer.execute({"dataset_id": "dataset-1", "dataset_type": "csv", "file_ref": str(path)})
    tool = RelationQueryExecutorTool(store=store)

    result = tool.execute(
        {
            "dataset_id": "dataset-1",
            "normalized_relation_id": normalized["normalized_relation_id"],
            "sql": "SELECT col_1, col_2 FROM relation_1",
            "max_rows": 1,
        }
    )

    assert result["row_count"] == 1
    assert result["truncated"]


def test_chart_spec_builder_truncates_data() -> None:
    tool = ChartSpecBuilderTool()

    result = tool.execute(
        {
            "query_result": {
                "columns": [
                    {"name": "col_1", "display_name": "地区", "type": "object"},
                    {"name": "col_2", "display_name": "销售金额", "type": "int64"},
                ],
                "rows": [{"col_1": "华东", "col_2": 120}, {"col_1": "华北", "col_2": 90}],
            },
            "max_points": 1,
        }
    )

    assert result["chart"]["type"] == "bar"
    assert result["chart"]["xField"] == "col_1"
    assert result["chart"]["truncated"]
    assert result["warnings"][0]["code"] == "CHART_DATA_TRUNCATED"


def test_runtime_can_call_chart_tool_without_dataset_scope() -> None:
    runtime = ToolCallingRuntime(ToolRegistry([ChartSpecBuilderTool()]))
    request = ToolCallRequest(
        tool_call_id="call-1",
        tool_name="chart.spec_builder",
        tool_version="v1",
        agent_name="data_analysis_agent",
        agent_version="v1",
        node_id="build_chart",
        task_id="task-1",
        trace_id="trace-1",
        session_id="session-1",
        tenant_id="tenant-1",
        user_id="user-1",
        dataset_scope=DatasetScope(),
        args={"query_result": {"columns": [], "rows": []}},
        timeout_ms=1000,
    )

    result = asyncio.run(runtime.call(request))

    assert result.success
