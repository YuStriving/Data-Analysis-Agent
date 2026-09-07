from __future__ import annotations

from shared_models.task import AnalysisTaskType


def resolve_injection_strategy(task_type: AnalysisTaskType) -> str:
    mapping = {
        "trend_analysis": "trend_bundle",
        "comparison_analysis": "comparison_bundle",
        "distribution_analysis": "distribution_bundle",
        "resume_recovery": "checkpoint_first",
        "unknown": "default_bundle",
    }
    return mapping[task_type]
