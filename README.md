# quant-agent-lab

**一个多智能体 A 股投研工程 / A multi-agent equity research workbench.**

五个各司其职的 Agent 协同工作：一个调度中枢 + 一个数据管道 + 两个风格迥异的分析师 + 一个复盘观察员，
前端用 React + AntD 展示信号、策略与 Agent 运行轨迹。

> ⚠️ **本项目只输出研究结论，不接任何券商下单接口。** 所有内容不构成投资建议。

---

## 为什么做这个

单人做投研最大的问题不是缺数据，是**缺一套稳定复用的流程**：
今天看基本面、明天追情绪，判断标准随心情漂移，做过的分析没法回溯，错的也没人复盘。

这个项目把流程固化下来：

- **分工**：数据收集、价值判断、情绪判断、复盘评分，各自独立，互不污染上下文
- **可追溯**：每次运行读了什么数据、谁下了什么结论、事后对没对，全部落库
- **可替换**：编排用 LangGraph，但业务逻辑写成框架无关的普通类，契约（JSON Schema）与框架解耦

## 架构

```
        ┌──────────────────────────────┐
        │   财务规划官 Planner          │  目标 → 任务计划 → 派活 → 汇总
        └───────────────┬──────────────┘
        ┌───────────────┼───────────────┬──────────────┐
        ▼               ▼               ▼              ▼
 ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐
 │ 信息收集员 │  │ 价投专家   │  │ 游资专家   │  │ 观察员     │
 │ Collector  │  │ Value      │  │ Momentum   │  │ Reviewer   │
 │ 抓取/清洗  │  │ 基本面     │  │ 情绪/量价  │  │ 复盘/评分  │
 └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
       └───────────────┴───────────────┴──────────────┘
                           ▼
                 结构化结果落库（SQLite / Postgres）
                           ▼
        FastAPI  ─────────────────►  React + AntD 前端
```

## 目录

```
docs/       需求、架构、Agent 契约、数据源接入、路线图、ADR
backend/    FastAPI + SQLAlchemy + LangGraph（编排）
frontend/   React 18 + TypeScript + Vite + AntD 5
deploy/     docker-compose 与部署说明
```

## 快速开始（v0.1 骨架）

后端不依赖任何付费数据源——默认使用 `MockProvider`，无账号也能跑通整条链路：

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8000
```

打开 http://127.0.0.1:8000/docs 看接口，或：

```bash
curl -X POST http://127.0.0.1:8000/api/runs \
  -H 'Content-Type: application/json' \
  -d '{"goal":"今天该关注什么","capital":100000,"risk":"medium"}'
```

前端：

```bash
cd frontend
npm install && npm run dev
```

## 数据源

| 源 | 用途 | 成本 | 备注 |
|---|---|---|---|
| 通达信 MCP | 行情、K 线、选股、公告、研报、宏观 | 免费 | 主数据源 |
| Wind（本地 WindPy MCP） | 基本面、跨市场、口径校验 | 复用已有终端 | 需本机 Windows |
| Mock | 开发与 CI | 免费 | 默认启用，保证可跑 |

见 [docs/04-数据源接入.md](docs/04-数据源接入.md)。

## 状态

v0.1 — **文档 + 骨架**。接口、契约、数据流已定型；Agent 的业务逻辑与回测待 v0.2。

### 智能体编辑器

前端 `/agents` 页面可以新建与编辑智能体：**名称 / 角色描述 / 工作流 / 可用工具 / 输出格式**，
保存前可试运行验证。内置的 5 个 Agent 可编辑不可删，自定义 Agent 可自由增删。

见 [docs/08-智能体编辑器.md](docs/08-智能体编辑器.md)。

路线见 [docs/05-路线图.md](docs/05-路线图.md)。

## License

MIT
