from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_backend.capabilities.agent_runtime.prompt.contracts import PromptTemplate
from agent_backend.capabilities.agent_runtime.prompt.exceptions import PromptTemplateFormatError


REQUIRED_METADATA_KEYS = {
    "template_id",
    "agent_id",
    "node_id",
    "version",
    "status",
    "description",
    "required_variables",
    "optional_variables",
    "output_contract",
}


def has_front_matter(path: Path) -> bool:
    return path.read_text(encoding="utf-8-sig").lstrip().startswith("---")


def load_prompt_template(path: Path) -> PromptTemplate:
    text = path.read_text(encoding="utf-8-sig")
    metadata, body = _split_front_matter(text, path)
    parsed = _parse_front_matter(metadata, path)
    _validate_metadata(parsed, path)

    return PromptTemplate(
        template_id=str(parsed["template_id"]),
        agent_id=str(parsed["agent_id"]),
        node_id=str(parsed["node_id"]),
        version=str(parsed["version"]),
        status=str(parsed["status"]),  # type: ignore[arg-type]
        description=str(parsed["description"]),
        required_variables=list(parsed["required_variables"]),
        optional_variables=list(parsed["optional_variables"]),
        output_contract=str(parsed["output_contract"]),
        body=body.strip(),
        source_path=path,
    )


def _split_front_matter(text: str, path: Path) -> tuple[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise PromptTemplateFormatError("Prompt template must start with front matter", str(path))

    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break

    if end_index is None:
        raise PromptTemplateFormatError("Prompt template front matter is not closed", str(path))

    metadata = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :])
    if not body.strip():
        raise PromptTemplateFormatError("Prompt template body must not be empty", str(path))
    return metadata, body


def _parse_front_matter(metadata: str, path: Path) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    current_key: str | None = None

    for raw_line in metadata.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        stripped = line.strip()
        if stripped.startswith("- "):
            if current_key is None:
                raise PromptTemplateFormatError(
                    "Front matter list item has no parent key",
                    str(path),
                )
            parsed.setdefault(current_key, []).append(_strip_quotes(stripped[2:].strip()))
            continue

        if ":" not in line:
            raise PromptTemplateFormatError(
                f"Invalid front matter line: {line}",
                str(path),
            )

        key, value = line.split(":", 1)
        current_key = key.strip()
        value = value.strip()
        parsed[current_key] = [] if value == "" else _strip_quotes(value)

    return parsed


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _validate_metadata(metadata: dict[str, Any], path: Path) -> None:
    missing_keys = sorted(REQUIRED_METADATA_KEYS.difference(metadata))
    if missing_keys:
        raise PromptTemplateFormatError(
            f"Prompt template is missing metadata keys: {missing_keys}",
            str(path),
        )

    for key in ("required_variables", "optional_variables"):
        if not isinstance(metadata[key], list):
            raise PromptTemplateFormatError(
                f"Prompt metadata {key} must be a list",
                str(path),
            )

    if metadata["status"] not in {"active", "inactive", "deprecated"}:
        raise PromptTemplateFormatError(
            "Prompt metadata status must be active, inactive, or deprecated",
            str(path),
        )
