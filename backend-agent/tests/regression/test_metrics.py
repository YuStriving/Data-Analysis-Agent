from agent_backend.capabilities.agent_runtime.evals.metrics import task_success_rate


def test_task_success_rate() -> None:
    assert task_success_rate(8, 10) == 0.8

