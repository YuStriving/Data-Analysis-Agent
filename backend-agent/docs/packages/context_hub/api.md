# Python Context Hub 接口文档

## 1. 公开函数

### `classify_task(request, snapshot=None) -> TaskProfile`

返回：

```json
{
  "task_type": "trend_analysis",
  "injection_strategy": "trend_bundle"
}
```

规则：

1. `snapshot` 存在时返回 `resume_recovery / checkpoint_first`。
2. 关键词命中顺序为对比、趋势、分布。
3. 未命中时返回 `unknown / default_bundle`。

### `build_context(request, snapshot=None) -> dict`

返回字段：

```json
{
  "task_type": "trend_analysis",
  "injection_strategy": "trend_bundle",
  "task_id": "task-1",
  "trace_id": "trace-1",
  "tenant_id": "tenant-1",
  "user_id": "user-1",
  "session_id": "session-1",
  "dataset_ids": ["dataset-sales"],
  "hot_context": {},
  "confirmed_facts": [],
  "conversation_summary": "",
  "injected_context_version": "v1"
}
```

`snapshot` 非空时，`hot_context`、`confirmed_facts`、`conversation_summary` 和版本从快照恢复。

## 2. 策略映射

1. `trend_analysis` -> `trend_bundle`
2. `comparison_analysis` -> `comparison_bundle`
3. `distribution_analysis` -> `distribution_bundle`
4. `resume_recovery` -> `checkpoint_first`
5. `unknown` -> `default_bundle`
