from __future__ import annotations

from typing import Any

from agent_backend.capabilities.agent_runtime.tool_calling.contracts import ToolDefinition


def build_line_chart(title: str) -> dict:
    return {
        "title": {"text": title},
        "xAxis": {"type": "category", "data": ["Jan", "Feb", "Mar"]},
        "yAxis": {"type": "value"},
        "series": [{"type": "line", "data": [120, 132, 101]}],
    }


class ChartSpecBuilderTool:
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="chart.spec_builder",
            version="v1",
            description="Build frontend-neutral chart specs from a QueryResult.",
            input_schema={
                "type": "object",
                "properties": {
                    "query_result": {"type": "object"},
                    "chart_type": {"type": "string", "enum": ["bar", "line", "pie", "table"]},
                    "intent": {"type": "string"},
                    "field_mapping": {"type": "object"},
                    "max_points": {"type": "integer", "minimum": 1},
                },
                "required": ["query_result"],
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "properties": {
                    "chart": {"type": "object"},
                    "warnings": {"type": "array"},
                },
                "required": ["chart", "warnings"],
            },
            allowed_agents=["data_analysis_agent"],
            allowed_nodes=["build_chart"],
            supported_dataset_types=[],
            required_permissions=[],
            timeout_ms=5000,
            tags=["chart", "spec"],
            risk_level="low",
        )

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        query_result = args["query_result"]
        rows = list(query_result.get("rows", []))
        columns = list(query_result.get("columns", []))
        max_points = int(args.get("max_points", 100))
        chart_type = args.get("chart_type") or self._infer_chart_type(columns)
        field_mapping = args.get("field_mapping") or self._infer_field_mapping(columns)
        warnings = []

        chart_rows = rows[:max_points]
        truncated = len(rows) > max_points
        if truncated:
            warnings.append(
                {
                    "code": "CHART_DATA_TRUNCATED",
                    "message": "Chart data exceeds max_points and has been truncated.",
                }
            )

        chart = {
            "type": chart_type,
            "title": args.get("intent") or "分析结果",
            "xField": field_mapping.get("xField"),
            "yField": field_mapping.get("yField"),
            "seriesField": field_mapping.get("seriesField"),
            "data": chart_rows,
            "encoding": self._build_encoding(columns, field_mapping),
            "truncated": truncated,
            "max_points": max_points,
        }
        return {"chart": chart, "warnings": warnings}

    def _infer_chart_type(self, columns: list[dict[str, Any]]) -> str:
        if len(columns) < 2:
            return "table"
        first_type = str(columns[0].get("type", columns[0].get("data_type", ""))).lower()
        if "date" in first_type or "time" in first_type:
            return "line"
        return "bar"

    def _infer_field_mapping(self, columns: list[dict[str, Any]]) -> dict[str, str | None]:
        if len(columns) < 2:
            return {"xField": columns[0]["name"] if columns else None, "yField": None, "seriesField": None}
        return {"xField": columns[0]["name"], "yField": columns[1]["name"], "seriesField": None}

    def _build_encoding(
        self,
        columns: list[dict[str, Any]],
        field_mapping: dict[str, str | None],
    ) -> dict[str, dict[str, str | None]]:
        by_name = {column["name"]: column for column in columns if "name" in column}
        encoding = {}
        for channel, mapping_key in (("x", "xField"), ("y", "yField"), ("series", "seriesField")):
            field = field_mapping.get(mapping_key)
            column = by_name.get(field) if field else None
            encoding[channel] = {
                "field": field,
                "display_name": column.get("display_name") if column else field,
            }
        return encoding

