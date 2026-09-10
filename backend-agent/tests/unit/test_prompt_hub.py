from pathlib import Path

import pytest

from agent_backend.capabilities.agent_runtime.prompt import (
    MissingPromptVariablesError,
    PromptRenderRequest,
    map_prompt_error_to_user_failure,
    render_prompt,
)
from agent_backend.capabilities.agent_runtime.prompt.exceptions import (
    DuplicateActivePromptTemplateError,
    PromptTemplateFormatError,
)
from agent_backend.capabilities.agent_runtime.prompt.loader import load_prompt_template
from agent_backend.capabilities.agent_runtime.prompt.registry import PromptRegistry


def test_render_prompt_loads_active_generate_sql_template() -> None:
    result = render_prompt(
        PromptRenderRequest(
            agent_id="data_analysis_agent",
            node_id="generate_sql",
            variables={
                "user_question": "统计每月销售额",
                "dataset_context": {"selected_dataset_id": "dataset-sales"},
                "schema_context": {"orders": ["order_date", "amount"]},
                "access_context": {"allowed_tables": ["orders"]},
            },
        )
    )

    assert result.template_id == "data_analysis.generate_sql.base"
    assert result.template_version == "v1"
    assert result.output_contract == "generate_sql_result_v1"
    assert len(result.rendered_hash) == 64
    assert "{{" not in result.rendered_text
    assert "metric_context" in result.variables_snapshot
    assert "可用指标定义（可选）：无" in result.rendered_text


def test_render_prompt_raises_for_missing_required_variables() -> None:
    with pytest.raises(MissingPromptVariablesError) as exc_info:
        render_prompt(
            PromptRenderRequest(
                agent_id="data_analysis_agent",
                node_id="generate_sql",
                variables={
                    "user_question": "统计每月销售额",
                    "dataset_context": {"selected_dataset_id": "dataset-sales"},
                    "access_context": {"allowed_tables": ["orders"]},
                },
            )
        )

    assert exc_info.value.missing_variables == ["schema_context"]


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
    template = load_prompt_template(
        Path(
            "src/agent_backend/capabilities/data_analysis/prompts/build_chart/base.v1.md"
        )
    )

    assert template.agent_id == "data_analysis_agent"
    assert template.node_id == "build_chart"
    assert template.required_variables == [
        "user_question",
        "executed_sql",
        "result_columns",
        "result_summary",
        "sample_rows",
        "row_count",
        "is_truncated",
    ]
    assert template.output_contract == "build_chart_result_v1"


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
