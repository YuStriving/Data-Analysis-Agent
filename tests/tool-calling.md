# 通用工具契约测试方案

需求：[spec](../spec/tool-calling/spec.md)；设计：[design](../spec/tool-calling/design.md)。
所有代码路径相对 backend-agent。结果与预期分别记录，不以预期替代通过证据。

## 用例矩阵

| 编号 | 需求 | 前置条件、输入或操作 | 预期结果 | 测试代码 |
| --- | --- | --- | --- | --- |
| TC-T01 | TC-001/003 | 注册文本和计算工具，用通用 context 调用；图表无业务 scope | 同一路径成功，无数据集依赖 | G1、D1 |
| TC-T02 | TC-002/003 | 设置 goal/purpose、具体业务 context；输入缺失/空白目标 | 字段类型完整传递；无效目标拒绝 | G2、E1、N1 |
| TC-T03 | TC-004 | 缺策略/Gate、节点能力不足、身份或权限不足；检查返回 bool/awaitable | 失败，业务调用次数为零；非法回调不得放行 | G3、E2、N2 |
| TC-T04 | TC-004/009 | 越权数据集、不支持类型、写 SQL、禁止风险/审批 | 执行前拒绝 | B1、G3 |
| TC-T05 | TC-005 | 多版本、版本不一致、工具或版本不存在 | 精确版本成功；不一致/不存在明确失败 | R1、E3 |
| TC-T06 | TC-006 | dict/Pydantic 输入、错误结构/schema、None/不可序列化输出 | 合法成功，非法输入不执行，非法输出不产生成功结果 | E4 |
| TC-T07 | TC-007 | sync/async/awaitable、事件循环线程隔离、超时/取消 | 保持响应，超时明确，取消传播，不重试 | E5、R2 |
| TC-T08 | TC-008 | 固定 call id、普通异常/已有异常 | 成功四字段稳定，错误四字段保留及原因链 | E6、R3 |
| TC-T09 | TC-009 | 发现可见但无权执行，现有数据分析节点与查询 | Gate 不被绕过，旧关键行为保持 | G4、B2、D2、N3、F1、C1 |
| TC-T10 | 文档 | 校验 spec/tests 链接、RULE 编号、pytest 配置 | 引用有效，方案集中，测试代码留在原目录 | 文档静态核验 |

## 测试函数映射

各标识对应以下可执行测试；参数化拒绝用例的每组输入均独立计入 pytest 结果。

- G1～G4：[test_tool_authorization_gate.py](../backend-agent/tests/unit/test_tool_authorization_gate.py)。G1：`test_unrelated_business_tools_share_the_generic_call_path`；G2：`test_context_rejects_blank_goal_and_purpose`、`test_context_requires_goal_and_purpose`；G3：`test_executor_requires_an_authorization_gate`、`test_gate_rejections_prevent_runtime_and_direct_execution`、`test_runtime_rejects_invalid_authorization_callback`；G4：`test_discovered_tool_still_requires_permission_at_execution`（目标文本声称扩大权限也不能通过）。
- E1～E6：[test_tool_executor.py](../backend-agent/tests/unit/test_tool_executor.py)。E1：`test_request_preserves_concrete_context_and_serialized_fields`；E2：`test_executor_rejects_invalid_authorization_return_before_execution`、`test_executor_rejects_async_authorization_without_running_business`；E3：`test_executor_rejects_version_mismatch_before_running_business`。
- E4：`test_executor_accepts_pydantic_input_and_generates_a_call_id`、`test_executor_rejects_invalid_input_without_running_business`、`test_executor_raises_for_malformed_input_without_running_business`、`test_executor_rejects_invalid_output`、`test_executor_rejects_non_json_outputs`、`test_executor_classifies_model_serialization_failure_as_invalid_output`。
- E5：`test_executor_awaits_an_async_business_tool`、`test_executor_awaits_a_coroutine_returned_by_a_sync_execute_method`、`test_executor_runs_sync_business_tools_outside_the_event_loop_thread`、`test_executor_times_out_and_cancels_async_business_execution`、`test_executor_preserves_cancellation`。
- E6：`test_executor_returns_a_structured_result_and_passes_context_to_business`、`test_executor_wraps_business_errors_and_preserves_the_cause`、`test_executor_preserves_typed_business_errors`、`test_tool_call_error_default_payload_can_be_sent_by_the_calling_event_boundary`。
- R1～R3：[test_tool_calling_runtime.py](../backend-agent/tests/unit/test_tool_calling_runtime.py)。R1：`test_registry_gets_tool_by_name_and_version`、`test_runtime_executes_the_requested_tool_version`、`test_runtime_raises_for_registry_lookup_errors`、`test_runtime_executes_the_business_object_resolved_before_validation`；R2：`test_runtime_times_out_slow_tool`；R3：`test_runtime_returns_business_data_and_call_identity`。
- B1～B2：[test_data_analysis_tool_runtime.py](../backend-agent/tests/unit/test_data_analysis_tool_runtime.py)。B1：`test_minimal_business_tools_preserve_factory_injected_access_checks`（Agent、节点、权限、数据集、类型、危险 SQL 六组）；B2：`test_schema_reader_runtime_reads_schema_from_metadata_engine`。
- D1～D2：[test_data_analysis_tools.py](../backend-agent/tests/unit/test_data_analysis_tools.py)。D1：`test_runtime_can_call_chart_tool_without_dataset_scope`；D2：`test_relation_query_executor_uses_duckdb`、`test_mysql_query_executor_enforces_max_rows`。
- N1～N3：[test_data_analysis_context_nodes.py](../backend-agent/tests/unit/test_data_analysis_context_nodes.py)。N1：`test_build_context_delivers_goal_purpose_and_typed_business_scope`；N2：`test_build_context_rejects_task_and_java_identity_mismatch`；N3：`test_build_context_calls_schema_tool_and_builds_context_bundle`、`test_load_task_context_rejects_non_readonly_context`、`test_tool_failure_details_survive_node_and_terminal_events`。
- F1：[test_data_analysis_graph.py](../backend-agent/tests/unit/test_data_analysis_graph.py)：`test_data_analysis_graph_reads_schema_then_generates_sql`、`test_data_analysis_graph_normalizes_file_schema_then_generates_sql`、`test_data_analysis_graph_rejects_unsafe_sql_before_execution`。
- C1：[test_execution_control.py](../backend-agent/tests/unit/test_execution_control.py)：`test_controller_rejects_tool_outside_node_allowlist`、`test_controller_rejects_risky_tool_policy`、`test_controller_counts_failures_by_reason_instead_of_message`。

