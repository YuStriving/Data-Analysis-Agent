from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import pandas as pd
from pydantic import BaseModel, Field

from agent_backend.capabilities.agent_runtime.tool_calling.contracts import ToolDefinition

FileResolver = Callable[[str], str | Path]


class RelationData(BaseModel):
    dataset_id: str
    dataset_type: str
    relations: list[dict[str, Any]]
    frames: dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}


class InMemoryRelationStore:
    def __init__(self) -> None:
        self._relations: dict[str, RelationData] = {}

    def put(self, relation_data: RelationData) -> str:
        normalized_relation_id = f"nr_{uuid4().hex}"
        self._relations[normalized_relation_id] = relation_data
        return normalized_relation_id

    def get(self, normalized_relation_id: str) -> RelationData:
        return self._relations[normalized_relation_id]


DEFAULT_RELATION_STORE = InMemoryRelationStore()


def _query_result_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "normalized_relation_id": {"type": "string"},
            "columns": {"type": "array"},
            "rows": {"type": "array"},
            "row_count": {"type": "integer"},
            "truncated": {"type": "boolean"},
            "execution_time_ms": {"type": "integer"},
        },
        "required": ["normalized_relation_id", "columns", "rows", "row_count", "truncated", "execution_time_ms"],
    }


class FileRelationNormalizerTool:
    def __init__(
        self,
        *,
        file_resolver: FileResolver | None = None,
        store: InMemoryRelationStore | None = None,
    ) -> None:
        self._file_resolver = file_resolver or Path
        self._store = store or DEFAULT_RELATION_STORE

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="file.relation_normalizer",
            version="v1",
            description="Normalize CSV, XLS, or XLSX datasets into SQL-safe relations.",
            input_schema={
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string"},
                    "dataset_type": {"type": "string", "enum": ["csv", "xls", "xlsx"]},
                    "file_ref": {"type": "string"},
                    "sheet_names": {"type": "array", "items": {"type": "string"}},
                    "header_row": {"type": "integer", "minimum": 1},
                    "sample_rows": {"type": "integer", "minimum": 0},
                    "max_rows_to_inspect": {"type": "integer", "minimum": 1},
                },
                "required": ["dataset_id", "dataset_type", "file_ref"],
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string"},
                    "dataset_type": {"type": "string"},
                    "normalized_relation_id": {"type": "string"},
                    "relations": {"type": "array"},
                    "warnings": {"type": "array"},
                },
                "required": ["dataset_id", "dataset_type", "normalized_relation_id", "relations", "warnings"],
            },
            allowed_agents=["data_analysis_agent"],
            allowed_nodes=["load_schema"],
            supported_dataset_types=["csv", "xls", "xlsx"],
            required_permissions=["dataset:read"],
            timeout_ms=10000,
            tags=["file", "relation", "schema"],
            risk_level="low",
        )

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        dataset_id = args["dataset_id"]
        dataset_type = args["dataset_type"]
        path = Path(self._file_resolver(args["file_ref"]))
        header_row = int(args.get("header_row", 1))
        sample_rows = int(args.get("sample_rows", 20))
        max_rows_to_inspect = int(args.get("max_rows_to_inspect", 1000))

        frames = self._read_frames(path, dataset_type, args.get("sheet_names"), header_row, max_rows_to_inspect)
        relations: list[dict[str, Any]] = []
        normalized_frames: dict[str, pd.DataFrame] = {}
        for index, (source_name, frame) in enumerate(frames.items(), start=1):
            relation_name = f"relation_{index}"
            normalized_frame, columns = self._normalize_columns(frame, sample_rows)
            normalized_frames[relation_name] = normalized_frame
            relations.append(
                {
                    "relation_name": relation_name,
                    "display_name": source_name,
                    "source_type": "csv_file" if dataset_type == "csv" else "excel_sheet",
                    "source_name": source_name,
                    "row_count_estimate": len(frame),
                    "columns": columns,
                }
            )

        normalized_relation_id = self._store.put(
            RelationData(
                dataset_id=dataset_id,
                dataset_type=dataset_type,
                relations=relations,
                frames=normalized_frames,
            )
        )
        return {
            "dataset_id": dataset_id,
            "dataset_type": dataset_type,
            "normalized_relation_id": normalized_relation_id,
            "relations": relations,
            "warnings": [],
        }

    def _read_frames(
        self,
        path: Path,
        dataset_type: str,
        sheet_names: list[str] | None,
        header_row: int,
        max_rows_to_inspect: int,
    ) -> dict[str, pd.DataFrame]:
        header = header_row - 1
        if dataset_type == "csv":
            return {path.name: pd.read_csv(path, header=header, nrows=max_rows_to_inspect)}

        sheets = sheet_names if sheet_names else None
        loaded = pd.read_excel(path, sheet_name=sheets, header=header, nrows=max_rows_to_inspect)
        if isinstance(loaded, dict):
            return loaded
        source_name = sheet_names[0] if sheet_names else path.stem
        return {source_name: loaded}

    def _normalize_columns(self, frame: pd.DataFrame, sample_rows: int) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
        normalized = frame.copy()
        column_names = [f"col_{index}" for index in range(1, len(normalized.columns) + 1)]
        original_columns = [str(column) for column in normalized.columns]
        normalized.columns = column_names
        columns = []
        for name, original_name in zip(column_names, original_columns, strict=True):
            series = normalized[name]
            sample_values = [
                value.item() if hasattr(value, "item") else value
                for value in series.dropna().head(sample_rows).tolist()
            ]
            columns.append(
                {
                    "name": name,
                    "display_name": original_name,
                    "original_name": original_name,
                    "data_type": str(series.dtype),
                    "nullable": bool(series.isna().any()),
                    "sample_values": sample_values,
                }
            )
        return normalized, columns


