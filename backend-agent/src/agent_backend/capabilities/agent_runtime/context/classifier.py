from __future__ import annotations

from pydantic import BaseModel

from agent_backend.foundation.contracts.memory import NodeCheckpointSnapshot
from agent_backend.foundation.contracts.task import AnalysisTaskRequest, AnalysisTaskType


class TaskProfile(BaseModel):
    task_type: AnalysisTaskType
    injection_strategy: str


def classify_task(
    request: AnalysisTaskRequest,
    snapshot: NodeCheckpointSnapshot | None = None,
) -> TaskProfile:
    if snapshot is not None:
        return TaskProfile(task_type="resume_recovery", injection_strategy="checkpoint_first")

    question = request.question.lower()
    if any(keyword in question for keyword in ("compare", "vs", "versus")):
        return TaskProfile(task_type="comparison_analysis", injection_strategy="comparison_bundle")
    if any(keyword in question for keyword in ("trend", "monthly", "over time")):
        return TaskProfile(task_type="trend_analysis", injection_strategy="trend_bundle")
    if any(keyword in question for keyword in ("distribution", "spread", "bucket")):
        return TaskProfile(task_type="distribution_analysis", injection_strategy="distribution_bundle")
    return TaskProfile(task_type="unknown", injection_strategy="default_bundle")
