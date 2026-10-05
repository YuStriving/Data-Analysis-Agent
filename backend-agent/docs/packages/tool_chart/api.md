# Python Tool Chart 接口文档

图表工具实现位于 `src/agent_backend/capabilities/data_analysis/tools/chart/service.py`。
只有 `ChartSpecBuilderTool` 是当前工具运行时注册的业务工具；其输出是前端无关 spec，
不是 ECharts 配置。

## 1. 当前公开函数

### `build_line_chart(title: str) -> dict`

当前返回示例：

```json
{
  "title": {"text": "Monthly Revenue"},
  "xAxis": {"type": "category", "data": ["Jan", "Feb", "Mar"]},
  "yAxis": {"type": "value"},
  "series": [{"type": "line", "data": [120, 132, 101]}]
}
```

## 2. `ChartSpecBuilderTool.execute(args, context=None) -> dict`

必填 `query_result`，可选 `chart_type`、`intent`、`field_mapping` 和 `max_points`。
返回 `{ "chart": ..., "warnings": [...] }`；图表字段包括 `type`、`title`、
`xField`、`yField`、`seriesField`、`data`、`encoding`、`truncated` 和 `max_points`。
默认最多保留 100 行，超出时返回 `CHART_DATA_TRUNCATED` 警告。类型缺省时按列数和
首列日期/时间类型推断，属于简单启发式。
