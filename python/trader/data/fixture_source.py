"""Read a frozen historical sample. Fixture mode never calls the network."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from trader.contracts import (
    DATA_QUALITY_FAILED,
    DATA_SOURCE_UNAVAILABLE,
    EMPTY_UNIVERSE,
    INVALID_ARGUMENT,
    TraderError,
)
from trader.paths import current_fixture_index, fixture_root


def resolve_dataset(universe: str, explicit: str | None = None) -> Path:
    if universe != "demo":
        raise TraderError(INVALID_ARGUMENT, "Day 2 只支持 universe=demo")
    if explicit:
        path = fixture_root() / explicit
    else:
        index_path = current_fixture_index()
        if not index_path.exists():
            raise TraderError(DATA_SOURCE_UNAVAILABLE, "缺少 data/fixtures/current.json", retryable=False)
        pointer = json.loads(index_path.read_text(encoding="utf-8"))
        dataset = pointer.get("demo")
        if not dataset:
            raise TraderError(DATA_SOURCE_UNAVAILABLE, "current.json 没有 demo 数据集", retryable=False)
        path = fixture_root() / str(dataset)
    if not path.is_dir():
        raise TraderError(DATA_SOURCE_UNAVAILABLE, f"找不到样本目录 {path.name}", retryable=False)
    return path


def load_manifest(dataset: Path) -> dict[str, Any]:
    path = dataset / "manifest.json"
    if not path.exists():
        raise TraderError(DATA_QUALITY_FAILED, "样本缺少 manifest.json")
    return json.loads(path.read_text(encoding="utf-8"))


def load_universe(dataset: Path) -> pd.DataFrame:
    path = dataset / "universe.csv"
    if not path.exists():
        raise TraderError(EMPTY_UNIVERSE, "样本股票池为空")
    frame = pd.read_csv(path, dtype={"symbol": str, "name": str})
    if frame.empty:
        raise TraderError(EMPTY_UNIVERSE, "样本股票池为空")
    frame["symbol"] = frame["symbol"].str.zfill(6)
    return frame


def load_bars(dataset: Path) -> pd.DataFrame:
    path = dataset / "bars.csv"
    if not path.exists():
        raise TraderError(DATA_QUALITY_FAILED, "样本缺少 bars.csv")
    frame = pd.read_csv(path, dtype={"symbol": str})
    if frame.empty:
        raise TraderError(DATA_QUALITY_FAILED, "样本日线为空")
    frame["symbol"] = frame["symbol"].str.zfill(6)
    frame["trade_date"] = frame["trade_date"].astype(str)
    return frame.sort_values(["symbol", "trade_date"])


def load_market(dataset: Path) -> dict[str, Any]:
    path = dataset / "market.json"
    if not path.exists():
        raise TraderError(DATA_QUALITY_FAILED, "样本缺少 market.json")
    return json.loads(path.read_text(encoding="utf-8"))


def load_industry(dataset: Path) -> dict[str, str | None]:
    path = dataset / "industry.csv"
    if not path.exists():
        return {}
    frame = pd.read_csv(path, dtype={"symbol": str})
    if frame.empty:
        return {}
    frame["symbol"] = frame["symbol"].str.zfill(6)
    return {
        row.symbol: None if pd.isna(row.industry) or row.industry == "" else str(row.industry)
        for row in frame.itertuples(index=False)
    }
