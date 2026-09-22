# Tasks

## 1. 文档与边界收敛

- [x] 1.1 更新 `backend-agent/agent.md` 的 Prompt and Context Rules，将节点级 prompt 规则改为 system prompt + Node Skill 边界，并验证文档不再要求 `prompts/{node_id}` 承载节点任务说明
- [x] 1.2 更新 `backend-agent/docs/packages/prompt_hub/*`，将 `prompt_hub` 定位收窄为 system prompt，并验证文档明确 Node Skill 不属于 prompt_hub 职责
- [x] 1.3 新增或更新 Node Skill 设计文档，说明 Skill 文件格式、静态 node binding、required_context、output_contract 与 message composition，并验证文档明确本阶段不做注册与发现

## 2. Node Skill 文件与加载

- [x] 2.1 新增 Node Skill contract、loader 与错误类型，支持读取 Markdown front matter，并用单元测试验证缺少必填 metadata 会失败
- [x] 2.2 将 `generate_sql`、`repair_sql`、`interpret_result`、`build_chart` 从现有节点 prompt 抽出到 `capabilities/data_analysis/skills/`，并验证四个 Skill 文件保留原有 rules、边界和 output_contract
- [x] 2.3 实现静态 node binding 或节点内显式 Skill 路径映射，并验证需要 LLM 的节点缺少绑定时会在模型调用前失败
- [x] 2.4 实现 Node Skill 的 required_context/optional_context 校验，并用单元测试验证缺少 required context 不调用模型、缺少 optional context 可以继续

## 3. LLM 消息组装与执行路径

- [x] 3.1 调整 system prompt 加载路径，确保 system prompt 可单独生成版本/hash，并用单元测试验证 system prompt 不再作为普通节点 prompt 加载
- [x] 3.2 新增 LLM message composition 逻辑，将 system prompt 组装为 `system` message，将 Node Skill 与当前 ContextBundle 组装为节点任务 message，并用单元测试验证 messages 顺序和 role 正确
- [x] 3.3 将 `generate_sql` 切换到 Node Skill 执行路径，并验证 `GenerateSqlResult` 校验、状态写入、错误分支和现有 generate_sql 单元测试通过
- [x] 3.4 迁移 `repair_sql`、`interpret_result`、`build_chart` 到同一执行路径，并验证每个节点仍使用对应 output_contract 做模型输出校验
- [x] 3.5 更新 replay/audit metadata，记录 `system_prompt_*` 与 `skill_*` 版本/hash，并验证事件或状态中可追踪本次模型调用使用的 system prompt 与 Node Skill

## 4. 回归验证

- [x] 4.1 更新或新增 prompt/skill 相关单元测试，并运行 `pytest tests/unit/test_prompt_hub.py tests/unit/test_prompt_input_adapter.py tests/unit/test_runtime_turn_runner.py` 验证关键路径
- [x] 4.2 运行与数据分析 graph 相关的单元测试，验证 `generate_sql -> validate_sql` 主链路行为未回退
- [x] 4.3 检查代码和文档中旧的节点 prompt 引用，验证除兼容说明外不再把 `generate_sql`、`repair_sql`、`interpret_result`、`build_chart` 称为 prompt_hub 管理的节点 prompt

## 5. Skill 推理增强

- [x] 5.1 为 `generate_sql`、`repair_sql`、`interpret_result`、`build_chart` 增加内部推理流程，验证其要求不输出完整推理链
- [x] 5.2 为四个 Node Skill 增加 few-shot 示例，覆盖成功路径和失败或降级路径，并验证示例 JSON 贴近对应 `output_contract`
- [x] 5.3 更新 Node Skill 文档和 OpenSpec delta，验证方案明确 few-shot 与内部推理流程属于 Skill 正文规范
