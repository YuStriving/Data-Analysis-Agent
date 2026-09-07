from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import TextIO

from agent_backend.capabilities.agent_runtime.observability.events import AlertRecord


def build_daily_alert_path(base_dir: str | Path, day: date) -> Path:
    return Path(base_dir) / f"{day.isoformat()}.log"


def write_alert_record(record: AlertRecord, sink: TextIO) -> None:
    sink.write(record.model_dump_json())
    sink.write("\n")
    sink.flush()


def append_daily_alert(base_dir: str | Path, record: AlertRecord) -> Path:
    path = build_daily_alert_path(base_dir, date.fromisoformat(record.timestamp[:10]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as sink:
        write_alert_record(record, sink)
    return path
