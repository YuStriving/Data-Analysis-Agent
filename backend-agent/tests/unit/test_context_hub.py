from context_hub.builder import build_context
from shared_models.memory import NodeCheckpointSnapshot
from shared_models.task import AnalysisTaskRequest


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
