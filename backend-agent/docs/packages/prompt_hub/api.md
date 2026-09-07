# Python Prompt Hub 接口文档

## 1. 当前公开内容

### `SYSTEM_PROMPT`

当前值：

```text
You are a read-only enterprise data analysis agent.
Follow tool constraints, preserve traceability, and do not fabricate metrics.
```

## 2. 建议公开函数

### `get_system_prompt() -> str`

### `get_prompt_bundle(task_type: str, context: dict) -> dict`

返回示例：

```json
{
  "system": "You are a read-only enterprise data analysis agent.",
  "planner": "Break the question into analysis steps.",
  "analyst": "Generate read-only SQL only.",
  "reviewer": "Escalate when risk is high."
}
```

## 3. Prompt 来源

1. `src/agent_backend/capabilities/data_analysis/prompts/system/base.md`
2. `src/agent_backend/capabilities/data_analysis/prompts/planner/analysis-planner.md`
3. `src/agent_backend/capabilities/data_analysis/prompts/analyst/sql-analyst.md`
4. `src/agent_backend/capabilities/data_analysis/prompts/reviewer/human-review.md`
