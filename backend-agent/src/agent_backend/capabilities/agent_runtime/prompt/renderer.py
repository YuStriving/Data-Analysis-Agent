from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from agent_backend.capabilities.agent_runtime.prompt.contracts import (
    PromptRenderRequest,
    PromptRenderResult,
    PromptTemplate,
)
from agent_backend.capabilities.agent_runtime.prompt.exceptions import (
    MissingPromptVariablesError,
    UndeclaredPromptVariablesError,
)


PLACEHOLDER_PATTERN = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


class PromptRenderer:
    def render(
        self,
        template: PromptTemplate,
        request: PromptRenderRequest,
    ) -> PromptRenderResult:
        self._validate_declared_placeholders(template)
        missing_variables = [
            variable
            for variable in template.required_variables
            if variable not in request.variables or request.variables[variable] is None
        ]
        if missing_variables:
            raise MissingPromptVariablesError(
                request.agent_id,
                request.node_id,
                template.template_id,
                template.version,
                missing_variables,
            )

        variables_snapshot = self._build_variables_snapshot(template, request.variables)
        rendered_text = PLACEHOLDER_PATTERN.sub(
            lambda match: self._format_variable(variables_snapshot.get(match.group(1))),
            template.body,
        )
        rendered_hash = hashlib.sha256(rendered_text.encode("utf-8")).hexdigest()

        return PromptRenderResult(
            agent_id=request.agent_id,
            node_id=request.node_id,
            template_id=template.template_id,
            template_version=template.version,
            output_contract=template.output_contract,
            rendered_text=rendered_text,
            rendered_hash=rendered_hash,
            variables_snapshot=variables_snapshot,
        )

    def _validate_declared_placeholders(self, template: PromptTemplate) -> None:
        declared = set(template.required_variables).union(template.optional_variables)
        referenced = set(PLACEHOLDER_PATTERN.findall(template.body))
        undeclared = sorted(referenced.difference(declared))
        if undeclared:
            raise UndeclaredPromptVariablesError(template.template_id, undeclared)

    def _build_variables_snapshot(
        self,
        template: PromptTemplate,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        snapshot: dict[str, Any] = {}
        for variable in template.required_variables:
            snapshot[variable] = variables[variable]
        for variable in template.optional_variables:
            snapshot[variable] = variables.get(variable)
        return snapshot

    def _format_variable(self, value: Any) -> str:
        if value is None:
            return "无"
        if isinstance(value, str):
            return value if value else "无"
        if isinstance(value, (list, dict)):
            if not value:
                return "[]" if isinstance(value, list) else "{}"
            return json.dumps(value, ensure_ascii=False, indent=2)
        return str(value)
