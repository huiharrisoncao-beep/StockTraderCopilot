"""Capture a real AKShare sample and write the demo fixture. Not used by tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from trader.contracts import TraderError, now_shanghai
from trader.data.akshare_source import (
    ADJUSTMENT,
    HIST_INTERFACE,
    INDEX_DAILY_INTERFACE,
    INDEXES,
    SINA_SPOT_INTERFACE,
    SPOT_INTERFACE,
    TX_HIST_INTERFACE,
    akshare_version,
    detect_bar_backend,
    detect_index_backend,
    fetch_daily_bars,
    fetch_index_daily,
    load_spot,
    select_liquid_universe,
)
from trader.paths import data_dir, fixture_root


def freeze_fixture(limit: int = 150, start_date: str = "20260101") -> Path:
    captured = now_shanghai()
    end_date = captured.strftime("%Y%m%d")
    bar_backend = detect_bar_backend(start_date, end_date)
    index_backend = detect_index_backend(start_date, end_date)
    spot, spot_scope = load_spot()
    universe = select_liquid_universe(spot, limit=limit)
    if len(universe) < 100:
        raise TraderError("EMPTY_UNIVERSE", f"流动性股票池只有 {len(universe)} 只，少于 100")
    frames: list[pd.DataFrame] = []
    failures: list[str] = []
    symbols = list(universe["symbol"])
    for index, symbol in enumerate(symbols, start=1):
        try:
            frames.append(fetch_daily_bars(symbol, start_date, end_date, backend=bar_backend))
        except TraderError:
            failures.append(symbol)
        if index == 1 or index % 25 == 0 or index == len(symbols):
            print(f"freeze bars {index}/{len(symbols)}", file=sys.stderr)
    if not frames:
        raise TraderError("DATA_SOURCE_UNAVAILABLE", "没有抓到任何日线", retryable=True)
    bars = pd.concat(frames, ignore_index=True)
    data_date = str(bars["trade_date"].max())
    kept_symbols = set(bars["symbol"])
    universe = universe[universe["symbol"].isin(kept_symbols)].copy()
    if len(universe) < 100:
        raise TraderError("EMPTY_UNIVERSE", f"成功抓取的股票只有 {len(universe)} 只，少于 100")
    market = _market(
        start_date,
        end_date,
        data_date,
        spot,
        universe["symbol"],
        spot_scope,
        index_backend,
    )
    volume_unit = "手" if bar_backend == "eastmoney" else "股"
    hist_interface = HIST_INTERFACE if bar_backend == "eastmoney" else TX_HIST_INTERFACE
    index_interface = INDEX_DAILY_INTERFACE if index_backend == "eastmoney" else TX_HIST_INTERFACE
    spot_interface = SINA_SPOT_INTERFACE if spot_scope == "sina_amount_page" else SPOT_INTERFACE
    dataset_name = "demo-" + data_date.replace("-", "")
    target = fixture_root() / dataset_name
    target.mkdir(parents=True, exist_ok=True)
    raw_dir = data_dir() / "raw" / data_date.replace("-", "")
    raw_dir.mkdir(parents=True, exist_ok=True)
    spot.head(limit).to_csv(raw_dir / "spot-head.csv", index=False)
    universe.to_csv(target / "universe.csv", index=False)
    universe.to_csv(data_dir() / "universe" / "demo.csv", index=False)
    bars.to_csv(target / "bars.csv", index=False)
    (target / "industry.csv").write_text("symbol,industry\n", encoding="utf-8")
    (target / "market.json").write_text(json.dumps(market, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "dataset": dataset_name,
        "provider": "akshare",
        "akshare_version": akshare_version(),
        "akshare_interfaces": [hist_interface, index_interface, spot_interface],
        "bar_backend": bar_backend,
        "index_backend": index_backend,
        "spot_scope": spot_scope,
        "captured_at": captured.isoformat(timespec="seconds"),
        "data_date": data_date,
        "adjustment": ADJUSTMENT,
        "volume_unit": volume_unit,
        "volume_note": (
            "AKShare stock_zh_a_hist 的成交量单位是手"
            if bar_backend == "eastmoney"
            else "AKShare stock_zh_a_hist_tx 的成交量单位是股。量比在同一单位内计算。"
        ),
        "universe": "demo",
        "symbols": int(len(universe)),
        "failed_symbols": failures,
        "is_live": False,
        "note": "截至该交易日收盘的历史样本，不是实时行情",
    }
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (fixture_root() / "current.json").write_text(
        json.dumps({"demo": dataset_name}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def _market(
    start_date: str,
    end_date: str,
    data_date: str,
    spot: pd.DataFrame,
    symbols: pd.Series,
    spot_scope: str,
    index_backend: str,
) -> dict:
    indexes = []
    for source_symbol, code, name in INDEXES:
        frame = fetch_index_daily(source_symbol, start_date, end_date, backend=index_backend)
        normalized = _normalize_index(frame)
        row = normalized[normalized["trade_date"].eq(data_date)]
        if row.empty:
            row = normalized.tail(1)
        latest = row.iloc[-1]
        previous = normalized[normalized["trade_date"].lt(str(latest["trade_date"]))]
        prev_close = float(previous.iloc[-1]["close"]) if not previous.empty else None
        close = float(latest["close"])
        change_pct = None if prev_close in (None, 0) else round(close / prev_close - 1, 6)
        indexes.append(
            {
                "code": code,
                "name": name,
                "close": round(close, 4),
                "change_pct": change_pct,
                "amount": None if pd.isna(latest["amount"]) else round(float(latest["amount"]), 2),
            }
        )
    spot = spot.copy()
    spot["代码"] = spot["代码"].astype(str).str.zfill(6)
    change = pd.to_numeric(spot["涨跌幅"], errors="coerce")
    breadth_scope = "all_a_spot"
    if change.notna().sum() < 1000:
        member = spot[spot["代码"].isin(set(symbols))]
        change = pd.to_numeric(member["涨跌幅"], errors="coerce")
        breadth_scope = "demo_universe"
    return {
        "data_date": data_date,
        "indices": indexes,
        "advance_count": int((change > 0).sum()),
        "decline_count": int((change < 0).sum()),
        "flat_count": int((change == 0).sum()),
        "breadth_scope": breadth_scope,
        "spot_scope": spot_scope,
        "breadth_note": "涨跌家数来自抓取时的 AKShare 行情快照，不是指数官方统计。",
    }


def _normalize_index(frame: pd.DataFrame) -> pd.DataFrame:
    columns = {column.lower(): column for column in frame.columns}
    date_col = columns.get("date", columns.get("日期"))
    close_col = columns.get("close", columns.get("收盘"))
    amount_col = columns.get("amount", columns.get("成交额"))
    if date_col is None or close_col is None:
        raise TraderError("DATA_QUALITY_FAILED", f"指数日线缺少日期或收盘价: {list(frame.columns)}")
    out = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(frame[date_col]).dt.strftime("%Y-%m-%d"),
            "close": pd.to_numeric(frame[close_col], errors="coerce"),
            "amount": pd.to_numeric(frame[amount_col], errors="coerce") if amount_col else None,
        }
    )
    return out.dropna(subset=["close"]).sort_values("trade_date")
