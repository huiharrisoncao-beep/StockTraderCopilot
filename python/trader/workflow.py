"""Stepwise research after a screening run has already been stored."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from trader.contracts import INVALID_ARGUMENT, TraderError, envelope, error_body, now_shanghai
from trader.indicators.trend import add_indicators
from trader.reporting.render import DISCLAIMER, industry_distribution, write_report
from trader.research.cards import build_cards
from trader.risk.checks import blocked_symbols, evaluate, focus_symbols
from trader.store.sqlite_store import (
    connect,
    load_bars,
    load_research,
    load_risk,
    load_run,
    save_report,
    save_research,
    save_risk,
)

RUN_ID = re.compile(r"research-\d{8}-\d{6}")
SYMBOL = re.compile(r"\d{6}")
SQLITE_SOURCE = {"provider": "sqlite", "dataset": "data/trader.sqlite", "adjustment": "qfq"}


def research_payload(run_id: str, symbols: list[str] | None) -> dict[str, Any]:
    _require_run_id(run_id)
    parsed = _parse_symbols(symbols)
    with connect() as conn:
        found = _require_run(conn, run_id)
        screening = found["screening"]
        indicated = _indicated(conn, [str(row["symbol"]) for row in screening["candidates"]])
        cards = build_cards(
            screening["candidates"],
            indicated,
            found["data_date"],
            parsed,
            str(screening.get("rule_set") or ""),
        )
        save_research(conn, run_id, cards)
    warnings = ["研究卡只展开筛选结果，不补充财务、新闻或资金流。"]
    if not cards:
        warnings.append("本次没有候选，研究卡为空。")
    elif parsed is None and len(screening["candidates"]) > len(cards):
        warnings.append("只展开前 5 名候选。")
    return _ok(
        "get_stock_research_data",
        found,
        {"rule_set": screening.get("rule_set"), "cards": cards, "symbols": [card["symbol"] for card in cards]},
        warnings,
    )


def risk_payload(run_id: str) -> dict[str, Any]:
    _require_run_id(run_id)
    with connect() as conn:
        found = _require_run(conn, run_id)
        cards = load_research(conn, run_id)
        if not cards and found["screening"]["candidates"]:
            raise TraderError(INVALID_ARGUMENT, "先调用 get_stock_research_data")
        symbols = [str(row["symbol"]) for row in found["screening"]["candidates"]]
        indicated = _indicated(conn, symbols)
        flags = evaluate(cards, found["screening"]["candidates"], indicated, found["data_date"], now_shanghai().date())
        save_risk(conn, run_id, flags)
    warnings = ["风险结果是规则命中，不是卖出建议。"]
    if any(flag["code"] == "STALE_SAMPLE" for flag in flags):
        warnings.append("样本距离生成日超过 5 个自然日。")
    return _ok(
        "check_stock_risk",
        found,
        {
            "flags": flags,
            "blocked_symbols": blocked_symbols(cards, flags),
            "focus_symbols": focus_symbols(cards, flags),
        },
        warnings,
    )


def report_payload(run_id: str) -> dict[str, Any]:
    _require_run_id(run_id)
    generated = now_shanghai()
    with connect() as conn:
        found = _require_run(conn, run_id)
        cards = load_research(conn, run_id)
        flags = load_risk(conn, run_id)
        context = {
            "run_id": run_id,
            "data_date": found["data_date"],
            "generated_at": generated.isoformat(timespec="seconds"),
            "universe": found.get("universe"),
            "source": found.get("source") or SQLITE_SOURCE,
            "market": found["market"],
            "screening": found["screening"],
            "cards": cards,
            "flags": flags,
        }
        try:
            markdown_path, json_path = write_report(context)
        except TraderError as exc:
            exc.run_id = run_id
            exc.data_date = found["data_date"]
            raise
        save_report(conn, run_id, markdown_path, json_path, context["generated_at"])
    warnings = [
        "本地历史样本，不是实时行情。",
        "报告表格由 Python 生成。解释时不要改写表中的数字。",
    ]
    return _ok(
        "generate_daily_report",
        found,
        {
            "markdown_path": markdown_path,
            "json_path": json_path,
            "disclaimer": DISCLAIMER,
            "market": found["market"],
            "screening": found["screening"],
            "cards": cards,
            "flags": flags,
            "industry_distribution": industry_distribution(found["screening"].get("candidates", [])),
            "focus_symbols": focus_symbols(cards, flags),
            "blocked_symbols": blocked_symbols(cards, flags),
        },
        warnings,
        generated_at=generated,
    )


def failure_envelope(tool: str, exc: TraderError) -> dict[str, Any]:
    return envelope(
        ok=False,
        tool=tool,
        run_id=exc.run_id,
        data_date=exc.data_date,
        source=SQLITE_SOURCE,
        data=None,
        error=error_body(exc),
    )


def _ok(
    tool: str,
    found: dict[str, Any],
    data: dict[str, Any],
    warnings: list[str],
    generated_at: Any = None,
) -> dict[str, Any]:
    return envelope(
        ok=True,
        tool=tool,
        run_id=found.get("run_id_value"),
        data_date=found["data_date"],
        source=found.get("source") or SQLITE_SOURCE,
        data=data,
        warnings=warnings,
        error=None,
        generated_at=generated_at,
    )


def _require_run_id(run_id: str) -> None:
    if RUN_ID.fullmatch(run_id) is None:
        raise TraderError(INVALID_ARGUMENT, "run_id 必须来自上一步，格式 research-YYYYMMDD-HHMMSS")


def _parse_symbols(symbols: list[str] | None) -> list[str] | None:
    if symbols is None:
        return None
    if any(SYMBOL.fullmatch(symbol) is None for symbol in symbols):
        raise TraderError(INVALID_ARGUMENT, "symbols 必须是 6 位代码")
    return symbols


def _require_run(conn: Any, run_id: str) -> dict[str, Any]:
    found = load_run(conn, run_id)
    if found is None:
        raise TraderError(INVALID_ARGUMENT, f"找不到 run_id {run_id}")
    found["run_id_value"] = run_id
    if not found.get("source"):
        found["source"] = dict(SQLITE_SOURCE)
    return found


def _indicated(conn: Any, symbols: list[str]) -> pd.DataFrame:
    bars = load_bars(conn, symbols)
    if bars.empty:
        return bars
    return add_indicators(bars)
