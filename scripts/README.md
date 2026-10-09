# Scripts

本目录提供本地启动、CI 校验与演示数据脚本。遵循 [根 AGENTS.md](../AGENTS.md)：
脚本不得隐式执行破坏性操作、嵌入密钥或代替应用业务逻辑。

- `dev/` 为本地开发辅助；`ci/` 必须可非交互执行；`seed/` 只创建安全的演示数据，
  并说明新增的记录。
- 脚本尽量保持可重复运行、目标明确、失败信息清晰。已有
  [聚合验证入口](ci/verify.ps1) 支持按模块跳过；它会安装或检查依赖，
  在文档改动时不必运行全量流程。
- 文档导航、结构和链接检查：从根目录运行 `python scripts/ci/check-docs.py`，
  只使用 Python 标准库，不安装应用依赖，不写文件。检查必需入口、本地链接、锚点、
  Skills 两级索引及保留目录中的 Plan 状态；错误返回退出码 1，成功返回 0。
- 检查程序回归：运行 `python -B -m unittest discover -s scripts/ci -p "test_*.py" -v`，
  使用临时 Git 仓库验证漏登、空声明、忽略范围及只读行为；CI docs 任务执行测试和文档检查。
  文档维护边界见 [根 AGENTS.md](../AGENTS.md) 和[文档导航](../docs/README.md)。
- 单次验证结果记入交付说明；需要 Agent 重复执行的流程写入适用的 [quality Skill](../skills/quality/README.md)，
  验证范围按根 AGENTS.md 与当前任务风险确定。
