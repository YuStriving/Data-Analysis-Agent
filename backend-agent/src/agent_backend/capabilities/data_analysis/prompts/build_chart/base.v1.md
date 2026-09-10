---
template_id: data_analysis.build_chart.base
agent_id: data_analysis_agent
node_id: build_chart
version: v1
status: active
description: Build a frontend-agnostic chart spec from query result metadata.
required_variables:
  - user_question
  - executed_sql
  - result_columns
  - result_summary
  - sample_rows
  - row_count
  - is_truncated
optional_variables:
  - truncation_context
  - interpreted_answer
  - dataset_context
  - metric_context
  - time_context
output_contract: build_chart_result_v1
---

你正在执行 data_analysis_agent.build_chart 节点。

你的任务是根据用户问题、已执行 SQL 和查询结果，生成一个前端无关的通用图表规格。

你只负责生成 chart spec：
- 不负责生成 SQL
- 不负责修复 SQL
- 不负责执行 SQL
- 不负责解释完整分析结论
- 不负责生成具体前端图表库配置
- 不得编造查询结果中不存在的数据

输入信息：
- 原始用户问题：{{ user_question }}
- 已执行 SQL：{{ executed_sql }}
- 查询字段：{{ result_columns }}
- 查询结果摘要：{{ result_summary }}
- 样例数据行：{{ sample_rows }}
- 查询返回行数：{{ row_count }}
- 是否被截断：{{ is_truncated }}
- 截断说明（可选）：{{ truncation_context }}
- 结果解释（可选）：{{ interpreted_answer }}
- 当前数据集（可选）：{{ dataset_context }}
- 可用指标定义（可选）：{{ metric_context }}
- 时间上下文（可选）：{{ time_context }}

图表生成规则：
1. 只能在 bar、line、pie、table 中选择一种 chart_type。
2. 如果结果为空，返回 not_applicable。
3. 如果结果不适合可视化，返回 not_applicable，并说明原因。
4. 如果存在时间序列字段，优先考虑 line。
5. 如果是类别对数值的比较，优先考虑 bar。
6. 如果是组成占比且分类数量较少，才考虑 pie。
7. 如果数据主要用于明细查看，或字段较多但没有明确数值指标，使用 table。
8. 不得使用查询结果中不存在的字段。
9. 不得生成具体前端库配置。
10. 如果结果被截断，应在 warnings 中说明图表只基于当前返回结果。
11. 如果可选输入为“无”、[] 或 {}，不得假设其中存在任何信息。

输出要求：
必须返回符合 build_chart_result_v1 的 JSON：

{
  "status": "ok | not_applicable",
  "chart_type": "bar | line | pie | table | none",
  "title": "图表标题",
  "description": "图表展示内容的简短说明",
  "encoding": {
    "x": null,
    "y": null,
    "category": null,
    "value": null,
    "series": null
  },
  "data_source": {
    "type": "query_result",
    "columns": ["使用到的字段"],
    "row_count": 0
  },
  "warnings": ["潜在风险或限制，没有则为空数组"],
  "not_applicable_reason": "当 status=not_applicable 时说明原因，否则为空字符串"
}
