from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from agent_backend.capabilities.data_analysis.tools.runtime import (
    build_data_analysis_tool_runtime,
    build_engine_resolver_from_dataset_metadata,
    build_file_resolver_from_dataset_metadata,
)


def test_engine_resolver_builds_new_engine_from_dataset_metadata(tmp_path: Path) -> None:
    db_path = tmp_path / "sales.db"
    metadata_by_id = _metadata_by_id(db_path)
    resolver = build_engine_resolver_from_dataset_metadata(metadata_by_id)

    first = resolver("dataset-sales")
    second = resolver("dataset-sales")

    assert first is not second
    assert str(first.url).startswith("sqlite:///")
    assert str(second.url).startswith("sqlite:///")


def test_tool_runtime_registers_data_analysis_tools(tmp_path: Path) -> None:
    runtime = build_data_analysis_tool_runtime(
        engine_resolver=build_engine_resolver_from_dataset_metadata(_metadata_by_id(tmp_path / "sales.db"))
    )

    tool_names = {definition.name for definition in runtime.list_tools("data_analysis_agent")}

    assert "mysql.schema_reader" in tool_names
    assert "mysql.query_executor" in tool_names
    assert "chart.spec_builder" in tool_names


def test_file_resolver_supports_local_path_from_dataset_metadata(tmp_path: Path) -> None:
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


def test_schema_reader_runtime_reads_schema_from_metadata_engine(tmp_path: Path) -> None:
    db_path = tmp_path / "sales.db"
    engine = create_engine(_sqlite_url(db_path))
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE sales (order_month TEXT, revenue INTEGER)"))

    runtime = build_data_analysis_tool_runtime(
        engine_resolver=build_engine_resolver_from_dataset_metadata(_metadata_by_id(db_path))
    )
    tool = runtime.registry.get("mysql.schema_reader", "v1")

    result = tool.execute({"dataset_id": "dataset-sales"})

    assert result["dataset_type"] == "mysql"
    assert result["relations"][0]["relation_name"] == "sales"
    assert [column["name"] for column in result["relations"][0]["columns"]] == [
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
