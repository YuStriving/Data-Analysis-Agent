from __future__ import annotations

from typing import Any

from jsonschema import ValidationError, validate

from agent_backend.agent_runtime.tool_calling.errors import ToolCallError


def validate_value(schema: dict[str, Any], value: Any, reason: str) -> None:
    if not schema:
        return
    try:
        validate(instance=value, schema=schema)
    except ValidationError as exc:
        path = ".".join(str(part) for part in exc.path)
        detail = {"path": path, "validator": exc.validator}
        raise ToolCallError(reason, exc.message, detail=detail) from exc
