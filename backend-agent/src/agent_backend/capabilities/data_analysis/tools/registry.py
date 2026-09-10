from __future__ import annotations

from pathlib import Path
from typing import Callable

from sqlalchemy.engine import Engine

from agent_backend.capabilities.agent_runtime.tool_calling.registry import ToolRegistry
from agent_backend.capabilities.data_analysis.tools.chart import ChartSpecBuilderTool
from agent_backend.capabilities.data_analysis.tools.mysql import MySQLQueryExecutorTool, MySQLSchemaReaderTool
from agent_backend.capabilities.data_analysis.tools.relation import (
    DEFAULT_RELATION_STORE,
    FileRelationNormalizerTool,
    InMemoryRelationStore,
    RelationQueryExecutorTool,
)

EngineResolver = Callable[[str], Engine]
FileResolver = Callable[[str], str | Path]


def build_data_analysis_tool_registry(
    *,
    engine_resolver: EngineResolver,
    file_resolver: FileResolver | None = None,
    relation_store: InMemoryRelationStore | None = None,
) -> ToolRegistry:
    store = relation_store or DEFAULT_RELATION_STORE
    return ToolRegistry(
        [
            MySQLSchemaReaderTool(engine_resolver),
            MySQLQueryExecutorTool(engine_resolver),
            FileRelationNormalizerTool(file_resolver=file_resolver, store=store),
            RelationQueryExecutorTool(store=store),
            ChartSpecBuilderTool(),
        ]
    )
