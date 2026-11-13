"""总览大屏聚合接口。

设计见 `docs/09-总览大屏设计.md`。

**当前阶段是 P0 占位**：六块数据全部是 mock，但契约按最终形态定死。
这样前端可以一次写完，后续接真实数据只改 provider，不改组件。

约定：每个模块都带 `status / source / as_of`，
前端据此渲染"未接入"占位，而不是把空数据画成 0——
"没有资金流入"和"不知道有没有资金流入"是两回事。
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/dashboard")

#: 与真实 2026-11-12 的盘面对齐，方便评审时对照
AS_OF = "2026-11-12"


def _sentiment_series(days: int = 60) -> list[dict[str, Any]]:
    """确定性的情绪指数序列（mock）。不用随机数，保证每次刷新一致。"""
    start = date(2026, 11, 12) - timedelta(days=days * 7 // 5 + 10)
    out: list[dict[str, Any]] = []
    for i in range(days):
        # 主干：一段上行后回落，叠加两层波动
        base = 55 + 18 * math.sin(i / 9.0) - 0.22 * i
        wave = 6 * math.sin(i / 2.3) + 3 * math.sin(i / 1.1)
        value = max(8.0, min(96.0, base + wave))
        day = start + timedelta(days=int(i * 1.4))
        out.append({"date": day.isoformat(), "value": round(value, 1)})
    out[-3]["value"] = 63.2
    out[-2]["value"] = 58.1
    out[-1] = {"date": AS_OF, "value": 42.6}
    return out


def _panorama() -> dict[str, Any]:
    return {
        "status": "degraded",
        "source": "mock（待接 agent:planner）",
        "as_of": f"{AS_OF} 15:35",
        "note": "战略要览尚未接入 planner 输出，以下为示例文案",
        "data": {
            "brief": (
                "情绪从高位回落，连板高度卡在 5 板，指数缩量下跌但涨停家数没崩，"
                "属于退潮中的抵抗。今天不追高位接力，只做低位首板的确认；"
                "防守优先级高于进攻。"
            ),
            "phase": {"key": "ebb", "label": "退潮", "since": AS_OF, "days": 1},
            "sentiment_index": {
                "today": 42.6,
                "yesterday": 58.1,
                "delta": -15.5,
                "trend_5d": "down",
            },
            "core_conflict": {
                "text": "指数缩量下跌 vs 连板高度仍在 5 板",
                "evidences": [
                    {"label": "成交额", "value": "1.60 万亿", "change": "-11.3%"},
                    {"label": "涨停家数", "value": "37", "change": "前日 82"},
                    {"label": "涨跌家数", "value": "656 / 3668", "change": "中位 -1.57%"},
                ],
            },
        },
    }


def _capital_flow() -> dict[str, Any]:
    return {
        "status": "degraded",
        "source": "mock（待接 akshare:board_fund_flow）",
        "as_of": f"{AS_OF} 15:35",
        "note": "板块资金流接口未接入，数据为示例",
        "data": {
            "net_inflow_top": [
                {"board": "光伏设备", "net_inflow_yi": 38.4, "change_pct": 2.31, "leader": "亚玛顿"},
                {"board": "银行", "net_inflow_yi": 21.7, "change_pct": 0.84, "leader": "招商银行"},
                {"board": "食品饮料", "net_inflow_yi": 12.5, "change_pct": 0.41, "leader": "贵州茅台"},
                {"board": "公用事业", "net_inflow_yi": 8.9, "change_pct": 0.62, "leader": "东方环宇"},
                {"board": "家用电器", "net_inflow_yi": 6.3, "change_pct": 0.35, "leader": "日出东方"},
            ],
            "net_outflow_top": [
                {"board": "半导体", "net_outflow_yi": 46.2, "change_pct": -2.14, "leader": "中芯国际"},
                {"board": "电力设备", "net_outflow_yi": 31.8, "change_pct": -1.86, "leader": "宁德时代"},
                {"board": "医药生物", "net_outflow_yi": 24.1, "change_pct": -1.42, "leader": "药明康德"},
                {"board": "计算机", "net_outflow_yi": 19.6, "change_pct": -2.31, "leader": "科大讯飞"},
                {"board": "有色金属", "net_outflow_yi": 14.2, "change_pct": -1.07, "leader": "北方稀土"},
            ],
            "note": "净额以主力资金计，不含散户小单",
        },
    }


def _sentiment() -> dict[str, Any]:
    return {
        "status": "degraded",
        "source": "mock（zvt 已具备计算条件，P1 接入）",
        "as_of": AS_OF,
        "note": "曲线与极端标的为示例数据，尚未接本地库",
        "data": {
            "series": _sentiment_series(60),
            "ma20": 55.4,
            "extremes": [
                {"type": "stock", "code": "600327", "name": "大东方", "reason": "5 连板，情绪最高标", "side": "hot"},
                {"type": "stock", "code": "603366", "name": "日出东方", "reason": "5 连板，尾盘反复", "side": "hot"},
                {"type": "stock", "code": "301502", "name": "华阳智能", "reason": "面王，冲高回落 17.56%", "side": "cold"},
                {"type": "board", "code": "BK1036", "name": "半导体", "reason": "主力净流出 46 亿", "side": "cold"},
            ],
        },
    }


def _opportunity() -> dict[str, Any]:
    return {
        "status": "degraded",
        "source": "mock（板块维度待接）",
        "as_of": AS_OF,
        "note": "板块热度数据未接入，雷达值为示例",
        "data": {
            "axes": ["题材热度", "资金强度", "赚钱效应", "持续性", "拥挤度"],
            "today": [72, 41, 38, 55, 66],
            "ma5": [65, 58, 62, 60, 48],
            "picks": [
                {"direction": "低位首板确认", "conviction": 0.72, "reason": "高位断层，资金转向低位补涨"},
                {"direction": "光伏设备", "conviction": 0.61, "reason": "净流入连续 3 日居前"},
                {"direction": "回避高位 4 板以上", "conviction": 0.68, "reason": "高位股次日平均 -6.2%"},
            ],
        },
    }


def _risks() -> dict[str, Any]:
    return {
        "status": "degraded",
        "source": "mock（规则引擎待写）",
        "as_of": f"{AS_OF} 15:35",
        "note": "预警条目为示例，规则引擎尚未实现",
        "data": {
            "items": [
                {
                    "level": "high",
                    "title": "高位股进入亏钱效应",
                    "evidence": "5 板以上个股次日平均 -6.2%，连续 2 日",
                    "source": "规则:连板断层",
                    "time": f"{AS_OF} 15:05",
                },
                {
                    "level": "high",
                    "title": "封板率跌破 50%",
                    "evidence": "37 涨停 / 42 炸板 = 46.8%",
                    "source": "zvt",
                    "time": f"{AS_OF} 15:05",
                },
                {
                    "level": "medium",
                    "title": "涨停家数单日腰斩",
                    "evidence": "82 → 37，跌幅 55%",
                    "source": "zvt",
                    "time": f"{AS_OF} 15:05",
                },
                {
                    "level": "medium",
                    "title": "指数缩量下跌",
                    "evidence": "成交额 1.60 万亿，较前日 -11.3%",
                    "source": "zvt",
                    "time": f"{AS_OF} 15:05",
                },
                {
                    "level": "low",
                    "title": "面王回撤 17.56%",
                    "evidence": "华阳智能 301502 冲高回落",
                    "source": "zvt",
                    "time": f"{AS_OF} 15:02",
                },
            ]
        },
    }


def _portfolio() -> dict[str, Any]:
    return {
        "status": "degraded",
        "source": "mock（手工占位，未接真实账户）",
        "as_of": f"{AS_OF} 15:35",
        "note": "持仓为示例数据，可在设置中导入后再看真实盈亏",
        "data": {
            "summary": {
                "total_pnl": 8420.5,
                "total_pnl_pct": 4.21,
                "today_pnl": -1230.0,
                "match_score": 62,
            },
            "positions": [
                {"code": "600519", "name": "贵州茅台", "cost": 1350.0, "price": 1410.27, "pnl_pct": 4.46, "weight": 32, "hot_board": "食品饮料"},
                {"code": "002623", "name": "亚玛顿", "cost": 28.4, "price": 31.18, "pnl_pct": 9.79, "weight": 26, "hot_board": "光伏设备"},
                {"code": "000858", "name": "五粮液", "cost": 148.0, "price": 139.5, "pnl_pct": -5.74, "weight": 24, "hot_board": "食品饮料"},
                {"code": "600036", "name": "招商银行", "cost": 39.2, "price": 41.6, "pnl_pct": 6.12, "weight": 18, "hot_board": "银行"},
            ],
            "advices": [
                {"code": "002623", "action": "reduce", "reason": "已 4 连板且光伏居净流入首位，兑现一半", "trigger": "明日冲高不封板即减"},
                {"code": "600519", "action": "hold", "reason": "板块不在流入前列，但成本低，不主动加仓", "trigger": "跌破 1350 减半"},
                {"code": "000858", "action": "watch", "reason": "亏损中，等待板块资金回流再补", "trigger": "食品饮料进入净流入前三"},
                {"code": "600036", "action": "hold", "reason": "防御属性，指数弱时抗跌", "trigger": "跌破 39.2 止损"},
            ],
        },
    }


@router.get("")
def dashboard(date_: str | None = Query(default=None, alias="date")) -> dict[str, Any]:
    modules = {
        "panorama": _panorama(),
        "capital_flow": _capital_flow(),
        "sentiment": _sentiment(),
        "opportunity": _opportunity(),
        "risks": _risks(),
        "portfolio": _portfolio(),
    }
    degraded = [k for k, v in modules.items() if v["status"] != "ok"]
    return {
        "as_of": date_ or AS_OF,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mock": True,
        "degraded_modules": degraded,
        "modules": modules,
    }
