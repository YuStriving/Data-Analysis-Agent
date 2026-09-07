def task_success_rate(succeeded: int, total: int) -> float:
    if total == 0:
        return 0.0
    return succeeded / total

