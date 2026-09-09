from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from agent_backend.capabilities.agent_runtime.memory.contracts import (
    AnswerGeneratedPayload,
    ChartBuiltPayload,
    FlushResult,
    MemoryEvent,
    MemoryScope,
    MemoryTurn,
    PendingMemoryItem,
    QuestionReceivedPayload,
    QueryExecutedPayload,
    ResultSummarizedPayload,
    SqlGeneratedPayload,
    SqlRepairedPayload,
)
from agent_backend.capabilities.agent_runtime.memory.protocols import (
    DurableMemoryStore,
    PendingMemoryStore,
    build_scope_key,
)


class MemoryService:
    def __init__(
        self,
        *,
        redis_store: PendingMemoryStore,
        mongo_store: DurableMemoryStore,
        flush_lock_ttl_seconds: int = 60,
        flush_batch_size: int = 500,
        recent_turn_limit: int = 6,
    ) -> None:
        self.redis_store = redis_store
        self.mongo_store = mongo_store
        self.flush_lock_ttl_seconds = flush_lock_ttl_seconds
        self.flush_batch_size = flush_batch_size
        self.recent_turn_limit = recent_turn_limit

    def record_turn(self, turn: MemoryTurn) -> PendingMemoryItem:
        scope = turn.scope
        scope_key = scope.to_key()
        pending_seq = self.redis_store.next_pending_seq(scope_key)
        item = PendingMemoryItem.from_turn(turn, pending_seq=pending_seq)
        self.redis_store.enqueue_item(item)
        self._merge_hot_context(
            scope_key,
            {
                "last_task_id": turn.task_id,
                "last_turn_id": turn.turn_id,
                "last_role": turn.role,
                "last_content": turn.content,
                "pending_seq": str(pending_seq),
            },
        )
        self._append_recent_turn(scope_key, turn)
        return item

    def record_event(self, event: MemoryEvent) -> PendingMemoryItem:
        scope_key = event.scope.to_key()
        pending_seq = self.redis_store.next_pending_seq(scope_key)
        item = PendingMemoryItem.from_event(event, pending_seq=pending_seq)
        self.redis_store.enqueue_item(item)
        hot_context_patch = self._hot_context_patch_for_event(event)
        hot_context_patch["pending_seq"] = str(pending_seq)
        self._merge_hot_context(scope_key, hot_context_patch)
        return item

    # Backward-compatible wrapper for early tests/callers.
    def enqueue_turn(self, item: PendingMemoryItem) -> None:
        self.redis_store.enqueue_item(item)
        if item.item_type == "turn":
            self._merge_hot_context(
                item.scope_key,
                {
                    "last_task_id": item.turn.task_id,
                    "last_turn_id": item.turn.turn_id,
                    "last_role": item.turn.role,
                    "last_content": item.turn.content,
                    "pending_seq": str(item.pending_seq),
                },
            )
            self._append_recent_turn(item.scope_key, item.turn)

    def load_hot_context(self, scope_key: str) -> dict[str, Any]:
        return self.redis_store.load_hot_context(scope_key)

    def flush_pending(self, scope: MemoryScope | str) -> FlushResult:
        scope_key = scope if isinstance(scope, str) else scope.to_key()
        if not self.redis_store.acquire_flush_lock(scope_key, self.flush_lock_ttl_seconds):
            return FlushResult(scope_key=scope_key, status="locked")

        try:
            raw_items = self.redis_store.list_pending_raw(scope_key, self.flush_batch_size)
            if not raw_items:
                return FlushResult(scope_key=scope_key, status="empty")

            pending_items: list[PendingMemoryItem] = []
            dead_letter_count = 0
            for raw_item in raw_items:
                try:
                    pending_items.append(PendingMemoryItem.model_validate(json.loads(raw_item)))
                except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                    self.redis_store.move_to_dead_letter(scope_key, raw_item, str(exc))
                    dead_letter_count += 1

            pending_items.sort(key=lambda item: item.pending_seq)
            turns = [item.turn for item in pending_items if item.item_type == "turn"]
            events = [item.event for item in pending_items if item.item_type == "event"]

            try:
                if turns:
                    self.mongo_store.save_turns(turns)
                if events:
                    self.mongo_store.save_events(events)
            except Exception as exc:
                return FlushResult(
                    scope_key=scope_key,
                    status="failed",
                    read_count=len(raw_items),
                    flushed_turn_count=0,
                    flushed_event_count=0,
                    dead_letter_count=dead_letter_count,
                    error_message=str(exc),
                )

            self.redis_store.trim_pending(scope_key, len(raw_items))
            return FlushResult(
                scope_key=scope_key,
                status="partial_invalid" if dead_letter_count else "flushed",
                read_count=len(raw_items),
                flushed_turn_count=len(turns),
                flushed_event_count=len(events),
                dead_letter_count=dead_letter_count,
            )
        finally:
            self.redis_store.release_flush_lock(scope_key)

    @staticmethod
    def scope_key_for(turn: MemoryTurn) -> str:
        return build_scope_key(turn.tenant_id, turn.user_id, turn.session_id)

    @staticmethod
    def scope_key_from_parts(tenant_id: str, user_id: str, session_id: str) -> str:
        return build_scope_key(tenant_id, user_id, session_id)

    def _merge_hot_context(self, scope_key: str, patch: dict[str, Any]) -> None:
        hot_context = self.redis_store.load_hot_context(scope_key)
        hot_context.update({key: value for key, value in patch.items() if value is not None})
        self.redis_store.save_hot_context(scope_key, hot_context)

    def _append_recent_turn(self, scope_key: str, turn: MemoryTurn) -> None:
        hot_context = self.redis_store.load_hot_context(scope_key)
        recent_turns = list(hot_context.get("recent_turns", []))
        recent_turns.append(
            {
                "task_id": turn.task_id,
                "role": turn.role,
                "content": turn.content,
                "created_at": turn.created_at.isoformat(),
            }
        )
        hot_context["recent_turns"] = recent_turns[-self.recent_turn_limit :]
        self.redis_store.save_hot_context(scope_key, hot_context)

    def _hot_context_patch_for_event(self, event: MemoryEvent) -> dict[str, Any]:
        payload = event.payload
        patch: dict[str, Any] = {"last_task_id": event.task_id, "last_event_id": event.event_id}
        if isinstance(payload, QuestionReceivedPayload):
            patch["last_question"] = payload.question
            patch["selected_dataset_id"] = payload.selected_dataset_id
        elif isinstance(payload, SqlGeneratedPayload):
            patch["last_sql"] = payload.sql
            patch["selected_dataset_id"] = payload.selected_dataset_id
        elif isinstance(payload, SqlRepairedPayload):
            patch["last_sql"] = payload.repaired_sql
            if payload.lesson:
                hot_context = self.redis_store.load_hot_context(event.scope.to_key())
                lessons = list(hot_context.get("repair_lessons", []))
                lessons.append(payload.lesson)
                patch["repair_lessons"] = lessons[-self.recent_turn_limit :]
        elif isinstance(payload, QueryExecutedPayload):
            patch["last_result_ref"] = payload.result_ref
        elif isinstance(payload, ResultSummarizedPayload):
            patch["last_result_summary"] = payload.summary
            patch["last_result_ref"] = payload.result_ref
        elif isinstance(payload, ChartBuiltPayload):
            patch["last_chart_summary"] = payload.model_dump(mode="json", exclude={"type"})
        elif isinstance(payload, AnswerGeneratedPayload):
            patch["last_answer"] = payload.answer
            patch["last_result_ref"] = payload.result_ref
            patch["last_chart_ref"] = payload.chart_ref
        return patch
