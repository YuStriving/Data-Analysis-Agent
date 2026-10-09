from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel

from agent_backend.agent_runtime.skills.contracts import NodeSkill
from agent_backend.agent_runtime.skills.exceptions import MissingSkillContextError
from agent_backend.capabilities.data_analysis.contracts.context import ContextBundle
from agent_backend.capabilities.data_analysis.skills.contracts import (
    SkillRenderRequest,
    SkillRenderResult,
)

SECTION_ATTRS = {
    "identity": "identity",
    "request": "request",
    "access": "access_context",
    "dataset": "dataset",
    "schema": "schema_context",
    "conversation": "conversation",
    "previous_turn": "previous_turn",
    "repair": "repair",
    "execution_result": "execution_result",
    "chart": "chart",
    "runtime": "runtime",
    "meta": "meta",
}

SECTION_LABELS = {
    "identity": "身份上下文",
    "request": "用户请求",
    "access": "权限约束",
    "dataset": "当前数据集",
    "schema": "可用表结构",
    "conversation": "对话上下文",
    "previous_turn": "上一轮上下文",
    "repair": "修复上下文",
    "execution_result": "执行结果上下文",
    "chart": "图表上下文",
    "runtime": "运行时上下文",
    "meta": "上下文元信息",
}


class NodeSkillRenderer:
    def render(self, skill: NodeSkill, request: SkillRenderRequest) -> SkillRenderResult:
        self._validate_binding(skill, request)
        missing_sections = [
            section
            for section in skill.required_context
            if self._section_value(request.bundle, section) is None
        ]
        if missing_sections:
            raise MissingSkillContextError(
                request.agent_id,
                request.node_id,
                skill.skill_id,
                missing_sections,
            )

        context_snapshot = self._build_context_snapshot(skill, request.bundle)
        rendered_text = self._render_text(skill, context_snapshot)
        rendered_hash = hashlib.sha256(rendered_text.encode("utf-8")).hexdigest()

        return SkillRenderResult(
            agent_id=request.agent_id,
            node_id=request.node_id,
            skill_id=skill.skill_id,
            skill_version=skill.version,
            output_contract=skill.output_contract,
            response_format=skill.response_format,
            rendered_text=rendered_text,
            rendered_hash=rendered_hash,
            context_snapshot=context_snapshot,
        )

    def _validate_binding(self, skill: NodeSkill, request: SkillRenderRequest) -> None:
        if skill.agent_id != request.agent_id or request.node_id not in skill.nodes:
            raise MissingSkillContextError(
                request.agent_id,
                request.node_id,
                skill.skill_id,
                ["skill_binding"],
            )

    def _build_context_snapshot(
        self,
        skill: NodeSkill,
        bundle: ContextBundle,
    ) -> dict[str, Any]:
        snapshot: dict[str, Any] = {}
        for section in skill.required_context:
            snapshot[section] = self._serialize_section(self._section_value(bundle, section))
        for section in skill.optional_context:
            snapshot[section] = self._serialize_section(self._section_value(bundle, section))
        return snapshot

    def _section_value(self, bundle: ContextBundle, section: str) -> Any:
        attr = SECTION_ATTRS.get(section)
        if attr is None:
            return None
        return getattr(bundle, attr)

    def _serialize_section(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json", exclude_none=True)
        return value

    def _render_text(self, skill: NodeSkill, context_snapshot: dict[str, Any]) -> str:
        context_lines = ["输入上下文："]
        for section, value in context_snapshot.items():
            label = SECTION_LABELS.get(section, section)
            context_lines.append(f"- {label}（{section}）：{self._format_value(value)}")
        return f"{skill.body.strip()}\n\n" + "\n".join(context_lines)

    def _format_value(self, value: Any) -> str:
        if value is None:
            return "无"
        if isinstance(value, str):
            return value if value else "无"
        if isinstance(value, (list, dict)):
            if not value:
                return "[]" if isinstance(value, list) else "{}"
            return json.dumps(value, ensure_ascii=False, indent=2)
        return str(value)
