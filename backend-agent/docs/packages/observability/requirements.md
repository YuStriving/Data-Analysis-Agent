# Python Observability 模块需求

## 1. 模块定位

`observability` 只负责结构化事件与日志输出，不参与任务状态决策。告警接收方式为本地日志记录，不直接发送钉钉、企业微信或邮件。

## 2. 事件要求

1. 每个事件必须包含 `task_id`、`trace_id`、`event_type` 和 `timestamp`。
2. 告警事件使用 `event_type=alert`，并携带 `level` 和 `message`。
3. 节点快照事件使用 `event_type=checkpoint`，并携带 `snapshot_id` 与 `node_id`。
4. 事件模型保持稳定，日志落盘格式固定为 JSON line。

## 3. 日志要求

1. 告警日志按自然日分割，文件名为 `YYYY-MM-DD.log`。
2. 默认运行目录为 `runtime/logs/backend-agent/alerts/`。
3. 每个 `AlertRecord` 写入一行 JSON。
4. 日志目录不存在时自动创建。

## 4. 非职责

1. 不负责外部消息通知。
2. 不负责任务恢复决策。
3. 不负责业务审计表的持久化。

## 5. MVP 验收标准

1. `build_daily_alert_path` 能按日期生成文件路径。
2. `write_alert_record` 输出单行 JSON。
3. `append_daily_alert` 能自动建目录并追加日志。
4. `CheckpointEvent` 能携带快照和节点信息。
