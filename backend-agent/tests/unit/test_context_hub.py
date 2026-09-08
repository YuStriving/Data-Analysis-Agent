from agent_backend.capabilities.agent_runtime.context.builder import build_context
from agent_backend.capabilities.agent_runtime.context.builder import ContextBuilder
from agent_backend.capabilities.agent_runtime.context.policies import resolve_context_policy
from agent_backend.foundation.contracts.context import (
    ContextIdentity,
    ContextSource,
    DatasetContext,
    ExecutionResultContext,
    RepairContext,
    RequestContext,
    SchemaContext,
)
from agent_backend.foundation.contracts.memory import NodeCheckpointSnapshot
from agent_backend.foundation.contracts.task import AnalysisTaskRequest


def test_build_context_uses_trend_policy() -> None:
    bundle = build_context(
        request=AnalysisTaskRequest(
            task_id="task-1",
            trace_id="trace-1",
            tenant_id="tenant-1",
            user_id="user-1",
            question="Show monthly revenue trend",
            dataset_ids=["dataset-sales"],
        )
    )

    assert bundle["task_type"] == "trend_analysis"
    assert bundle["injection_strategy"] == "trend_bundle"
    assert bundle["dataset_ids"] == ["dataset-sales"]


def test_build_context_uses_checkpoint_first_policy_for_resume() -> None:
    bundle = build_context(
        request=AnalysisTaskRequest(
            task_id="task-1",
            trace_id="trace-1",
            tenant_id="tenant-1",
            user_id="user-1",
            question="Resume the previous task",
            dataset_ids=["dataset-sales"],
        ),
        snapshot=NodeCheckpointSnapshot.demo(),
    )

    assert bundle["task_type"] == "resume_recovery"
    assert bundle["injection_strategy"] == "checkpoint_first"
    assert bundle["hot_context"]["question"] == "Show revenue trend"
    assert "last_stable_checkpoint" not in bundle


def test_context_builder_returns_missing_required_context() -> None:
    source = ContextSource(
        identity=ContextIdentity(
            task_id="task-1",
            trace_id="trace-1",
            tenant_id="tenant-1",
            user_id="user-1",
            session_id="session-1",
        ),
        request=RequestContext(question="Show monthly revenue trend", task_type="trend_analysis"),
        dataset=DatasetContext(available_dataset_ids=["dataset-sales"]),
    )
    policy = resolve_context_policy("data_analysis_agent", "generate_sql")

    result = ContextBuilder().build(source, policy)

    assert result.status == "missing_required_context"
    assert result.bundle is None
    assert result.missing_sections == ["dataset", "schema"]


def test_context_builder_applies_generate_sql_v2_policy() -> None:
    source = ContextSource(
        identity=ContextIdentity(
            task_id="task-1",
            trace_id="trace-1",
            tenant_id="tenant-1",
            user_id="user-1",
            session_id="session-1",
        ),
        request=RequestContext(question="Show monthly revenue trend", task_type="trend_analysis"),
        dataset=DatasetContext(
            available_dataset_ids=["dataset-sales"],
            selected_dataset_id="dataset-sales",
        ),
        schema=SchemaContext(schema_summary="orders.amount decimal, sales amount"),
        execution_result=ExecutionResultContext(executed_sql="select 1", result_summary="one row"),
    )
    policy = resolve_context_policy("data_analysis_agent", "generate_sql")

    result = ContextBuilder().build(source, policy)

    assert result.status == "ok"
    assert result.bundle is not None
    assert result.bundle.identity is not None
    assert result.bundle.identity.session_id == "session-1"
    assert result.bundle.execution_result is None
    assert result.bundle.runtime is not None
    assert result.bundle.runtime.policy_name == "generate_sql_v2"
    assert result.bundle.meta is not None
    assert "schema" in result.bundle.meta.included_sections


def test_context_builder_truncates_schema_by_policy_limit() -> None:
    source = ContextSource(
        identity=ContextIdentity(
            task_id="task-1",
            trace_id="trace-1",
            tenant_id="tenant-1",
            user_id="user-1",
            session_id="session-1",
        ),
        request=RequestContext(question="Show monthly revenue trend", task_type="trend_analysis"),
        dataset=DatasetContext(
            available_dataset_ids=["dataset-sales"],
            selected_dataset_id="dataset-sales",
        ),
        schema=SchemaContext(schema_summary="x" * 5000),
    )
    policy = resolve_context_policy("data_analysis_agent", "generate_sql")

    result = ContextBuilder().build(source, policy)

    assert result.bundle is not None
    assert result.bundle.schema_context is not None
    assert len(result.bundle.schema_context.schema_summary) == 4000
    assert result.bundle.schema_context.truncated is True
    assert result.bundle.meta is not None
    assert result.bundle.meta.truncated_sections == ["schema"]


def test_context_builder_requires_repair_context_for_repair_sql() -> None:
    source = ContextSource(
        identity=ContextIdentity(
            task_id="task-1",
            trace_id="trace-1",
            tenant_id="tenant-1",
            user_id="user-1",
            session_id="session-1",
        ),
        request=RequestContext(question="Fix the SQL", task_type="unknown"),
        dataset=DatasetContext(
            available_dataset_ids=["dataset-sales"],
            selected_dataset_id="dataset-sales",
        ),
        schema=SchemaContext(schema_summary="orders.amount decimal"),
        repair=RepairContext(failed_sql="select bad from orders"),
    )
    policy = resolve_context_policy("data_analysis_agent", "repair_sql")

    result = ContextBuilder().build(source, policy)

    assert result.status == "missing_required_context"
    assert result.missing_sections == ["repair"]
