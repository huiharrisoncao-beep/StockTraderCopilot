"""Bar checks that run before indicators. One bad stock does not fail the market."""

from __future__ import annotations

import math

import pandas as pd

ADJUSTMENT = "qfq"


def prepare_symbol(frame: pd.DataFrame) -> tuple[pd.DataFrame | None, str | None]:
    """Return a clean frame, or None plus a screening reason code."""
    if frame.empty:
        return None, "DATA_INCOMPLETE"
    dates = frame["trade_date"].astype(str)
    if dates.duplicated().any() or not dates.is_monotonic_increasing:
        return None, "DATA_INCOMPLETE"
    if frame["adjustment"].astype(str).ne(ADJUSTMENT).any():
        return None, "DATA_INCOMPLETE"
    close = pd.to_numeric(frame["close"], errors="coerce")
    volume = pd.to_numeric(frame["volume"], errors="coerce")
    if close.isna().any() or not close.map(_finite_positive).all():
        return None, "DATA_INCOMPLETE"
    if volume.isna().any() or not volume.map(_finite_non_negative).all():
        return None, "DATA_INCOMPLETE"
    cleaned = frame.copy()
    cleaned["close"] = close
    cleaned["volume"] = volume
    cleaned["trade_date"] = dates
    return cleaned.sort_values("trade_date"), None


def _finite_positive(value: float) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def _finite_non_negative(value: float) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value) and value >= 0
