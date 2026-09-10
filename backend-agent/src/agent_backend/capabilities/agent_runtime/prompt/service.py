from __future__ import annotations

from agent_backend.capabilities.agent_runtime.prompt.contracts import (
    PromptRenderRequest,
    PromptRenderResult,
    UserFacingFailure,
)
from agent_backend.capabilities.agent_runtime.prompt.exceptions import (
    MissingPromptVariablesError,
)
from agent_backend.capabilities.agent_runtime.prompt.registry import PromptRegistry
from agent_backend.capabilities.agent_runtime.prompt.renderer import PromptRenderer


_DEFAULT_REGISTRY: PromptRegistry | None = None


def render_prompt(request: PromptRenderRequest) -> PromptRenderResult:
    registry = _get_default_registry()
    template = registry.get_template(
        request.agent_id,
        request.node_id,
        request.template_version,
    )
    return PromptRenderer().render(template, request)


def map_prompt_error_to_user_failure(error: MissingPromptVariablesError) -> UserFacingFailure:
    missing = set(error.missing_variables)

    if "user_question" in missing:
        return UserFacingFailure(
            code="missing_user_question",
            message="我还没有拿到明确的分析问题。请告诉我你想分析什么指标、范围或维度。",
            retryable=True,
            user_action_required=True,
            missing_variables=error.missing_variables,
        )
    if "dataset_context" in missing:
        return UserFacingFailure(
            code="missing_dataset_context",
            message="我还没有拿到要分析的数据集。请先选择一个数据源或上传文件后再继续。",
            retryable=True,
            user_action_required=True,
            missing_variables=error.missing_variables,
        )
    if "schema_context" in missing:
        return UserFacingFailure(
            code="missing_schema_context",
            message="我暂时无法读取当前数据集的表结构，所以还不能可靠生成 SQL。请确认数据源连接是否正常，或稍后重试。",
            retryable=True,
            user_action_required=False,
            missing_variables=error.missing_variables,
        )
    if "access_context" in missing:
        return UserFacingFailure(
            code="missing_access_context",
            message="当前数据权限信息不完整。为避免越权查询，我不能继续生成 SQL，请重新选择数据集或联系管理员确认权限。",
            retryable=True,
            user_action_required=True,
            missing_variables=error.missing_variables,
        )
    if {"failed_sql", "error_message"}.intersection(missing):
        return UserFacingFailure(
            code="missing_repair_context",
            message="缺少失败 SQL 或错误原因，无法自动修复。请重新发起分析或保留完整错误上下文后重试。",
            retryable=True,
            user_action_required=True,
            missing_variables=error.missing_variables,
        )
    if {"result_summary", "sample_rows", "result_columns"}.intersection(missing):
        return UserFacingFailure(
            code="missing_result_context",
            message="查询结果暂时不可用，无法生成结果解释或图表。请先确认 SQL 已成功执行。",
            retryable=True,
            user_action_required=False,
            missing_variables=error.missing_variables,
        )

    return UserFacingFailure(
        code="missing_prompt_variables",
        message="当前分析上下文不完整，暂时无法继续处理。请补充必要信息后重试。",
        retryable=True,
        user_action_required=True,
        missing_variables=error.missing_variables,
    )


def _get_default_registry() -> PromptRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = PromptRegistry()
    return _DEFAULT_REGISTRY
