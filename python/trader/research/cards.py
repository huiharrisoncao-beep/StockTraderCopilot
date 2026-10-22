"""Expand screening rows into research cards. No opinions and no outside data."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from trader.contracts import INVALID_ARGUMENT, TraderError

RESEARCH_LIMIT = 5
UNAVAILABLE_FIELDS = ["valuation", "news", "fund_flow"]
REQUIRED_FIELDS = (
    "close",
    "ma20",
    "ma60",
    "return_20d",
    "volume_ratio",
    "distance_to_high_60d",
    "closes_above_ma20_ratio",
)


def select_candidates(candidates: list[dict[str, Any]], symbols: list[str] | None) -> list[dict[str, Any]]:
    if symbols is None:
        return list(candidates[:RESEARCH_LIMIT])
    if not symbols or len(symbols) > RESEARCH_LIMIT:
        raise TraderError(INVALID_ARGUMENT, "symbols 必须是 1 到 5 只本次候选")
    if len(symbols) != len(set(symbols)):
        raise TraderError(INVALID_ARGUMENT, "symbols 不能重复")
    by_symbol = {str(row["symbol"]): row for row in candidates}
    missing = [symbol for symbol in symbols if symbol not in by_symbol]
    if missing:
        raise TraderError(INVALID_ARGUMENT, "代码不在本次候选中: " + ",".join(missing))
    return [by_symbol[symbol] for symbol in symbols]


def build_cards(
    candidates: list[dict[str, Any]],
    indicated: pd.DataFrame,
    data_date: str,
    symbols: list[str] | None,
    rule_set: str,
) -> list[dict[str, Any]]:
    chosen = select_candidates(candidates, symbols)
    cards: list[dict[str, Any]] = []
    for row in chosen:
        symbol = str(row["symbol"])
        ratio = _above_ma20_ratio(indicated, symbol, data_date)
        card = {
            "symbol": symbol,
            "name": row.get("name"),
            "industry": row.get("industry"),
            "data_date": data_date,
            "close": _num(row.get("close")),
            "ma20": _num(row.get("ma20")),
            "ma60": _num(row.get("ma60")),
            "return_20d": _num(row.get("return_20d")),
            "volume_ratio": _num(row.get("volume_ratio")),
            "distance_to_high_60d": _num(row.get("distance_to_high_60d")),
            "rule_set": rule_set,
            "closes_above_ma20_ratio": ratio,
            "valuation": None,
            "news": None,
            "fund_flow": None,
        }
        card["missing_fields"] = [name for name in REQUIRED_FIELDS if card.get(name) is None]
        card["unavailable_fields"] = list(UNAVAILABLE_FIELDS)
        cards.append(card)
    return cards


def _above_ma20_ratio(frame: pd.DataFrame, symbol: str, data_date: str) -> float | None:
    if frame.empty or "ma20" not in frame.columns:
        return None
    group = frame[frame["symbol"].astype(str).eq(symbol) & frame["trade_date"].astype(str).le(data_date)]
    window = group.sort_values("trade_date").tail(20)
    if len(window) < 20:
        return None
    closes = pd.to_numeric(window["close"], errors="coerce")
    averages = pd.to_numeric(window["ma20"], errors="coerce")
    if closes.isna().any() or averages.isna().any():
        return None
    return round(float((closes > averages).mean()), 6)


def _num(value: Any) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    if not math.isfinite(float(value)):
        return None
    return float(value)
