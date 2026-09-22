from __future__ import annotations

from agent_backend.capabilities.agent_runtime.execution import LlmRequestAdapter
from agent_backend.capabilities.agent_runtime.prompt.contracts import PromptRenderResult
from agent_backend.capabilities.agent_runtime.skills import SkillRenderResult


def test_llm_request_adapter_wraps_system_prompt_and_skill_messages() -> None:
    system_prompt_result = PromptRenderResult(
        agent_id="data_analysis_agent",
        node_id="system",
        template_id="data_analysis.system.base",
        template_version="v1",
        output_contract="system_prompt_v1",
        rendered_text="Global safety rules.",
        rendered_hash="hash-1",
    )
    skill_result = SkillRenderResult(
        agent_id="data_analysis_agent",
        node_id="generate_sql",
        skill_id="data_analysis.generate_sql",
        skill_version="v1",
        output_contract="generate_sql_result_v1",
        response_format="json_object",
        rendered_text="Generate SQL as JSON.",
        rendered_hash="hash-2",
    )

    request = LlmRequestAdapter().build_completion_request(
        skill_result,
        system_prompt_result=system_prompt_result,
        metadata={"trace_id": "trace-1"},
    )

    assert request.response_format == "json_object"
    assert len(request.messages) == 2
    assert request.messages[0].role == "system"
    assert request.messages[0].content == "Global safety rules."
    assert request.messages[1].role == "user"
    assert request.messages[1].content == "Generate SQL as JSON."
    assert request.metadata == {
        "agent_id": "data_analysis_agent",
        "node_id": "generate_sql",
        "template_id": "data_analysis.generate_sql",
        "template_version": "v1",
        "rendered_prompt_hash": "hash-2",
        "output_contract": "generate_sql_result_v1",
        "skill_id": "data_analysis.generate_sql",
        "skill_version": "v1",
        "rendered_skill_hash": "hash-2",
        "system_prompt_template_id": "data_analysis.system.base",
        "system_prompt_version": "v1",
        "rendered_system_prompt_hash": "hash-1",
        "trace_id": "trace-1",
    }


def test_llm_request_adapter_allows_generation_options() -> None:
    prompt_result = PromptRenderResult(
        agent_id="data_analysis_agent",
        node_id="interpret_result",
        template_id="data_analysis.interpret_result.base",
        template_version="v1",
        output_contract="interpret_result_v1",
        rendered_text="Explain query result.",
        rendered_hash="hash-2",
    )

    request = LlmRequestAdapter().build_completion_request(
        prompt_result,
        response_format="text",
        temperature=0.2,
        max_output_tokens=512,
        timeout_ms=30000,
    )

    assert request.response_format == "text"
    assert request.temperature == 0.2
    assert request.max_output_tokens == 512
    assert request.timeout_ms == 30000
