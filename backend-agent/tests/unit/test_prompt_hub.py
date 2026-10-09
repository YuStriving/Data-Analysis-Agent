from pathlib import Path

import pytest

from agent_backend.agent_runtime.prompt import (
    MissingPromptVariablesError,
    PromptRenderRequest,
    render_prompt,
    render_system_prompt,
)
from agent_backend.agent_runtime.prompt.exceptions import (
    DuplicateActivePromptTemplateError,
    PromptTemplateFormatError,
    PromptTemplateNotFoundError,
)
from agent_backend.agent_runtime.prompt.loader import load_prompt_template
from agent_backend.agent_runtime.prompt.registry import PromptRegistry
from agent_backend.capabilities.data_analysis.prompting.failures import (
    map_prompt_error_to_user_failure,
)


def test_render_system_prompt_loads_active_system_template() -> None:
    result = render_system_prompt("data_analysis_agent")

    assert result.template_id == "data_analysis.system.base"
    assert result.template_version == "v1"
    assert result.output_contract == "system_prompt_v1"
    assert len(result.rendered_hash) == 64
    assert "{{" not in result.rendered_text
    assert "全局规则" in result.rendered_text


def test_prompt_hub_no_longer_loads_node_prompts() -> None:
    with pytest.raises(PromptTemplateNotFoundError):
        render_prompt(
            PromptRenderRequest(
                agent_id="data_analysis_agent",
                node_id="generate_sql",
                variables={},
            )
        )


def test_prompt_error_maps_to_user_facing_failure() -> None:
    error = MissingPromptVariablesError(
        agent_id="data_analysis_agent",
        node_id="generate_sql",
        template_id="data_analysis.generate_sql.base",
        template_version="v1",
        missing_variables=["schema_context"],
    )

    failure = map_prompt_error_to_user_failure(error)

    assert failure.code == "missing_schema_context"
    assert "表结构" in failure.message
    assert failure.retryable is True


def test_load_prompt_template_parses_front_matter() -> None:
    template = load_prompt_template(Path("agent_backend/capabilities/data_analysis/prompts/system/base.v1.md"))

    assert template.agent_id == "data_analysis_agent"
    assert template.node_id == "system"
    assert template.required_variables == []
    assert template.output_contract == "system_prompt_v1"


def test_registry_detects_duplicate_active_templates(tmp_path: Path) -> None:
    _write_template(tmp_path / "alpha" / "prompts" / "system" / "one.v1.md", "one")
    _write_template(tmp_path / "alpha" / "prompts" / "system" / "two.v1.md", "two")

    with pytest.raises(DuplicateActivePromptTemplateError):
        PromptRegistry(template_roots=[tmp_path])


def test_load_prompt_template_rejects_missing_front_matter(tmp_path: Path) -> None:
    path = tmp_path / "plain.md"
    path.write_text("plain prompt", encoding="utf-8")

    with pytest.raises(PromptTemplateFormatError):
        load_prompt_template(path)


def test_load_prompt_template_accepts_yaml_inline_lists(tmp_path: Path) -> None:
    path = tmp_path / "inline-list.v1.md"
    path.write_text(
        """---
template_id: data_analysis.generate_sql.inline
agent_id: data_analysis_agent
node_id: generate_sql
version: v1
status: active
description: Test inline YAML list.
required_variables: [user_question, dataset_context]
optional_variables: []
output_contract: generate_sql_result_v1
---

测试模板。
""",
        encoding="utf-8",
    )

    template = load_prompt_template(path)

    assert template.required_variables == ["user_question", "dataset_context"]
    assert template.optional_variables == []


def _write_template(path: Path, template_id_suffix: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
template_id: data_analysis.system.{template_id_suffix}
agent_id: data_analysis_agent
node_id: system
version: v1-{template_id_suffix}
status: active
description: Test template.
required_variables:
optional_variables:
output_contract: system_prompt_v1
---

测试模板。
""",
        encoding="utf-8",
    )
