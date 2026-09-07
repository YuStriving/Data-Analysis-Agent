from pydantic import BaseModel


EVENT_TYPE_ALERT = "alert"
EVENT_TYPE_CHECKPOINT = "checkpoint"


class StreamEvent(BaseModel):
    task_id: str
    trace_id: str
    event_type: str
    timestamp: str
    message: str | None = None


class AlertEvent(StreamEvent):
    event_type: str = EVENT_TYPE_ALERT
    level: str = "error"


class AlertRecord(AlertEvent):
    pass


class CheckpointEvent(StreamEvent):
    event_type: str = EVENT_TYPE_CHECKPOINT
    snapshot_id: str
    node_id: str

