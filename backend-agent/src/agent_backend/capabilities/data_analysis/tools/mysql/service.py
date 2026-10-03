from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from agent_backend.capabilities.agent_runtime.tool_calling.contracts import (
    InputArgsDefinition,
    ToolExecutionContext,
)

EngineResolver = Callable[[str], Engine]


class MySQLSchemaReaderTool:
    def __init__(self, engine_resolver: EngineResolver) -> None:
        self.input_args: InputArgsDefinition = {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string"},
                "table_names": {"type": "array", "items": {"type": "string"}},
                "include_sample_values": {"type": "boolean"},
                "max_tables": {"type": "integer", "minimum": 1},
                "max_columns_per_table": {"type": "integer", "minimum": 1},
                "sample_rows": {"type": "integer", "minimum": 0},
            },
            "required": ["dataset_id"],
            "additionalProperties": False,
        }
        self._engine_resolver = engine_resolver

    name = "mysql.schema_reader"
    description = "Read authorized MySQL schema and return RelationSchema shaped metadata."

    def execute(self, args: dict[str, Any], context: ToolExecutionContext | None = None) -> dict[str, Any]:
        dataset_id = args["dataset_id"]
        engine = self._engine_resolver(dataset_id)
        inspector = inspect(engine)
        table_names = args.get("table_names") or inspector.get_table_names()
        max_tables = args.get("max_tables")
        max_columns = args.get("max_columns_per_table")
        include_samples = bool(args.get("include_sample_values", False))
        sample_rows = int(args.get("sample_rows", 3))
        table_names = list(table_names)[:max_tables]

        relations = []
        for table_name in table_names:
            columns = inspector.get_columns(table_name)
            if max_columns:
                columns = columns[:max_columns]
            sample_values = self._read_sample_values(engine, table_name, columns, sample_rows) if include_samples else {}
            primary_keys = inspector.get_pk_constraint(table_name).get("constrained_columns", [])
            table_comment = self._safe_table_comment(inspector, table_name)
            relations.append(
                {
                    "relation_name": table_name,
                    "display_name": table_comment or table_name,
                    "source_type": "mysql_table",
                    "source_name": table_name,
                    "row_count_estimate": None,
                    "primary_keys": primary_keys,
                    "columns": [
                        {
                            "name": column["name"],
                            "display_name": column.get("comment") or column["name"],
                            "original_name": column["name"],
                            "data_type": str(column["type"]),
                            "nullable": bool(column.get("nullable", True)),
                            "comment": column.get("comment"),
                            "sample_values": sample_values.get(column["name"], []),
                        }
                        for column in columns
                    ],
                }
            )
        return {"dataset_id": dataset_id, "dataset_type": "mysql", "relations": relations}

    def _safe_table_comment(self, inspector: Any, table_name: str) -> str | None:
        try:
            return inspector.get_table_comment(table_name).get("text")
        except Exception:  # noqa: BLE001 -- comments are optional across datasource dialects.
            return None

    def _read_sample_values(
        self,
        engine: Engine,
        table_name: str,
        columns: list[dict[str, Any]],
        sample_rows: int,
    ) -> dict[str, list[Any]]:
        if sample_rows <= 0 or not columns:
            return {}
        preparer = engine.dialect.identifier_preparer
        quoted_table = preparer.quote(table_name)
        column_names = [column["name"] for column in columns]
        quoted_columns = ", ".join(preparer.quote(column_name) for column_name in column_names)
        with engine.connect() as connection:
            rows = connection.execute(text(f"SELECT {quoted_columns} FROM {quoted_table} LIMIT {sample_rows}")).mappings()
            samples: dict[str, list[Any]] = {column_name: [] for column_name in column_names}
            for row in rows:
                for column_name in column_names:
                    value = row[column_name]
                    if value is not None and value not in samples[column_name]:
                        samples[column_name].append(value)
            return samples


class MySQLQueryExecutorTool:
    def __init__(self, engine_resolver: EngineResolver) -> None:
        self.input_args: InputArgsDefinition = {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string"},
                "sql": {"type": "string"},
                "max_rows": {"type": "integer", "minimum": 1},
                "relation_names": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["dataset_id", "sql", "max_rows"],
            "additionalProperties": False,
        }
        self._engine_resolver = engine_resolver

    name = "mysql.query_executor"
    description = "Execute readonly SQL on an authorized MySQL dataset and return QueryResult."

    def execute(self, args: dict[str, Any], context: ToolExecutionContext | None = None) -> dict[str, Any]:
        started = time.perf_counter()
        dataset_id = args["dataset_id"]
        max_rows = int(args["max_rows"])
        engine = self._engine_resolver(dataset_id)
        with engine.connect() as connection:
            result = connection.execute(text(args["sql"]))
            fetched = result.mappings().fetchmany(max_rows + 1)
            rows = [dict(row) for row in fetched[:max_rows]]
            columns = [{"name": key, "type": "unknown", "display_name": key} for key in result.keys()]  # noqa: SIM118 -- CursorResult is not a dict.
        return {
            "dataset_id": dataset_id,
            "dataset_type": "mysql",
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": len(fetched) > max_rows,
            "execution_time_ms": int((time.perf_counter() - started) * 1000),
        }
