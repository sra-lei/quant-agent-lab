# 03 · Agent 契约（Agent Contracts）

> 契约是本项目最重要的资产。改契约 = 改所有 Agent 的接口，必须走版本号。

## 0. 通用约定

- **序列化**：JSON，字段 `snake_case`
- **时间**：日期 `YYYY-MM-DD`；时间戳 ISO8601 带时区
- **数值**：金额单位统一为**元**（不是万元），比例用小数（`0.05` = 5%）
- **缺失值**：一律 `null` + 在 `missing_fields` 里列出，**禁止填 0 或估算值**
- **版本**：每个契约带 `schema_version`，破坏性变更升主版本

---

## 1. `TaskPlan` — 规划官输出

```json
{
  "schema_version": "1.0",
  "plan_id": "plan_20261113_001",
  "goal": "找出本周值得关注的低估值+情绪启动标的",
  "budget": { "max_tokens": 120000, "deadline_s": 600 },
  "tasks": [
    { "task_id": "t1", "agent": "collector",
      "depends_on": [], "params": { "universe": "all", "days": 60 } },
    { "task_id": "t2", "agent": "value_analyst",
      "depends_on": ["t1"], "params": { "max_pe_percentile": 0.3 } },
    { "task_id": "t3", "agent": "momentum_analyst",
      "depends_on": ["t1"], "params": { "min_turnover_ratio": 1.5 } },
    { "task_id": "t4", "agent": "planner_synthesize",
      "depends_on": ["t2", "t3"], "params": {} }
  ]
}
```

**约束**
- `tasks` 必须是 DAG（无环）；编排器启动时校验
- `agent` 必须在 registry 注册，否则运行前报错
- `depends_on` 为空的任务可并行

---

## 2. `MarketSnapshot` — 收集员输出

```json
{
  "schema_version": "1.0",
  "snapshot_id": "snap_20261113",
  "as_of": "2026-11-13",
  "source": "tdx_mcp",
  "universe": ["600519", "000858"],
  "bars": {
    "600519": [
      { "date": "2026-11-12", "open": 1680.0, "high": 1699.0,
        "low": 1672.0, "close": 1695.5,
        "volume": 2100000, "amount": 3560000000 }
    ]
  },
  "breadth": {
    "advancers": 2810, "decliners": 1620,
    "limit_up": 43, "limit_down": 6,
    "turnover_rate": 0.0128
  },
  "fundamentals": {
    "600519": { "pe_ttm": 22.1, "pb": 7.8, "roe": 0.31,
                "revenue_yoy": 0.11, "net_profit_yoy": 0.09,
                "report_period": "2026Q3" }
  },
  "announcements": [
    { "code": "600519", "date": "2026-11-10",
      "type": "分红", "title": "2026 年中期利润分配方案" }
  ],
  "quality": {
    "stale": false,
    "missing_fields": ["000858.fundamentals.roe"],
    "anomalies": [
      { "code": "000858", "field": "close", "reason": "单日涨跌幅 21.3%，疑似复权异常" }
    ]
  }
}
```

**约束**
- `universe` 内每只票都必须出现在 `bars` 里（可以为空列表，但不能缺 key）
- `quality.stale=true` 时，下游 Agent **必须**在结论中标注"数据过期"
- `anomalies` 非空的标的，分析师不得给出高 conviction（< 0.5）

---

## 3. `AnalystView` — 两位分析师输出（同一契约）

```json
{
  "schema_version": "1.0",
  "view_id": "view_value_20261113",
  "agent": "value_analyst",
  "snapshot_id": "snap_20261113",
  "as_of": "2026-11-13",
  "candidates": [
    {
      "code": "600519",
      "name": "贵州茅台",
      "stance": "long",
      "conviction": 0.68,
      "horizon_days": 60,
      "rationale": "PE 处于近五年 18% 分位，ROE 31%，现金流稳定；三季度营收增速回升至 11%",
      "entry_zone": [1620.0, 1700.0],
      "invalidation": "若下季度营收增速转负，或 PE 分位升破 60%，逻辑失效",
      "evidence": ["snap_20261113.bars.600519", "snap_20261113.fundamentals.600519"]
    }
  ],
  "notes": "全市场估值中位数处于历史 45% 分位，整体不贵但也不算极端便宜",
  "warnings": []
}
```

