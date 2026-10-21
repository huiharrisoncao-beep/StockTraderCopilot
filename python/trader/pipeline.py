"""Fixture daily research path: read, check, calculate, screen, persist."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from trader.contracts import DATA_QUALITY_FAILED, TraderError, envelope, now_shanghai
from trader.data.fixture_source import (
    load_bars,
    load_industry,
    load_manifest,
    load_market,
    load_universe,
    resolve_dataset,
)
from trader.data.quality import prepare_symbol
from trader.indicators.trend import add_indicators
from trader.paths import data_dir, project_root
from trader.screening.screener import screen
from trader.store.sqlite_store import connect, save_run


def run_daily(universe: str, data_mode: str, dataset: str | None = None) -> dict[str, Any]:
    if data_mode != "fixture":
        raise TraderError(
            "INVALID_ARGUMENT",
            "daily 命令的演示路径是 fixture。live 抓取请使用 freeze-fixture。",
        )
    dataset_path = resolve_dataset(universe, dataset)
    manifest = load_manifest(dataset_path)
    data_date = str(manifest["data_date"])
    names = _names(load_universe(dataset_path))
    industries = load_industry(dataset_path)
    market = load_market(dataset_path)
    if market.get("data_date") != data_date:
        raise TraderError(DATA_QUALITY_FAILED, "market.json 的数据日期与 manifest 不一致")
    bars, exclusions = _clean_bars(load_bars(dataset_path), set(names))
    if bars.empty:
        raise TraderError(DATA_QUALITY_FAILED, "清洗后没有可用日线")
    indicated = add_indicators(bars)
    if indicated[indicated["trade_date"].eq(data_date)].empty:
        raise TraderError(DATA_QUALITY_FAILED, f"样本没有 {data_date} 的日线")
    screening = screen(indicated, names, industries, data_date)
    screening["exclusions"].extend(exclusions)
    screening["exclusions"].sort(key=lambda item: item["symbol"])
    counts: dict[str, int] = {}
    for item in screening["exclusions"]:
        counts[item["reason"]] = counts.get(item["reason"], 0) + 1
    screening["excluded_counts"] = counts
    screening["universe_size"] = len(names)
    warnings = [
        "本地历史样本，不是实时行情。",
        "筛选规则 trend_volume_v1 只用于演示，不构成投资建议。",
    ]
    if not screening["candidates"]:
        warnings.append("规则下没有候选股票，这是合法结果。")
    generated = now_shanghai()
    run_id = "research-" + generated.strftime("%Y%m%d-%H%M%S")
    source = {
        "provider": "fixture",
        "dataset": str(dataset_path.relative_to(project_root())),
        "adjustment": manifest.get("adjustment", "qfq"),
        "note": manifest.get("note", "本地历史样本，不是实时行情"),
    }
    payload = {"market": market, "screening": screening}
    _write_json(data_date, run_id, payload)
    with connect() as conn:
        save_run(
            conn,
            run_id=run_id,
            data_date=data_date,
            universe=universe,
            data_mode=data_mode,
            created_at=generated.isoformat(timespec="seconds"),
            market=market,
            screening=screening,
            bars=bars,
        )
    return envelope(
        ok=True,
        tool="run_daily_research",
        run_id=run_id,
        data_date=data_date,
        source=source,
        data=payload,
        warnings=warnings,
        error=None,
        generated_at=generated,
    )


def _names(universe: pd.DataFrame) -> dict[str, str]:
    return {str(row.symbol): str(row.name) for row in universe.itertuples(index=False)}


def _clean_bars(frame: pd.DataFrame, symbols: set[str]) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    kept: list[pd.DataFrame] = []
    exclusions: list[dict[str, str]] = []
    seen: set[str] = set()
    for symbol, group in frame.groupby("symbol", sort=True):
        code = str(symbol)
        if code not in symbols:
            continue
        seen.add(code)
        cleaned, reason = prepare_symbol(group)
        if reason or cleaned is None:
            exclusions.append({"symbol": code, "reason": reason or "DATA_INCOMPLETE"})
            continue
        kept.append(cleaned)
    for code in sorted(symbols - seen):
        exclusions.append({"symbol": code, "reason": "DATA_INCOMPLETE"})
    if not kept:
        return frame.iloc[0:0].copy(), exclusions
    return pd.concat(kept, ignore_index=True), exclusions


def _write_json(data_date: str, run_id: str, payload: dict[str, Any]) -> None:
    target = data_dir() / "processed" / data_date
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{run_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


