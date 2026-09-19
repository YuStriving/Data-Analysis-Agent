from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from sqlalchemy import URL, create_engine
from sqlalchemy.engine import Engine

from agent_backend.capabilities.agent_runtime.tool_calling.runtime import (
    ToolCallingRuntime,
)
from agent_backend.capabilities.data_analysis.contracts import (
    validate_dataset_metadata,
)
from agent_backend.capabilities.data_analysis.tools.registry import (
    EngineResolver,
    FileResolver,
    build_data_analysis_tool_registry,
)
from agent_backend.capabilities.data_analysis.tools.relation import (
    InMemoryRelationStore,
)

DatasetMetadataById = Mapping[str, Mapping[str, Any]]
REQUIRED_DATA_ANALYSIS_TOOLS = (
    ("mysql.schema_reader", "v1"),
    ("file.relation_normalizer", "v1"),
)


def build_data_analysis_tool_runtime(
    *,
    engine_resolver: EngineResolver,
    file_resolver: FileResolver | None = None,
    relation_store: InMemoryRelationStore | None = None,
) -> ToolCallingRuntime:
    registry = build_data_analysis_tool_registry(
        engine_resolver=engine_resolver,
        file_resolver=file_resolver,
        relation_store=relation_store,
    )
    return ToolCallingRuntime(registry)


def build_default_data_analysis_tool_runtime(
    dataset_metadata_by_id: DatasetMetadataById | None = None,
    *,
    relation_store: InMemoryRelationStore | None = None,
) -> ToolCallingRuntime:
    metadata_by_id = dataset_metadata_by_id if dataset_metadata_by_id is not None else {}
    runtime = build_data_analysis_tool_runtime(
        engine_resolver=build_engine_resolver_from_dataset_metadata(metadata_by_id),
        file_resolver=build_file_resolver_from_dataset_metadata(metadata_by_id),
        relation_store=relation_store,
    )
    validate_data_analysis_tool_runtime(runtime)
    return runtime


def validate_data_analysis_tool_runtime(runtime: ToolCallingRuntime) -> None:
    for tool_name, tool_version in REQUIRED_DATA_ANALYSIS_TOOLS:
        runtime.get_tool(tool_name, tool_version)


def build_file_resolver_from_dataset_metadata(
    dataset_metadata_by_id: DatasetMetadataById,
) -> FileResolver:
    def _resolve(file_ref: str) -> str | Path:
        file_ref_to_path = _file_ref_path_map(dataset_metadata_by_id)
        if file_ref in file_ref_to_path:
            return file_ref_to_path[file_ref]
        return _resolve_local_file_ref(file_ref)

    return _resolve


def build_engine_resolver_from_dataset_metadata(
    dataset_metadata_by_id: DatasetMetadataById,
) -> EngineResolver:
    def _resolve(dataset_id: str) -> Engine:
        raw_metadata = dataset_metadata_by_id.get(dataset_id)
        if raw_metadata is None:
            raise ValueError(f"Dataset metadata was not found: {dataset_id}")
        metadata = validate_dataset_metadata(
            dict(raw_metadata),
            expected_dataset_id=dataset_id,
        ).to_runtime_metadata()
        if metadata.get("dataset_type") != "mysql":
            raise ValueError(f"Dataset is not a MySQL dataset: {dataset_id}")

        # TODO(security): Replace inline MySQL credentials with a Java-issued
        # secret reference or short-lived readonly connection credentials before
        # production.
        # TODO(perf): Cache Engines by dataset/connection fingerprint and close
        # them on rotation or worker shutdown.
        return create_engine(_mysql_engine_url(metadata), pool_pre_ping=True)

    return _resolve


def _file_ref_path_map(dataset_metadata_by_id: DatasetMetadataById) -> dict[str, str | Path]:
    mapping: dict[str, str | Path] = {}
    for raw_metadata in dataset_metadata_by_id.values():
        metadata = validate_dataset_metadata(dict(raw_metadata)).to_runtime_metadata()
        dataset_type = metadata.get("dataset_type")
        if dataset_type not in {"csv", "xls", "xlsx"}:
            continue
        file_ref = metadata.get("file_ref")
        if not isinstance(file_ref, str) or not file_ref.strip():
            continue
        local_path = metadata.get("local_path")
        if local_path is None:
            file = metadata.get("file")
            if isinstance(file, Mapping):
                local_path = file.get("local_path")
        if isinstance(local_path, str) and local_path.strip():
            mapping[file_ref] = _resolve_local_file_ref(local_path)
    return mapping


def _resolve_local_file_ref(file_ref: str) -> str | Path:
    if not isinstance(file_ref, str) or not file_ref.strip():
        raise ValueError("file_ref is required")
    if _looks_like_windows_path(file_ref):
        return Path(file_ref)
    parsed = urlparse(file_ref)
    if parsed.scheme in {"", None}:
        return Path(file_ref)
    if parsed.scheme == "file":
        path = unquote(parsed.path)
        if path.startswith("/") and _looks_like_windows_path(path[1:]):
            path = path[1:]
        return Path(path)
    if parsed.scheme == "oss":
        # TODO(storage): Resolve oss:// file refs through Java-issued signed
        # URLs or short-lived file access tokens. Python must not hold long-lived
        # OSS credentials.
        raise ValueError("OSS file_ref requires a Java-issued signed URL or local_path")
    raise ValueError(f"Unsupported file_ref scheme: {parsed.scheme}")


def _looks_like_windows_path(value: str) -> bool:
    return len(value) >= 3 and value[1] == ":" and value[0].isalpha() and value[2] in {"\\", "/"}


def _mysql_engine_url(metadata: Mapping[str, Any]) -> URL | str:
    mysql = metadata.get("mysql")
    if not isinstance(mysql, Mapping):
        raise TypeError("MySQL connection metadata is required")

    sqlalchemy_url = mysql.get("sqlalchemy_url")
    if isinstance(sqlalchemy_url, str) and sqlalchemy_url.strip():
        return sqlalchemy_url

    driver = _required_str(mysql, "driver", default="mysql+pymysql")
    username = _required_str(mysql, "username")
    password = _required_str(mysql, "password")
    host = _required_str(mysql, "host")
    database = _database_name(mysql)
    port = _port(mysql)
    query = mysql.get("query")
    if query is not None and not isinstance(query, dict):
        raise ValueError("MySQL query options must be a mapping")

    return URL.create(
        drivername=driver,
        username=username,
        password=password,
        host=host,
        port=port,
        database=database,
        query=query,
    )


def _required_str(mapping: Mapping[str, Any], key: str, *, default: str | None = None) -> str:
    value = mapping.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"MySQL connection field is required: {key}")
    return value


def _database_name(mysql: Mapping[str, Any]) -> str:
    value = mysql.get("database", mysql.get("database_name"))
    if not isinstance(value, str) or not value.strip():
        raise ValueError("MySQL connection field is required: database")
    return value


def _port(mysql: Mapping[str, Any]) -> int:
    value = mysql.get("port", 3306)
    if not isinstance(value, int) or value <= 0:
        raise ValueError("MySQL connection port must be a positive integer")
    return value