**字段语义**
- `stance`：`long`（看多）/ `watch`（观察）/ `avoid`（回避）
- `conviction`：0–1，**必须**与证据强度匹配；证据不足就低于 0.5
- `invalidation`：**必填**。说不出什么情况下自己会错的判断，等于没有判断
- `evidence`：必须指向 snapshot 内的具体路径，前端据此做溯源跳转

---

## 4. `ResearchConclusion` — 规划官合并输出

```json
{
  "schema_version": "1.0",
  "conclusion_id": "concl_20261113_001",
  "run_id": "run_20261113_001",
  "as_of": "2026-11-13",
  "summary": "今日两路视角分歧明显：价值面看多消费龙头，情绪面看多算力链；建议分仓对待。",
  "picks": [
    {
      "code": "600519", "name": "贵州茅台", "stance": "long",
      "conviction": 0.6,
      "sources": ["value_analyst"],
      "rationale": "估值分位低 + 现金流稳，适合中线",
      "risk": "消费复苏不及预期"
    }
  ],
  "disagreements": [
    {
      "code": "600519",
      "agents": ["value_analyst", "momentum_analyst"],
      "summary": "价投给出 long(0.68)，游资给出 avoid(0.55)：前者看估值修复，后者认为资金正在流出、缺乏催化。"
    }
  ],
  "risk_notes": ["数据源 tdx_mcp 当日公告覆盖不全，可能漏掉盘后重大事项"],
  "disclaimer": "本结论由自动化系统生成，不构成投资建议。"
}
```

**硬性规则**
1. **分歧不合并**：两个专家对同一标的方向相反时，必须进 `disagreements`，不得取平均后只报一个
2. **来源可查**：`sources` 里每个 agent 名必须对应一次真实运行
3. **免责声明**：前端展示时必须原样保留 `disclaimer`

---

## 5. `ReviewReport` — 观察员输出

```json
{
  "schema_version": "1.0",
  "review_id": "review_2026W46",
  "period": "2026-W46",
  "as_of": "2026-11-15",
  "samples": 27,
  "hit_rate": 0.52,
  "avg_return": 0.031,
  "max_drawdown": -0.084,
  "by_agent": {
    "value_analyst":    { "hit_rate": 0.61, "samples": 13, "avg_return": 0.045 },
    "momentum_analyst": { "hit_rate": 0.43, "samples": 14, "avg_return": 0.018 }
  },
  "attributions": [
    { "code": "300750", "verdict": "miss",
      "reason": "情绪面判断正确但入场点偏高，触发回撤止损" }
  ],
  "improvements": [
    "游资策略在连板高度 > 5 时命中率显著下降，建议加入高度过滤",
    "数据缺失导致的无效信号占比 11%，优先补齐公告覆盖"
  ]
}
```

**约束**
- `improvements` 必须是**可执行的具体动作**，不接受"加强研究""注意风险"这类空话
- 样本数 < 5 时不出 `hit_rate`（统计意义不足），标 `insufficient_samples: true`

---

## 6. 契约演进规则

| 变更类型 | 例子 | 处理 |
|---|---|---|
| 加可选字段 | 新增 `sector` | 次版本号 +0.1，向后兼容 |
| 改字段语义 | `conviction` 从 0-1 改成 0-100 | 主版本 +1，所有 Agent 同步升级 |
| 删必填字段 | 移除 `invalidation` | 禁止（除非升主版本且给出迁移说明） |

**执行方式**：契约代码在 `backend/app/contracts/schemas.py`，任何改动必须同时更新本文档与对应测试。
