from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, NoReturn

import pytest
from sqlalchemy import create_engine, text

from agent_backend.agent_runtime.tool_calling import (
    ToolCallError,
    ToolCallRequest,
    ToolExecutor,
)
from agent_backend.capabilities.data_analysis.tools.contracts import (
    DataAnalysisToolExecutionContext,
    DatasetScope,
)
from agent_backend.capabilities.data_analysis.tools.runtime import (
    build_data_analysis_tool_runtime,
    build_engine_resolver_from_dataset_metadata,
    build_file_resolver_from_dataset_metadata,
)


def test_engine_resolver_builds_new_engine_from_dataset_metadata(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "sales.db"
    metadata_by_id = _metadata_by_id(db_path)
    resolver = build_engine_resolver_from_dataset_metadata(metadata_by_id)

    first = resolver("dataset-sales")
    second = resolver("dataset-sales")

    assert first is not second
    assert str(first.url).startswith("sqlite:///")
    assert str(second.url).startswith("sqlite:///")


@pytest.mark.parametrize(
    ("overrides", "expected_reason"),
    [
        ({"agent_name": "other_agent"}, "Agent not allowed"),
        ({"node_id": "build_chart"}, "Node not allowed"),
        ({"permissions": ["dataset:read"]}, "Missing permissions"),
        ({"allowed_dataset_ids": []}, "Dataset not allowed"),
        ({"dataset_types": {"dataset-sales": "csv"}}, "Dataset type unsupported"),
        ({"sql": "DELETE FROM sales"}, "SQL guardrail rejected"),
    ],
)
def test_minimal_business_tools_preserve_factory_injected_access_checks(
    overrides: dict[str, Any],
    expected_reason: str,
) -> None:
    def resolver(dataset_id: str) -> NoReturn:
        raise AssertionError("Rejected tool call reached the datasource.")

    runtime = build_data_analysis_tool_runtime(engine_resolver=resolver)
    request = ToolCallRequest(
        tool_name="mysql.query_executor",
        args={
            "dataset_id": "dataset-sales",
            "sql": overrides.get("sql", "SELECT * FROM sales"),
            "max_rows": 1,
        },
        context=DataAnalysisToolExecutionContext(
            tool_call_id="call-1",
            tool_version="v1",
            agent_name=overrides.get("agent_name", "data_analysis_agent"),
            agent_version="v1",
            node_id=overrides.get("node_id", "execute_sql"),
            task_id="task-1",
            trace_id="trace-1",
            session_id="session-1",
            tenant_id="tenant-1",
            user_id="user-1",
            dataset_scope=DatasetScope(
                allowed_dataset_ids=overrides.get(
                    "allowed_dataset_ids", ["dataset-sales"]
                ),
                dataset_types=overrides.get(
                    "dataset_types", {"dataset-sales": "mysql"}
                ),
            ),
            timeout_ms=1000,
            permissions=overrides.get("permissions", ["dataset:read", "query:execute"]),
            goal="Analyze sales",
            purpose="Execute the selected analysis step",
        ),
    )

    with pytest.raises(ToolCallError) as caught:
        asyncio.run(runtime.call(request))

    assert caught.value.reason == expected_reason
    assert not caught.value.retryable


def test_tool_runtime_registers_data_analysis_tools(tmp_path: Path) -> None:
    runtime = build_data_analysis_tool_runtime(
        engine_resolver=build_engine_resolver_from_dataset_metadata(
            _metadata_by_id(tmp_path / "sales.db")
        )
    )

    tool_names = {
        definition.name for definition in runtime.list_tools("data_analysis_agent")
    }

    assert "mysql.schema_reader" in tool_names
    assert "mysql.query_executor" in tool_names
    assert "chart.spec_builder" in tool_names


def test_file_resolver_supports_local_path_from_dataset_metadata(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("month,revenue\n2026-01,100\n", encoding="utf-8")
    resolver = build_file_resolver_from_dataset_metadata(
        {
            "dataset-file": {
                "dataset_id": "dataset-file",
                "dataset_type": "csv",
                "file_ref": "oss://bucket/sales.csv",
                "local_path": str(csv_path),
            }
        }
    )

    assert resolver("oss://bucket/sales.csv") == csv_path


def test_file_resolver_supports_file_uri(tmp_path: Path) -> None:
    csv_path = tmp_path / "sales.csv"
    resolver = build_file_resolver_from_dataset_metadata({})

    assert resolver(csv_path.as_uri()) == csv_path


def test_file_resolver_rejects_oss_without_local_path() -> None:
    resolver = build_file_resolver_from_dataset_metadata({})

    try:
        resolver("oss://bucket/sales.csv")
    except ValueError as exc:
        assert "Java-issued signed URL" in str(exc)
    else:
        raise AssertionError("oss:// file_ref should require Java-issued access")


def test_file_resolver_rejects_metadata_oss_without_local_path() -> None:
    resolver = build_file_resolver_from_dataset_metadata(
        {
            "dataset-file": {
                "dataset_id": "dataset-file",
                "dataset_type": "csv",
                "file_ref": "oss://bucket/sales.csv",
            }
        }
    )

    with pytest.raises(ValueError, match="local_path is required"):
        resolver("oss://bucket/sales.csv")


def test_schema_reader_runtime_reads_schema_from_metadata_engine(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "sales.db"
    engine = create_engine(_sqlite_url(db_path))
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE sales (order_month TEXT, revenue INTEGER)")
        )

    runtime = build_data_analysis_tool_runtime(
        engine_resolver=build_engine_resolver_from_dataset_metadata(
            _metadata_by_id(db_path)
        )
    )
    result = asyncio.run(
        ToolExecutor(
            options=runtime.registry.get_options("mysql.schema_reader", "v1"),
            authorize=runtime.authorize,
        ).execute(
            runtime.registry.get("mysql.schema_reader", "v1"),
            {"dataset_id": "dataset-sales"},
            DataAnalysisToolExecutionContext(
                agent_name="data_analysis_agent",
                agent_version="v1",
                node_id="build_context",
                task_id="task-1",
                trace_id="trace-1",
                session_id="session-1",
                tenant_id="tenant-1",
                user_id="user-1",
                dataset_scope=DatasetScope(
                    allowed_dataset_ids=["dataset-sales"],
                    dataset_types={"dataset-sales": "mysql"},
                ),
                permissions=["dataset:read"],
                goal="Analyze sales",
                purpose="Execute the selected analysis step",
            ),
        )
    )

    assert result.data["dataset_type"] == "mysql"
    assert result.data["relations"][0]["relation_name"] == "sales"
    assert [column["name"] for column in result.data["relations"][0]["columns"]] == [
        "order_month",
        "revenue",
    ]


def _metadata_by_id(db_path: Path) -> dict[str, dict[str, object]]:
    return {
        "dataset-sales": {
            "dataset_id": "dataset-sales",
            "dataset_type": "mysql",
            "display_name": "Sales",
            "mysql": {
                "sqlalchemy_url": _sqlite_url(db_path),
            },
        }
    }


def _sqlite_url(db_path: Path) -> str:
    return f"sqlite:///{db_path.as_posix()}"