class RelationQueryExecutorTool:
    def __init__(self, *, store: InMemoryRelationStore | None = None) -> None:
        self._store = store or DEFAULT_RELATION_STORE

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="relation.query_executor",
            version="v1",
            description="Execute readonly SQL against normalized file relations using DuckDB.",
            input_schema={
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string"},
                    "normalized_relation_id": {"type": "string"},
                    "sql": {"type": "string"},
                    "max_rows": {"type": "integer", "minimum": 1},
                    "relation_names": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["dataset_id", "normalized_relation_id", "sql", "max_rows"],
                "additionalProperties": False,
            },
            output_schema=_query_result_schema(),
            allowed_agents=["data_analysis_agent"],
            allowed_nodes=["execute_sql"],
            supported_dataset_types=["csv", "xls", "xlsx"],
            required_permissions=["dataset:read", "query:execute"],
            timeout_ms=10000,
            tags=["relation", "query", "duckdb", "readonly"],
            risk_level="medium",
        )

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        import duckdb

        started = time.perf_counter()
        normalized_relation_id = args["normalized_relation_id"]
        max_rows = int(args["max_rows"])
        relation_data = self._store.get(normalized_relation_id)
        sql = self._limit_sql(str(args["sql"]), max_rows + 1)

        with duckdb.connect(database=":memory:") as connection:
            for relation_name, frame in relation_data.frames.items():
                connection.register(relation_name, frame)
            result_frame = connection.execute(sql).fetchdf()

        truncated = len(result_frame) > max_rows
        result_frame = result_frame.head(max_rows)
        rows = result_frame.to_dict(orient="records")
        columns = [{"name": name, "type": str(result_frame[name].dtype), "display_name": name} for name in result_frame.columns]
        return {
            "normalized_relation_id": normalized_relation_id,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
            "execution_time_ms": int((time.perf_counter() - started) * 1000),
        }

    def _limit_sql(self, sql: str, limit: int) -> str:
        stripped = sql.strip().rstrip(";")
        return f"SELECT * FROM ({stripped}) AS _tool_query LIMIT {limit}"
