"""Risk rules. No network."""

from __future__ import annotations

from datetime import date

import pandas as pd

from trader.risk.checks import evaluate


def _card(symbol: str, **overrides: object) -> dict:
    card = {
        "symbol": symbol,
        "name": symbol,
        "industry": "银行",
        "close": 13.0,
        "ma20": 12.0,
        "ma60": 11.0,
        "return_20d": 0.1,
        "volume_ratio": 1.5,
        "distance_to_high_60d": -0.01,
        "closes_above_ma20_ratio": 0.8,
        "missing_fields": [],
    }
    card.update(overrides)
    return card


def _history(symbol: str, closes: list[float], ma20: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": [symbol] * len(closes),
            "trade_date": [f"2026-08-{index + 1:02d}" for index in range(len(closes))],
            "close": closes,
            "ma20": ma20,
        }
    )


def test_missing_price_blocks() -> None:
    card = _card("600519", close=None, missing_fields=["close"])
    flags = evaluate([card], [card], pd.DataFrame(), "2026-10-21", date(2026, 10, 22))
    blocked = [flag for flag in flags if flag["symbol"] == "600519" and flag["severity"] == "block"]
    assert blocked[0]["code"] == "DATA_INCOMPLETE"


def test_industry_concentration_needs_three_named_industries() -> None:
    top = [_card(f"60000{index}", industry="银行") for index in range(3)]
    top.extend(_card(f"60001{index}", industry="医药") for index in range(2))
    flags = evaluate([], top, pd.DataFrame(), "2026-10-21", date(2026, 10, 22))
    assert any(flag["code"] == "INDUSTRY_CONCENTRATION" and flag["severity"] == "warn" for flag in flags)

    blank = [_card(f"60000{index}", industry=None) for index in range(5)]
    quiet = evaluate([], blank, pd.DataFrame(), "2026-10-21", date(2026, 10, 22))
    assert all(flag["code"] != "INDUSTRY_CONCENTRATION" for flag in quiet)


def test_stale_sample_uses_calendar_days() -> None:
    fresh = evaluate([], [], pd.DataFrame(), "2026-10-21", date(2026, 10, 22))
    assert all(flag["code"] != "STALE_SAMPLE" for flag in fresh)
    stale = evaluate([], [], pd.DataFrame(), "2026-10-15", date(2026, 10, 21))
    assert any(flag["code"] == "STALE_SAMPLE" for flag in stale)


def test_large_daily_move_warns_without_blocking() -> None:
    closes = [10.0] * 20 + [12.0]
    history = _history("600519", closes, [9.0] * 21)
    flags = evaluate([], [_card("600519")], history, "2026-08-21", date(2026, 8, 21))
    moves = [flag for flag in flags if flag["code"] == "ABNORMAL_MOVE"]
    assert moves and moves[0]["severity"] == "warn"
    assert all(flag["severity"] != "block" for flag in flags)
