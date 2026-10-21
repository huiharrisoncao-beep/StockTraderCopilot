"""Apply trend_volume_v1 to the last bar of each symbol."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from trader.screening.rules import RULES, RULE_SET


def screen(
    frame: pd.DataFrame,
    names: dict[str, str],
    industries: dict[str, str | None],
    as_of: str,
) -> dict[str, Any]:
    exclusions: list[dict[str, str]] = []
    rows: list[dict[str, Any]] = []
    scoped = frame[frame["trade_date"].astype(str).le(as_of)]
    for symbol, group in scoped.groupby("symbol", sort=True):
        ordered = group.sort_values("trade_date")
        latest = ordered.iloc[-1]
        if str(latest["trade_date"]) != as_of:
            exclusions.append({"symbol": str(symbol), "reason": "DATA_INCOMPLETE"})
            continue
        reason = _reason(ordered, latest)
        if reason is not None:
            exclusions.append({"symbol": str(symbol), "reason": reason})
            continue
        rows.append(_row(str(symbol), latest, names, industries))
    rows.sort(key=lambda item: (-item["return_20d"], item["symbol"]))
    limit = int(RULES["candidate_limit"])
    candidates = rows[:limit]
    counts: dict[str, int] = {}
    for item in exclusions:
        counts[item["reason"]] = counts.get(item["reason"], 0) + 1
    return {
        "rule_set": RULE_SET,
        "rules": RULES,
        "candidate_count": len(candidates),
        "eligible_count": len(rows),
        "excluded_counts": counts,
        "exclusions": exclusions,
        "candidates": candidates,
    }


def _reason(ordered: pd.DataFrame, latest: pd.Series) -> str | None:
    valid = ordered["close"].map(lambda value: isinstance(value, (int, float)) and math.isfinite(value) and value > 0)
    if int(valid.sum()) < int(RULES["min_history"]):
        return "INSUFFICIENT_HISTORY"
    if not _finite(latest.get("close")) or not _finite(latest.get("ma20")) or not _finite(latest.get("ma60")):
        return "DATA_INCOMPLETE"
    if not _finite(latest.get("return_20d")) or not _finite(latest.get("volume_ratio")):
        return "DATA_INCOMPLETE"
    close = float(latest["close"])
    ma20 = float(latest["ma20"])
    ma60 = float(latest["ma60"])
    if not (close > ma20 > ma60):
        return "TREND_NOT_ALIGNED"
    return_20d = float(latest["return_20d"])
    if not (float(RULES["min_return_20d"]) <= return_20d <= float(RULES["max_return_20d"])):
        return "RETURN_OUT_OF_RANGE"
    volume_ratio = float(latest["volume_ratio"])
    if not (float(RULES["min_volume_ratio"]) <= volume_ratio <= float(RULES["max_volume_ratio"])):
        return "VOLUME_OUT_OF_RANGE"
    return None


def _row(
    symbol: str,
    latest: pd.Series,
    names: dict[str, str],
    industries: dict[str, str | None],
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "name": names.get(symbol),
        "industry": industries.get(symbol),
        "close": _round(latest["close"]),
        "ma20": _round(latest["ma20"]),
        "ma60": _round(latest["ma60"]),
        "return_20d": _round(latest["return_20d"]),
        "volume_ratio": _round(latest["volume_ratio"]),
        "high_60d": _round(latest["high_60d"]) if _finite(latest.get("high_60d")) else None,
        "distance_to_high_60d": _round(latest["distance_to_high_60d"])
        if _finite(latest.get("distance_to_high_60d"))
        else None,
    }


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _round(value: Any) -> float:
    return round(float(value), 6)
