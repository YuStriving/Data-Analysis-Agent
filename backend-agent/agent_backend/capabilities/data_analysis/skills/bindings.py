from __future__ import annotations

from pathlib import Path

from agent_backend.agent_runtime.skills.exceptions import NodeSkillNotFoundError

_DATA_ANALYSIS_AGENT_ID = "data_analysis_agent"
_STATIC_SKILL_BINDINGS: dict[tuple[str, str], Path] = {
    (_DATA_ANALYSIS_AGENT_ID, "generate_sql"): Path("skills/generate_sql/base.v1.md"),
    (_DATA_ANALYSIS_AGENT_ID, "repair_sql"): Path("skills/repair_sql/base.v1.md"),
    (_DATA_ANALYSIS_AGENT_ID, "interpret_result"): Path("skills/interpret_result/base.v1.md"),
    (_DATA_ANALYSIS_AGENT_ID, "build_chart"): Path("skills/build_chart/base.v1.md"),
}


def resolve_node_skill_path(agent_id: str, node_id: str) -> Path:
    try:
        relative_path = _STATIC_SKILL_BINDINGS[(agent_id, node_id)]
    except KeyError as exc:
        raise NodeSkillNotFoundError(agent_id, node_id) from exc
    return _default_capabilities_root() / relative_path


def _default_capabilities_root() -> Path:
    return Path(__file__).resolve().parents[1]
