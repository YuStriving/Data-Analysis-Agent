from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agent_backend.agent_runtime.skills.contracts import NodeSkill
from agent_backend.agent_runtime.skills.exceptions import NodeSkillFormatError

REQUIRED_METADATA_KEYS = {
    "skill_id",
    "agent_id",
    "nodes",
    "version",
    "status",
    "description",
    "required_context",
    "optional_context",
    "output_contract",
    "response_format",
}


def load_node_skill(path: Path) -> NodeSkill:
    text = path.read_text(encoding="utf-8-sig")
    metadata, body = _split_front_matter(text, path)
    parsed = _parse_front_matter(metadata, path)
    _validate_metadata(parsed, path)

    return NodeSkill(
        skill_id=str(parsed["skill_id"]),
        agent_id=str(parsed["agent_id"]),
        nodes=[str(item) for item in parsed["nodes"]],
        version=str(parsed["version"]),
        status=str(parsed["status"]),  # type: ignore[arg-type]
        description=str(parsed["description"]),
        required_context=[str(item) for item in parsed["required_context"]],
        optional_context=[str(item) for item in parsed["optional_context"]],
        output_contract=str(parsed["output_contract"]),
        response_format=str(parsed["response_format"]),  # type: ignore[arg-type]
        body=body.strip(),
        source_path=path,
    )


def _split_front_matter(text: str, path: Path) -> tuple[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise NodeSkillFormatError("Node Skill must start with front matter", str(path))

    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break

    if end_index is None:
        raise NodeSkillFormatError("Node Skill front matter is not closed", str(path))

    metadata = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :])
    if not body.strip():
        raise NodeSkillFormatError("Node Skill body must not be empty", str(path))
    return metadata, body


def _parse_front_matter(metadata: str, path: Path) -> dict[str, Any]:
    try:
        parsed = yaml.safe_load(metadata) or {}
    except yaml.YAMLError as exc:
        raise NodeSkillFormatError(
            f"Invalid Node Skill front matter: {exc}",
            str(path),
        ) from exc
    if not isinstance(parsed, dict):
        raise NodeSkillFormatError("Node Skill front matter must be a mapping", str(path))
    for key in ("required_context", "optional_context"):
        if parsed.get(key) is None:
            parsed[key] = []
    return parsed


def _validate_metadata(metadata: dict[str, Any], path: Path) -> None:
    missing_keys = sorted(REQUIRED_METADATA_KEYS.difference(metadata))
    if missing_keys:
        raise NodeSkillFormatError(
            f"Node Skill is missing metadata keys: {missing_keys}",
            str(path),
        )

    for key in ("nodes", "required_context", "optional_context"):
        if not isinstance(metadata[key], list):
            raise NodeSkillFormatError(f"Node Skill metadata {key} must be a list", str(path))

    if metadata["status"] not in {"active", "inactive", "deprecated"}:
        raise NodeSkillFormatError(
            "Node Skill metadata status must be active, inactive, or deprecated",
            str(path),
        )

    if metadata["response_format"] not in {"text", "json_object"}:
        raise NodeSkillFormatError(
            "Node Skill metadata response_format must be text or json_object",
            str(path),
        )
