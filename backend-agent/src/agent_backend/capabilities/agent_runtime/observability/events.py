from pydantic import BaseModel, Field


EVENT_TYPE_ALERT = "alert"
EVENT_TYPE_CHECKPOINT = "checkpoint"
EVENT_TYPE_TOOL_CALL_STARTED = "tool_call_started"
EVENT_TYPE_TOOL_CALL_FINISHED = "tool_call_finished"


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


class ToolCallStartedEvent(StreamEvent):
    event_type: str = EVENT_TYPE_TOOL_CALL_STARTED
    tool_call_id: str
    tool_name: str
    tool_version: str
    agent_name: str
    agent_version: str
    node_id: str | None = None
    session_id: str
    tenant_id: str
    user_id: str
    dataset_id: str | None = None
    dataset_type: str | None = None
    timeout_ms: int
    args_hash: str
    input_summary: dict = Field(default_factory=dict)


class ToolCallFinishedEvent(StreamEvent):
    event_type: str = EVENT_TYPE_TOOL_CALL_FINISHED
    tool_call_id: str
    tool_name: str
    tool_version: str
    agent_name: str
    agent_version: str
    node_id: str | None = None
    session_id: str
    tenant_id: str
    user_id: str
    dataset_id: str | None = None
    dataset_type: str | None = None
    latency_ms: int | None = None
    success: bool
    status: str
    error_code: str | None = None
    error_message: str | None = None
    error_detail: dict | None = None
    retryable: bool = False
    attempt: int = 1
    max_attempts: int = 1
    truncated: bool | None = None
    row_count: int | None = None
    output_summary: dict | None = None