## 验证命令

在 backend-agent 执行：

本轮 Python 环境未安装 DuckDB，已按项目声明的依赖安装到忽略目录 `.venv/verification-deps`。
复现本轮环境时，先执行以下两步；已安装 DuckDB 的项目环境可直接运行下面的测试命令。

```powershell
python -m pip install --target .venv/verification-deps 'duckdb>=1.1.0' --disable-pip-version-check
$env:PYTHONPATH = (Resolve-Path -LiteralPath '.venv/verification-deps').Path
```

```powershell
python -m pytest -p no:cacheprovider tests/unit/test_tool_executor.py tests/unit/test_tool_calling_runtime.py tests/unit/test_tool_authorization_gate.py tests/unit/test_execution_control.py tests/unit/test_data_analysis_tools.py tests/unit/test_data_analysis_tool_runtime.py tests/unit/test_data_analysis_context_nodes.py tests/unit/test_data_analysis_graph.py -q
python -m ruff check src/agent_backend/capabilities/agent_runtime/tool_calling src/agent_backend/capabilities/agent_runtime/execution_control src/agent_backend/capabilities/data_analysis/tools src/agent_backend/orchestration/data_analysis/nodes/build_context.py tests/unit/test_tool_executor.py tests/unit/test_tool_calling_runtime.py tests/unit/test_tool_authorization_gate.py tests/unit/test_execution_control.py tests/unit/test_data_analysis_tools.py tests/unit/test_data_analysis_tool_runtime.py tests/unit/test_data_analysis_context_nodes.py tests/unit/test_data_analysis_graph.py
```

## 验证记录

规划稿所列历史基线为五个相关测试文件 59 passed、1 skipped（缺 DuckDB）；本轮验收使用以下实际结果。

| 记录 | 日期 | 用例与检查 | 实际结果 |
| --- | --- | --- | --- |
| V1 | 2026-10-03 | 上述八文件 pytest；TC-T01～TC-T09 | **127 passed，0 skipped**；1 条 LangChainPendingDeprecationWarning，来自 LangGraph 依赖，未影响测试 |
| V2 | 2026-10-03 | 上述范围 Ruff | **All checks passed** |
| V3 | 2026-10-03 | TC-T10、RULE-07/08：11 份相关文档 | 38 个本地链接目标存在；TC-001～009、RULE-01～08、TC-T01～10 完整；48 个测试函数引用实际存在；无行尾空格；pytest testpaths 仍为模块 tests；影响范围内 git diff --check 通过 |
| V4 | 2026-10-03 | 独立只读复核及授权修正 | 复现授权回调返回 bool/awaitable 仍执行的问题；新增独立执行器 3 例、Runtime/业务检查 6 例，修正后两个文件 **49 passed**，独立复核同为 49 passed，无 coroutine 未等待警告 |
| V5 | 2026-10-03 | 用户授权提交后的提交前复验 | 当前工作区及暂存区独立导出快照均为 **127 passed**、Ruff 通过；快照的 11 份相关文档、38 个本地链接通过；git diff --cached --check 通过。Java、Docker、OpenSpec 删除及其他独立改动未纳入暂存区 |

V3 检查步骤：枚举 spec/tests 下 Markdown，以及 AGENTS.md、backend-agent/agent.md 和
tool_calling 的 README/architecture；按引用文件所在目录解析相对链接并检查目标存在；
校验需求、规则及用例组编号；用 Python AST 对照八个测试文件的函数名；读取 pyproject.toml
确认测试发现目录为 tests。协作规范验收结果见 [collaboration-rules.md](collaboration-rules.md)。

测试先行记录：输出模型序列化失败原被包装为普通执行失败，新增复现后明确归为 Invalid tool output；
非法授权返回的 9 个新用例在修正前均失败（工具被执行），修正后均通过且工具调用次数为零。
最终 V1 在全部测试补齐后执行，包含真实 DuckDB 查询，解决历史跳过项。

本次按计划完成关键路径验证，未运行仓库全量测试或连接实际 Java/MySQL 部署；Java 入口没有改动，
数据库适配路径使用 SQLite 和本地 DuckDB 验证。无计划内关键用例未执行。
同步线程超时只停止等待，不保证底层线程终止；调用方不得据此假定业务操作已停止。
