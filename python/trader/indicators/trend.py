"""Trading-day indicators. Windows are bar counts, not calendar days."""

from __future__ import annotations

import pandas as pd


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    ordered = frame.sort_values(["symbol", "trade_date"]).copy()
    grouped = ordered.groupby("symbol", sort=False)
    ordered["ma20"] = grouped["close"].transform(lambda series: series.rolling(20, min_periods=20).mean())
    ordered["ma60"] = grouped["close"].transform(lambda series: series.rolling(60, min_periods=60).mean())
    ordered["return_20d"] = grouped["close"].transform(lambda series: series / series.shift(20) - 1)
    volume_mean = grouped["volume"].transform(lambda series: series.rolling(20, min_periods=20).mean())
    ordered["volume_ratio"] = ordered["volume"] / volume_mean
    ordered.loc[ordered["volume"].eq(0), "volume_ratio"] = 0.0
    ordered["high_60d"] = grouped["high"].transform(lambda series: series.rolling(60, min_periods=60).max())
    ordered["distance_to_high_60d"] = ordered["close"] / ordered["high_60d"] - 1
    return ordered
