"""工具实现层。

声明在 `tools.py`，实现在这里，两边用同一个 key 对齐。
设计约束：
1. 工具失败**不抛异常**，返回 `{"error": ...}` 让模型自己决定怎么应对
2. 返回值必须**裁剪**（只给必要的尾部数据），否则一次行情调用就能把上下文撑爆
3. 所有取数走 `DataProvider`，不直连网络——保证 mock 模式下也能跑通
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

from app.core.llm import get_llm
from app.core.logging import get_logger
from app.data.base import DataProvider, ProviderError

log = get_logger(__name__)

#: 返回给模型的最大条数，防止上下文爆炸
MAX_SERIES_ROWS = 10


@dataclass
class ToolContext:
    provider: DataProvider
    as_of: date
    reports_dir: Path = field(default_factory=lambda: Path("reports"))
    calls: list[dict] = field(default_factory=list)


# --------------------------------------------------------------------- helpers
def _clip_series(rows: list[dict]) -> list[dict]:
    return rows[-MAX_SERIES_ROWS:]


def _bar_to_dict(bar) -> dict:
    return {
        "date": bar.date.isoformat(),
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
    }


# -------------------------------------------------------------------- handlers
def _market_quotes(ctx: ToolContext, args: dict) -> dict:
    code = str(args.get("code") or "").strip()
    if not code:
        return {"error": "缺少参数 code"}
    days = int(args.get("days") or 60)
    start = ctx.as_of - timedelta(days=days * 2)

    try:
        bars = ctx.provider.quotes([code], start, ctx.as_of).get(code) or []
    except ProviderError as exc:
        return {"error": f"取行情失败：{exc}"}

    if not bars:
        return {"error": f"{code} 无行情数据"}

    return {
        "code": code,
        "count": len(bars),
        "last_close": bars[-1].close,
        "recent": _clip_series([_bar_to_dict(b) for b in bars]),
        "source": ctx.provider.name,
        "as_of": ctx.as_of.isoformat(),
    }


def _market_fundamentals(ctx: ToolContext, args: dict) -> dict:
    code = str(args.get("code") or "").strip()
    if not code:
        return {"error": "缺少参数 code"}
    period = str(args.get("period") or f"{ctx.as_of.year}Q{(ctx.as_of.month - 1) // 3 or 4}")

    try:
        data = ctx.provider.fundamentals([code], period).get(code)
    except ProviderError as exc:
        return {"error": f"取财务数据失败：{exc}"}

    if data is None:
        return {"error": f"{code} 无财务数据（period={period}）"}

    return {"code": code, "period": period, **data.model_dump()}


def _market_announcements(ctx: ToolContext, args: dict) -> dict:
    code = str(args.get("code") or "").strip()
    days = int(args.get("days") or 90)
    if not code:
        return {"error": "缺少参数 code"}

    try:
        items = ctx.provider.announcements([code], days=days)
    except ProviderError as exc:
        return {"error": f"取公告失败：{exc}"}

    return {
        "code": code,
        "count": len(items),
        "items": [
            {"date": a.date.isoformat(), "type": a.type, "title": a.title}
            for a in items[:MAX_SERIES_ROWS]
        ],
    }


def _market_breadth(ctx: ToolContext, args: dict) -> dict:
    raw_date = args.get("date")
    on = ctx.as_of
    if raw_date:
        try:
            on = date.fromisoformat(str(raw_date)[:10])
        except ValueError:
            return {"error": f"日期格式不合法：{raw_date}"}

    try:
        breadth = ctx.provider.market_breadth(on)
    except ProviderError as exc:
        return {"error": f"取市场宽度失败：{exc}"}

    return {"date": on.isoformat(), **breadth.model_dump()}


def _calc_indicators(ctx: ToolContext, args: dict) -> dict:
    code = str(args.get("code") or "").strip()
    window = int(args.get("window") or 20)
    if not code:
        return {"error": "缺少参数 code"}

    try:
        bars = ctx.provider.quotes([code], ctx.as_of - timedelta(days=window * 3), ctx.as_of).get(code) or []
    except ProviderError as exc:
        return {"error": f"取行情失败：{exc}"}

    closes = [b.close for b in bars]
    volumes = [b.volume for b in bars]
    if len(closes) < 6:
        return {"error": f"{code} 数据不足，无法计算指标"}

    def ma(n: int) -> float | None:
        return round(mean(closes[-n:]), 4) if len(closes) >= n else None

    def pct(n: int) -> float | None:
        if len(closes) <= n or not closes[-1 - n]:
            return None
        return round(closes[-1] / closes[-1 - n] - 1, 4)

    avg_vol = mean(volumes[-6:-1]) if len(volumes) >= 6 else 0
    return {
        "code": code,
        "last_close": closes[-1],
        "ma5": ma(5),
        "ma10": ma(10),
        "ma20": ma(20),
        "ret5": pct(5),
        "ret20": pct(20),
        "volume_ratio": round(volumes[-1] / avg_vol, 3) if avg_vol else None,
        "window": window,
    }


def _calc_score(ctx: ToolContext, args: dict) -> dict:
    def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
        return max(lo, min(hi, value))

    def pe_score(pe: float) -> float:
        if pe <= 0:
            return 0.3
        if pe <= 15:
            return 1.0
        if pe <= 25:
            return 0.7
        if pe <= 40:
            return 0.4
        return 0.1

    def roe_score(roe: float) -> float:
        if roe >= 0.20:
            return 1.0
        if roe >= 0.12:
            return 0.7
        if roe >= 0.06:
            return 0.4
        return 0.1

    def growth_score(g: float) -> float:
        if g >= 0.20:
            return 1.0
        if g >= 0.05:
            return 0.6
        if g >= 0:
            return 0.4
        return 0.1

    try:
        pe = float(args["pe"])
        roe = float(args["roe"])
        growth = float(args["growth"])
    except (KeyError, TypeError, ValueError):
        return {"error": "pe / roe / growth 三个参数都必须提供数值"}

    parts = {
        "pe": round(pe_score(pe), 3),
        "roe": round(roe_score(roe), 3),
        "growth": round(growth_score(growth), 3),
    }
    score = 0.4 * parts["pe"] + 0.3 * parts["roe"] + 0.3 * parts["growth"]
    return {"score": round(clamp(score), 3), "components": parts, "weights": {"pe": 0.4, "roe": 0.3, "growth": 0.3}}


def _llm_complete(ctx: ToolContext, args: dict) -> dict:
    prompt = str(args.get("prompt") or "").strip()
    if not prompt:
        return {"error": "缺少参数 prompt"}

    llm = get_llm(tier="cheap")
    try:
        result = llm.complete(
            system="你是投研助手，回答要具体、可核对，不确定就说不确定。",
            user=prompt[:4000],
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": f"模型调用失败：{exc}"}

    return {"text": result.text[:4000], "model": llm.model, "tokens": result.tokens}


def _report_write(ctx: ToolContext, args: dict) -> dict:
    title = str(args.get("title") or "未命名报告").strip()
    body = str(args.get("body") or "").strip()
    if not body:
        return {"error": "缺少参数 body"}

    try:
        ctx.reports_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^\w\u4e00-\u9fa5]+", "-", title)[:40] or "report"
        path = ctx.reports_dir / f"{ctx.as_of.isoformat()}-{slug}.md"
        path.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
    except OSError as exc:
        return {"error": f"写文件失败：{exc}"}

    return {"saved": True, "path": str(path), "bytes": len(body)}


def _zvt_kline(_ctx: ToolContext, args: dict[str, Any]) -> dict:
    code = str(args.get("code") or "").strip()
    if not code:
        return {"error": "缺少参数 code"}
    days = int(args.get("days") or 60)

    from app.data.zvt_local import default_store

    try:
        data = default_store().kline(code, days)
    except RuntimeError as exc:
        return {"error": str(exc)}

    # 只回尾部若干根，防止一次把 60 天全塞进上下文
    bars = data.pop("bars", [])
    data["bars_tail"] = bars[-12:]
    return data


def _zvt_limit_board(_ctx: ToolContext, args: dict[str, Any]) -> dict:
    from app.data.zvt_local import default_store, parse_date

    store = default_store()
    try:
        on = store.resolve_date(parse_date(args.get("date")))
        return store.limit_board(on)
    except RuntimeError as exc:
        return {"error": str(exc)}


def _zvt_breadth(_ctx: ToolContext, args: dict[str, Any]) -> dict:
    from app.data.zvt_local import default_store, parse_date

    store = default_store()
    try:
        on = store.resolve_date(parse_date(args.get("date")))
        return store.breadth(on)
    except RuntimeError as exc:
        return {"error": str(exc)}


HANDLERS = {
    "market.quotes": _market_quotes,
    "market.fundamentals": _market_fundamentals,
    "market.announcements": _market_announcements,
    "market.breadth": _market_breadth,
    "zvt.kline": _zvt_kline,
    "zvt.limit_board": _zvt_limit_board,
    "zvt.breadth": _zvt_breadth,
    "calc.indicators": _calc_indicators,
    "calc.score": _calc_score,
    "llm.complete": _llm_complete,
    "report.write": _report_write,
}


def execute_tool(ctx: ToolContext, key: str, args: dict[str, Any]) -> dict:
    """执行一个工具，永远返回可 JSON 序列化的 dict（失败也在 dict 里说明）。"""
    handler = HANDLERS.get(key)
    if handler is None:
        result = {"error": f"未知工具 {key}"}
    else:
        try:
            result = handler(ctx, args or {})
        except Exception as exc:  # noqa: BLE001 - 工具失败不应中断整条链路
            log.warning("tool %s crashed: %s", key, exc)
            result = {"error": f"{key} 执行失败：{exc}"}

    ctx.calls.append({"tool": key, "args": args, "result": _truncate(result)})
    return result


def _truncate(payload: Any, limit: int = 1200) -> Any:
    """给 trace 用的轻量副本，避免把大对象塞进运行记录。"""
    text = json.dumps(payload, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return payload
    return {"preview": text[:limit] + "…", "truncated": True}
