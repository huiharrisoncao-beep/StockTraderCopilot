"""Rule hits only. Warnings are not sell instructions."""

from __future__ import annotations

import math
from datetime import date
from typing import Any

import pandas as pd

RUN_SYMBOL = "*"
PRICE_FIELDS = ("close", "ma20", "ma60", "return_20d", "volume_ratio")


def evaluate(
    cards: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    indicated: pd.DataFrame,
    data_date: str,
    today: date,
) -> list[dict[str, str]]:
    flags = [_completeness(card) for card in cards]
    flags.extend(_symbol_flags(candidates, indicated, data_date))
    flags.extend(_run_flags(candidates, data_date, today))
    present = [flag for flag in flags if flag is not None]
    present.sort(key=lambda item: (0 if item["severity"] == "block" else 1, item["symbol"], item["code"]))
    return present


def blocked_symbols(cards: list[dict[str, Any]], flags: list[dict[str, str]]) -> list[str]:
    blocked = {flag["symbol"] for flag in flags if flag["severity"] == "block"}
    return [card["symbol"] for card in cards if card["symbol"] in blocked]


def focus_symbols(cards: list[dict[str, Any]], flags: list[dict[str, str]]) -> list[str]:
    blocked = set(blocked_symbols(cards, flags))
    return [card["symbol"] for card in cards if card["symbol"] not in blocked]


def _completeness(card: dict[str, Any]) -> dict[str, str] | None:
    missing = [str(name) for name in card.get("missing_fields") or []]
    if not missing:
        missing = [name for name in PRICE_FIELDS if card.get(name) is None]
    if not missing:
        return None
    return {
        "symbol": str(card["symbol"]),
        "code": "DATA_INCOMPLETE",
        "severity": "block",
        "message": "研究卡缺少价格或指标: " + ",".join(missing),
    }


def _symbol_flags(
    candidates: list[dict[str, Any]],
    indicated: pd.DataFrame,
    data_date: str,
) -> list[dict[str, str] | None]:
    flags: list[dict[str, str] | None] = []
    for row in candidates:
        symbol = str(row["symbol"])
        history = _history(indicated, symbol, data_date)
        flags.append(_trend(symbol, row, history))
        flags.append(_move(symbol, row, history))
    return flags


def _run_flags(candidates: list[dict[str, Any]], data_date: str, today: date) -> list[dict[str, str] | None]:
    return [_industry(candidates[:5]), _stale(data_date, today)]


def _trend(symbol: str, row: dict[str, Any], history: pd.DataFrame) -> dict[str, str] | None:
    close = _num(row.get("close"))
    ma20 = _num(row.get("ma20"))
    reasons: list[str] = []
    if close is not None and ma20 is not None and close < ma20:
        reasons.append("收盘低于 MA20")
    if len(history) >= 6 and {"ma20"}.issubset(history.columns):
        latest = _num(history.iloc[-1].get("ma20"))
        prior = _num(history.iloc[-6].get("ma20"))
        if latest is not None and prior is not None and latest < prior:
            reasons.append("MA20 低于 5 个交易日前")
    if not reasons:
        return None
    return {
        "symbol": symbol,
        "code": "TREND_WEAKENING",
        "severity": "warn",
        "message": "趋势走弱: " + "；".join(reasons) + "。这不是卖出建议。",
    }


def _move(symbol: str, row: dict[str, Any], history: pd.DataFrame) -> dict[str, str] | None:
    reasons: list[str] = []
    return_20d = _num(row.get("return_20d"))
    if return_20d is not None and abs(return_20d) > 0.40:
        reasons.append("20日收益率绝对值大于 40%")
    if len(history) >= 21 and "close" in history.columns:
        closes = pd.to_numeric(history["close"], errors="coerce").tail(21)
        changes = closes.pct_change().dropna()
        if not changes.empty and bool((changes.abs() > 0.09).any()):
            reasons.append("窗口内出现单日涨跌幅绝对值大于 9%")
    if not reasons:
        return None
    return {
        "symbol": symbol,
        "code": "ABNORMAL_MOVE",
        "severity": "warn",
        "message": "异常波动: " + "；".join(reasons) + "。这不是卖出建议。",
    }


def _industry(top: list[dict[str, Any]]) -> dict[str, str] | None:
    counts: dict[str, int] = {}
    for row in top:
        industry = row.get("industry")
        if not isinstance(industry, str) or not industry.strip():
            continue
        counts[industry] = counts.get(industry, 0) + 1
    crowded = sorted(name for name, count in counts.items() if count >= 3)
    if not crowded:
        return None
    return {
        "symbol": RUN_SYMBOL,
        "code": "INDUSTRY_CONCENTRATION",
        "severity": "warn",
        "message": "前 5 名候选中同一行业不少于 3 只: " + ",".join(crowded) + "。这不是卖出建议。",
    }


def _stale(data_date: str, today: date) -> dict[str, str] | None:
    try:
        sample = date.fromisoformat(data_date)
    except ValueError:
        return None
    if (today - sample).days <= 5:
        return None
    return {
        "symbol": RUN_SYMBOL,
        "code": "STALE_SAMPLE",
        "severity": "warn",
        "message": f"数据日期 {data_date} 距离生成日超过 5 个自然日，不是最新交易日。这不是卖出建议。",
    }


def _history(frame: pd.DataFrame, symbol: str, data_date: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    group = frame[frame["symbol"].astype(str).eq(symbol) & frame["trade_date"].astype(str).le(data_date)]
    return group.sort_values("trade_date")


def _num(value: Any) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    if not math.isfinite(float(value)):
        return None
    return float(value)
