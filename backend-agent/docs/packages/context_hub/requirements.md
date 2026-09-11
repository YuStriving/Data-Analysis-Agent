# Python Context Hub 模块需求

## 1. 模块定位

`context_hub` 负责判断当前任务类型，并按任务类型选择上下文注入策略，最终输出给模型提示层和编排层使用。

## 2. 当前能力

1. `classify_task` 根据问题关键词识别趋势、对比、分布等任务类型。
2. `build_context` 在传入 `agent_runtime.checkpoint` 的 `NodeCheckpointSnapshot` 时强制识别为 `resume_recovery`。
3. 恢复任务使用 `checkpoint_first` 注入策略。
4. 输出 `ContextInjectionBundle`，包含身份、数据集、热上下文、确认事实、会话摘要和版本。

## 3. 核心职责

1. 任务识别
2. 策略选择
3. 快照上下文注入
4. 输出紧凑且有权限边界的上下文字典

## 4. MVP 规则

1. 上下文必须包含 `task_id`、`trace_id`、`tenant_id`、`user_id`。
2. 生成或修复 SQL 前必须包含 Java 传入的 `access_context`。
3. `access_context.readonly` 必须为 `true`，且必须包含已授权数据集。
4. 普通任务优先使用 keyword 推断；恢复任务以快照为准。
5. `injection_strategy` 由 task type 映射，不允许自由拼接任意上下文。
6. 输出版本固定为 `v1` 并写入 `injected_context_version`。

## 5. 验收标准

1. `resume_recovery` 始终选择 `checkpoint_first`。
2. 趋势、对比、分布问题能映射到对应策略。
3. 快照中的热上下文、确认事实和会话摘要能进入 bundle。
4. 未知问题返回 `unknown / default_bundle`，不扩大数据范围。
