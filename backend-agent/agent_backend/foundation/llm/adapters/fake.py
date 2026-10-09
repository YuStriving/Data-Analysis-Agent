from __future__ import annotations

from collections.abc import Sequence

from agent_backend.foundation.llm.contracts import (
    LlmCompletionRequest,
    LlmCompletionResult,
    LlmUsage,
)


class FakeLlmClient:
    provider = "fake"

    def __init__(
        self,
        outputs: str | Sequence[str] = "",
        *,
        client_id: str = "fake",
        model_name: str = "fake-model",
        error: Exception | None = None,
    ) -> None:
        self.client_id = client_id
        self.model_name = model_name
        self.error = error
        self.requests: list[LlmCompletionRequest] = []
        self._repeat_output = outputs if isinstance(outputs, str) else None
        self._output_queue = [] if isinstance(outputs, str) else list(outputs)

    def complete(self, request: LlmCompletionRequest) -> LlmCompletionResult:
        self.requests.append(request)
        if self.error is not None:
            raise self.error

        if self._repeat_output is not None:
            content = self._repeat_output
        elif self._output_queue:
            content = self._output_queue.pop(0)
        else:
            content = ""

        return LlmCompletionResult(
            content=content,
            client_id=self.client_id,
            provider=self.provider,
            model_name=self.model_name,
            usage=LlmUsage(),
            latency_ms=0,
            finish_reason="stop",
        )
