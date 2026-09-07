from __future__ import annotations

import json
from datetime import date
from io import StringIO

from observability.events import EVENT_TYPE_CHECKPOINT, CheckpointEvent
from observability.logger import (
    AlertRecord,
    append_daily_alert,
    build_daily_alert_path,
    write_alert_record,
)


def test_daily_alert_path_is_bucketed_by_date(tmp_path) -> None:
    path = build_daily_alert_path(tmp_path, date(2026, 9, 7))
    assert path.name == "2026-09-07.log"


def test_write_alert_record_emits_json_line() -> None:
    sink = StringIO()
    record = AlertRecord(
        task_id="task-1",
        trace_id="trace-1",
        level="warning",
        message="flush retry limit reached",
        timestamp="2026-09-07T10:00:00+08:00",
    )

    write_alert_record(record, sink)

    payload = json.loads(sink.getvalue())
    assert payload["task_id"] == "task-1"
    assert payload["level"] == "warning"
    assert payload["message"] == "flush retry limit reached"


def test_append_daily_alert_creates_date_log(tmp_path) -> None:
    record = AlertRecord(
        task_id="task-1",
        trace_id="trace-1",
        level="error",
        message="mongo write failed",
        timestamp="2026-09-07T10:00:00+08:00",
    )

    path = append_daily_alert(tmp_path, record)

    assert path == tmp_path / "2026-09-07.log"
    assert json.loads(path.read_text(encoding="utf-8"))["message"] == "mongo write failed"


def test_checkpoint_event_carries_snapshot_id() -> None:
    event = CheckpointEvent(
        task_id="task-1",
        trace_id="trace-1",
        timestamp="2026-09-07T10:00:00+08:00",
        snapshot_id="snapshot-1",
        node_id="generate_sql",
    )
    assert event.event_type == EVENT_TYPE_CHECKPOINT
    assert event.snapshot_id == "snapshot-1"
    assert event.node_id == "generate_sql"
