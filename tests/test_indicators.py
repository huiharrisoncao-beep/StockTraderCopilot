"""Hand-checked indicators. No network."""

from __future__ import annotations

import pandas as pd

from trader.indicators.trend import add_indicators


def test_ma_return_and_zero_volume_ratio() -> None:
    closes = [float(day) for day in range(1, 61)]
    volumes = [1.0] * 59 + [2.0]
    frame = pd.DataFrame(
        {
            "symbol": ["000001"] * 60,
            "trade_date": [f"2026-01-{day:02d}" for day in range(1, 61)],
            "high": closes,
            "close": closes,
            "volume": volumes,
        }
    )
    latest = add_indicators(frame).iloc[-1]
    assert latest["ma20"] == 50.5
    assert latest["ma60"] == 30.5
    assert latest["return_20d"] == 60 / 40 - 1
    assert latest["volume_ratio"] == 2 / 1.05
    assert latest["high_60d"] == 60
    assert latest["distance_to_high_60d"] == 0

    zero = frame.copy()
    zero["volume"] = 0.0
    assert add_indicators(zero).iloc[-1]["volume_ratio"] == 0.0
