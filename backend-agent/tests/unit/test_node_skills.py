from pathlib import Path

import pytest

from agent_backend.capabilities.agent_runtime.skills import (
    MissingSkillContextError,
    NodeSkillFormatError,
    NodeSkillNotFoundError,
    SkillInputAdapter,
    load_node_skill,
    render_node_skill,
)
from agent_backend.foundation.access import AccessContext
from agent_backend.foundation.contracts.context import (
    ContextBundle,
    ConversationContext,
    DatasetContext,
    PreviousTurnContext,
    RequestContext,
    SchemaContext,
)


def make_generate_sql_bundle() -> ContextBundle:
    return ContextBundle(
        request=RequestContext(
            question="Show monthly revenue trend",
            task_type="trend_analysis",
        ),
        access=AccessContext(
            tenant_id="tenant-1",
            user_id="user-1",
            allowed_dataset_ids=["dataset-sales"],
            readonly=True,
        ),
        dataset=DatasetContext(
            available_dataset_ids=["dataset-sales"],
            selected_dataset_id="dataset-sales",
        ),
        schema=SchemaContext(
            schema_summary="orders.order_date date, orders.amount decimal",
            metric_mapping={"revenue": "sum(orders.amount)"},
            time_field_hints={"orders": "order_date"},
        ),
        conversation=ConversationContext(
            conversation_summary="User often asks for monthly revenue.",
            confirmed_facts=["dataset-sales is authorized"],
        ),
        previous_turn=PreviousTurnContext(
            last_question="Show revenue",
            last_sql="select sum(amount) from orders",
            last_selected_dataset_id="dataset-sales",
        ),
    )


def test_load_node_skill_parses_front_matter() -> None:
    skill = load_node_skill(
        Path("src/agent_backend/capabilities/data_analysis/skills/generate_sql/base.v1.md")
    )

    assert skill.skill_id == "data_analysis.generate_sql"
    assert skill.agent_id == "data_analysis_agent"
    assert skill.nodes == ["generate_sql"]
    assert skill.required_context == ["request", "dataset", "schema", "access"]
    assert skill.output_contract == "generate_sql_result_v1"
    assert skill.response_format == "json_object"


@pytest.mark.parametrize(
    ("node_id", "skill_id", "output_contract"),
    [
        ("generate_sql", "data_analysis.generate_sql", "generate_sql_result_v1"),
        ("repair_sql", "data_analysis.repair_sql", "repair_sql_result_v1"),
        ("interpret_result", "data_analysis.interpret_result", "interpret_result_v1"),
        ("build_chart", "data_analysis.build_chart", "build_chart_result_v1"),
    ],
)
def test_static_node_skill_bindings_load_expected_contracts(
    node_id: str,
    skill_id: str,
    output_contract: str,
) -> None:
    request = SkillInputAdapter().build_skill_request(
        agent_id="data_analysis_agent",
        node_id=node_id,
        bundle=make_generate_sql_bundle(),
    )

    skill = load_node_skill(request.skill_path)

    assert skill.skill_id == skill_id
    assert skill.output_contract == output_contract
    assert skill.response_format == "json_object"


def test_load_node_skill_rejects_missing_required_metadata(tmp_path: Path) -> None:
    path = tmp_path / "bad-skill.md"
    path.write_text(
        """---
skill_id: data_analysis.bad
agent_id: data_analysis_agent
nodes:
  - generate_sql
version: v1
status: active
description: Bad skill.
required_context: []
optional_context: []
output_contract: generate_sql_result_v1
---

body
""",
        encoding="utf-8",
    )

    with pytest.raises(NodeSkillFormatError, match="response_format"):
        load_node_skill(path)


def test_render_node_skill_requires_required_context() -> None:
    bundle = make_generate_sql_bundle()
    bundle.schema_context = None
    request = SkillInputAdapter().build_skill_request(
        agent_id="data_analysis_agent",
        node_id="generate_sql",
        bundle=bundle,
    )

    with pytest.raises(MissingSkillContextError) as exc_info:
        render_node_skill(request)

    assert exc_info.value.missing_sections == ["schema"]


def test_skill_input_adapter_rejects_missing_static_binding() -> None:
    with pytest.raises(NodeSkillNotFoundError):
        SkillInputAdapter().build_skill_request(
            agent_id="data_analysis_agent",
            node_id="missing_node",
            bundle=make_generate_sql_bundle(),
        )


def test_render_node_skill_allows_missing_optional_context() -> None:
    bundle = make_generate_sql_bundle()
    bundle.conversation = None
    bundle.previous_turn = None
    request = SkillInputAdapter().build_skill_request(
        agent_id="data_analysis_agent",
        node_id="generate_sql",
        bundle=bundle,
    )

    result = render_node_skill(request)

    assert result.skill_id == "data_analysis.generate_sql"
    assert result.context_snapshot["conversation"] is None
    assert "对话上下文" in result.rendered_text
    assert "无" in result.rendered_text
