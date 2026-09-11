from __future__ import annotations

from typing import Protocol

from agent_backend.capabilities.agent_runtime.checkpoint.contracts import NodeCheckpointSnapshot


class CheckpointStore(Protocol):
    def save_snapshot(self, snapshot: NodeCheckpointSnapshot) -> None: ...

    def get_snapshot(self, snapshot_id: str) -> NodeCheckpointSnapshot | None: ...

    def get_latest_stable_snapshot(
        self,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str,
        task_id: str,
    ) -> NodeCheckpointSnapshot | None: ...
