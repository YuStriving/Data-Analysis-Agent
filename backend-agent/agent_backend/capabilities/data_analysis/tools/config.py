from __future__ import annotations

from agent_backend.agent_runtime.tool_calling.contracts import (
    ToolExecutionOptions,
)
from agent_backend.capabilities.data_analysis.tools.policy import (
    DataAnalysisToolAccessPolicy,
)


def build_data_analysis_tool_options() -> dict[tuple[str, str], ToolExecutionOptions]:
    """Declare execution settings at the data-analysis assembly seam."""
    return {
        ("mysql.schema_reader", "v1"): ToolExecutionOptions(
            version="v1",
            output_schema={
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string"},
                    "dataset_type": {"type": "string"},
                    "relations": {"type": "array"},
                },
                "required": ["dataset_id", "dataset_type", "relations"],
            },
            timeout_ms=10000,
        ),
        ("mysql.query_executor", "v1"): ToolExecutionOptions(
            version="v1",
            output_schema={
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string"},
                    "dataset_type": {"type": "string"},
                    "columns": {"type": "array"},
                    "rows": {"type": "array"},
                    "row_count": {"type": "integer"},
                    "truncated": {"type": "boolean"},
                    "execution_time_ms": {"type": "integer"},
                },
                "required": [
                    "dataset_id",
                    "dataset_type",
                    "columns",
                    "rows",
                    "row_count",
                    "truncated",
                    "execution_time_ms",
                ],
            },
            timeout_ms=10000,
        ),
        ("file.relation_normalizer", "v1"): ToolExecutionOptions(
            version="v1",
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
            timeout_ms=10000,
        ),
        ("relation.query_executor", "v1"): ToolExecutionOptions(
            version="v1",
            output_schema={
                "type": "object",
                "properties": {
                    "normalized_relation_id": {"type": "string"},
                    "columns": {"type": "array"},
                    "rows": {"type": "array"},
                    "row_count": {"type": "integer"},
                    "truncated": {"type": "boolean"},
                    "execution_time_ms": {"type": "integer"},
                },
                "required": [
                    "normalized_relation_id",
                    "columns",
                    "rows",
                    "row_count",
                    "truncated",
                    "execution_time_ms",
                ],
            },
            timeout_ms=10000,
        ),
        ("chart.spec_builder", "v1"): ToolExecutionOptions(
            version="v1",
            output_schema={
                "type": "object",
                "properties": {"chart": {"type": "object"}, "warnings": {"type": "array"}},
                "required": ["chart", "warnings"],
            },
            timeout_ms=5000,
        ),
    }


def build_data_analysis_tool_access_policies() -> dict[tuple[str, str], DataAnalysisToolAccessPolicy]:
    """Keep business access and SQL requirements out of tool descriptions."""
    return {
        ("mysql.schema_reader", "v1"): DataAnalysisToolAccessPolicy(
            allowed_agents=["data_analysis_agent"],
            allowed_nodes=["load_schema", "build_context"],
            required_permissions=["dataset:read"],
            supported_dataset_types=["mysql"],
            risk_level="low",
            requires_readonly_sql=False,
        ),
        ("mysql.query_executor", "v1"): DataAnalysisToolAccessPolicy(
            allowed_agents=["data_analysis_agent"],
            allowed_nodes=["execute_sql"],
            required_permissions=["dataset:read", "query:execute"],
            supported_dataset_types=["mysql"],
            risk_level="medium",
            requires_readonly_sql=True,
        ),
        ("file.relation_normalizer", "v1"): DataAnalysisToolAccessPolicy(
            allowed_agents=["data_analysis_agent"],
            allowed_nodes=["load_schema", "build_context"],
            required_permissions=["dataset:read"],
            supported_dataset_types=["csv", "xls", "xlsx"],
            risk_level="low",
            requires_readonly_sql=False,
        ),
        ("relation.query_executor", "v1"): DataAnalysisToolAccessPolicy(
            allowed_agents=["data_analysis_agent"],
            allowed_nodes=["execute_sql"],
            required_permissions=["dataset:read", "query:execute"],
            supported_dataset_types=["csv", "xls", "xlsx"],
            risk_level="medium",
            requires_readonly_sql=True,
        ),
        ("chart.spec_builder", "v1"): DataAnalysisToolAccessPolicy(
            allowed_agents=["data_analysis_agent"],
            allowed_nodes=["build_chart"],
            required_permissions=[],
            supported_dataset_types=[],
            risk_level="low",
            requires_readonly_sql=False,
        ),
    }
