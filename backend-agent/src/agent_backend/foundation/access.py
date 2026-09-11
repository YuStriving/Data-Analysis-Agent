from __future__ import annotations

from pydantic import BaseModel, Field


class AccessContext(BaseModel):
    tenant_id: str = Field(..., description="Tenant scope resolved by Java")
    user_id: str = Field(..., description="User identifier resolved by Java")
    allowed_dataset_ids: list[str] = Field(
        default_factory=list,
        description="Dataset identifiers authorized for this task",
    )
    readonly: bool = Field(True, description="Whether the agent is limited to read-only operations")
