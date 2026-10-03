from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agent_backend.capabilities.agent_runtime.tool_calling.contracts import (
    ToolExecutionContext,
)


class DatasetScope(BaseModel):
    model_config = {"extra": "forbid"}

    selected_dataset_id: str | None = None
    allowed_dataset_ids: list[str] = Field(default_factory=list)
    dataset_types: dict[str, str] = Field(default_factory=dict)
    normalized_relation_datasets: dict[str, str] = Field(default_factory=dict)

    def dataset_id_for_args(self, args: dict[str, Any]) -> str | None:
        dataset_id = args.get("dataset_id")
        if isinstance(dataset_id, str):
            return dataset_id
        relation_id = args.get("normalized_relation_id")
        if isinstance(relation_id, str):
            return self.normalized_relation_datasets.get(relation_id)
        return self.selected_dataset_id

    def dataset_type_for_id(self, dataset_id: str | None) -> str | None:
        return self.dataset_types.get(dataset_id) if dataset_id is not None else None


class DataAnalysisToolExecutionContext(ToolExecutionContext):
    dataset_scope: DatasetScope
