from fastapi import FastAPI

from agent_backend.foundation.contracts.task import AnalysisTaskRequest

app = FastAPI(title="Agent API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "agent-api"}


@app.post("/internal/tasks")
def create_task(request: AnalysisTaskRequest) -> dict[str, str]:
    return {
        "task_id": request.task_id,
        "trace_id": request.trace_id,
        "status": "accepted",
    }

