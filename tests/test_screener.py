"""Rule boundaries for trend_volume_v1. No network."""

from __future__ import annotations

import pandas as pd

from trader.data.quality import prepare_symbol
from trader.screening.screener import screen


def _frame(symbol: str, **latest: float) -> pd.DataFrame:
    rows = []
    for offset in range(59):
        rows.append(
            {
                "symbol": symbol,
                "trade_date": f"2026-07-{offset + 1:02d}",
                "close": 10.0,
                "ma20": 9.0,
                "ma60": 8.0,
                "return_20d": 0.1,
                "volume_ratio": 1.5,
                "high_60d": 11.0,
                "distance_to_high_60d": -0.1,
            }
        )
    rows.append(
        {
            "symbol": symbol,
            "trade_date": "2026-10-21",
            "close": latest.get("close", 12.0),
            "ma20": latest.get("ma20", 11.0),
            "ma60": latest.get("ma60", 10.0),
            "return_20d": latest.get("return_20d", 0.1),
            "volume_ratio": latest.get("volume_ratio", 1.5),
            "high_60d": 12.0,
            "distance_to_high_60d": 0.0,
        }
    )
    return pd.DataFrame(rows)


def _reason(frame: pd.DataFrame) -> str | None:
    result = screen(frame, {frame.iloc[0]["symbol"]: "测试"}, {}, "2026-10-21")
    if result["candidates"]:
        return None
    return result["exclusions"][0]["reason"]


def test_inclusive_boundaries_pass() -> None:
    low = _frame("000001", return_20d=0.05, volume_ratio=1.2)
    high = _frame("000002", return_20d=0.40, volume_ratio=3.0)
    result = screen(pd.concat([low, high]), {"000001": "甲", "000002": "乙"}, {}, "2026-10-21")
    assert [row["symbol"] for row in result["candidates"]] == ["000002", "000001"]


def test_boundary_failures_keep_reason_codes() -> None:
    assert _reason(_frame("000001", return_20d=0.049999)) == "RETURN_OUT_OF_RANGE"
    assert _reason(_frame("000001", return_20d=0.400001)) == "RETURN_OUT_OF_RANGE"
    assert _reason(_frame("000001", volume_ratio=1.199999)) == "VOLUME_OUT_OF_RANGE"
    assert _reason(_frame("000001", volume_ratio=3.000001)) == "VOLUME_OUT_OF_RANGE"
    assert _reason(_frame("000001", close=11.0, ma20=11.0)) == "TREND_NOT_ALIGNED"
    assert _reason(_frame("000001", ma20=10.0, ma60=10.0)) == "TREND_NOT_ALIGNED"
    short = _frame("000001").iloc[:59].copy()
    short.loc[short.index[-1], "trade_date"] = "2026-10-21"
    assert _reason(short) == "INSUFFICIENT_HISTORY"


def test_equal_return_sorts_by_symbol_and_caps_at_ten() -> None:
    frames = [_frame(f"{index:06d}", return_20d=0.2) for index in range(12)]
    result = screen(pd.concat(frames), {}, {}, "2026-10-21")
    assert result["eligible_count"] == 12
    assert [row["symbol"] for row in result["candidates"]] == [f"{index:06d}" for index in range(10)]


def test_missing_close_is_data_incomplete() -> None:
    frame = _frame("600519")[["symbol", "trade_date", "close"]].copy()
    frame["volume"] = 1.0
    frame["adjustment"] = "qfq"
    frame.loc[frame.index[-1], "close"] = None
    cleaned, reason = prepare_symbol(frame)
    assert cleaned is None
    assert reason == "DATA_INCOMPLETE"


def test_symbol_without_as_of_bar_is_excluded() -> None:
    stale = _frame("000001")
    stale["trade_date"] = "2026-10-20"
    result = screen(stale, {"000001": "甲"}, {}, "2026-10-21")
    assert result["candidates"] == []
    assert result["exclusions"] == [{"symbol": "000001", "reason": "DATA_INCOMPLETE"}]
