# Python Observability 接口文档

## 1. 事件常量

```python
EVENT_TYPE_ALERT = "alert"
EVENT_TYPE_CHECKPOINT = "checkpoint"
```

## 2. 事件模型

### `StreamEvent`

```python
class StreamEvent(BaseModel):
    task_id: str
    trace_id: str
    event_type: str
    timestamp: str
    message: str | None = None
```

### `AlertEvent` / `AlertRecord`

```python
class AlertEvent(StreamEvent):
    event_type: str = EVENT_TYPE_ALERT
    level: str = "error"

class AlertRecord(AlertEvent):
    pass
```

### `CheckpointEvent`

```python
class CheckpointEvent(StreamEvent):
    event_type: str = EVENT_TYPE_CHECKPOINT
    snapshot_id: str
    node_id: str
```

## 3. 日志函数

### `build_daily_alert_path(base_dir, day) -> Path`

返回 `base_dir / {YYYY-MM-DD}.log`。

### `write_alert_record(record, sink) -> None`

写入 `record.model_dump_json()` 并在行尾追加换行。

### `append_daily_alert(base_dir, record) -> Path`

根据 `record.timestamp` 的日期创建或追加对应日志文件，返回最终路径。

默认日志根目录建议：

```text
runtime/logs/backend-agent/alerts/
```
