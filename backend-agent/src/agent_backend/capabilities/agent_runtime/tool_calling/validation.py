from __future__ import annotations

from typing import Any

from jsonschema import ValidationError, validate

from agent_backend.capabilities.agent_runtime.tool_calling.contracts import ToolErrorCode
from agent_backend.capabilities.agent_runtime.tool_calling.errors import ToolCallingException


def validate_value(schema: dict[str, Any], value: Any, error_code: ToolErrorCode) -> None:
    if not schema:
        return
    try:
        validate(instance=value, schema=schema)
    except ValidationError as exc:
        path = ".".join(str(part) for part in exc.path)
        detail = {"path": path, "validator": exc.validator}
        raise ToolCallingException(error_code, exc.message, detail=detail) from exc
