from __future__ import annotations

from agent_backend.orchestration.data_analysis.nodes._shared import enter_node
from agent_backend.orchestration.state import AgentState


def interpret_result(state: AgentState) -> AgentState:
    return enter_node(state, "interpret_result")
