import pytest

from agent_backend.capabilities.agent_runtime.context.contracts import (
    ContextBundle,
    ConversationContext,
    DatasetContext,
    PreviousTurnContext,
    RequestContext,
    SchemaContext,
)
from agent_backend.capabilities.agent_runtime.prompt import (
    MissingPromptInputSectionsError,
    build_prompt_request,
    render_prompt,
)
from agent_backend.foundation.access import AccessContext


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


def test_prompt_input_adapter_builds_generate_sql_request() -> None:
    request = build_prompt_request(
        agent_id="data_analysis_agent",
        node_id="generate_sql",
        bundle=make_generate_sql_bundle(),
    )

    assert request.agent_id == "data_analysis_agent"
    assert request.node_id == "generate_sql"
    assert request.variables["user_question"] == "Show monthly revenue trend"
    assert request.variables["dataset_context"]["selected_dataset_id"] == "dataset-sales"
    assert request.variables["schema_context"]["schema_summary"].startswith("orders.")
    assert request.variables["access_context"]["allowed_dataset_ids"] == ["dataset-sales"]
    assert request.variables["access_context"]["readonly"] is True
    assert request.variables["metric_context"] == {"revenue": "sum(orders.amount)"}
    assert request.variables["time_context"] == {"orders": "order_date"}
    assert request.variables["recent_context"]["previous_turn"]["last_question"] == "Show revenue"


def test_prompt_input_adapter_result_renders_generate_sql_prompt() -> None:
    prompt_request = build_prompt_request(
        agent_id="data_analysis_agent",
        node_id="generate_sql",
        bundle=make_generate_sql_bundle(),
    )

    result = render_prompt(prompt_request)

    assert result.template_id == "data_analysis.generate_sql.base"
    assert result.output_contract == "generate_sql_result_v1"
    assert "{{" not in result.rendered_text
    assert "权限约束" in result.rendered_text


def test_prompt_input_adapter_requires_access_context() -> None:
    bundle = make_generate_sql_bundle()
    bundle.access_context = None

    with pytest.raises(MissingPromptInputSectionsError) as exc_info:
        build_prompt_request(
            agent_id="data_analysis_agent",
            node_id="generate_sql",
            bundle=bundle,
        )

    assert exc_info.value.missing_sections == ["access"]
