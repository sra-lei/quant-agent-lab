# TODO

> 本文件是**当前 sprint 的待办**；长期路线见 [docs/05-路线图.md](docs/05-路线图.md)。
> 完成一项就移到「已完成」，不要留在待办里制造虚假进度。

## 进行中

- [ ] **接通达信 MCP**：`TdxMcpProvider` 的工具名目前是占位（`kline` / `announcement` / `market_breadth`），
      需要按实际 MCP 服务的 `tools/list` 对齐；缺 endpoint 与工具清单
- [ ] **Wind MCP 联调**：需在本机 Windows 起 `wind-mcp`，把地址与 token 给到 `WIND_MCP_ENDPOINT`

## 下一步

- [ ] 自定义 Agent 接入日程编排（`ConfigDrivenAgent` 实现 `BaseAgent` + plan 读取 enabled 配置）
- [ ] 工作流分支：步骤间条件判断（如"数据缺失则跳过该分析师"）
- [ ] 版本对比支持任选两个历史版本（接口已支持 `?against=N`，前端只做了"对比当前"）
- [ ] 工具参数级默认值（现在只能选工具，不能预填参数）
- [ ] CI：GitHub Actions 跑 `scripts/smoke.py` + 契约测试

## 已知限制（不是 bug，是明确的取舍）

- LangGraph 编排实现为骨架，未实跑（需 `pip install -e ".[langgraph]"`）
- 内置 5 个 Agent 是确定性规则，不读编辑器配置；编辑器配置目前只用于试运行
- 无 LLM Key 时最终结论为 schema 样例（工具调用仍是真实执行）
- 前端 bundle 1.1MB 未做代码分割

## 已完成

- [x] v0.1 文档与骨架（需求/架构/契约/数据源/路线图/ADR/部署）
- [x] 智能体编辑器（名称/角色/工作流/工具/输出格式）
- [x] 提示词与配置版本历史（差异对比 + 回滚）
- [x] 工具执行层（8 个工具 handler + function calling 循环）
- [x] 单进程单端口部署（FastAPI 托管前端）
- [x] 接入真实 LLM（DeepSeek deepseek-v4-flash）：多轮工具调用 + schema 校验通过
      · 实测一次价投 Agent：3 轮、3 次工具调用、约 5.3k tokens
