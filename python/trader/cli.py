"""Research CLI. stdout is one JSON object."""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

from trader.contracts import INVALID_ARGUMENT, INTERNAL, TraderError, envelope, error_body
from trader.data.fixture_source import load_manifest, resolve_dataset
from trader.data.freeze import freeze_fixture
from trader.pipeline import run_daily
from trader.store.sqlite_store import connect, load_run
from trader.workflow import failure_envelope, report_payload, research_payload, risk_payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trader.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    daily = sub.add_parser("daily")
    _add_common(daily)
    daily.add_argument("--dataset")

    snapshot = sub.add_parser("market-snapshot")
    _add_common(snapshot)
    snapshot.add_argument("--dataset")
    snapshot.add_argument("--as-of")

    screen = sub.add_parser("screen")
    screen.add_argument("--run-id", required=True)
    screen.add_argument("--json", action="store_true")

    research = sub.add_parser("stock-research")
    research.add_argument("--run-id", required=True)
    research.add_argument("--symbols")
    research.add_argument("--json", action="store_true")

    risk = sub.add_parser("check-risk")
    risk.add_argument("--run-id", required=True)
    risk.add_argument("--json", action="store_true")

    report = sub.add_parser("report")
    report.add_argument("--run-id", required=True)
    report.add_argument("--json", action="store_true")

    freeze = sub.add_parser("freeze-fixture")
    freeze.add_argument("--limit", type=int, default=150)
    freeze.add_argument("--json", action="store_true")

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code in (0, None):
            return 0
        _emit(
            envelope(
                ok=False,
                tool="cli",
                run_id=None,
                data_date=None,
                source={"provider": None, "dataset": None, "adjustment": "qfq"},
                data=None,
                error=error_body(TraderError(INVALID_ARGUMENT, "命令参数不合法")),
            )
        )
        return 1
    try:
        if args.command == "daily":
            payload = run_daily(args.universe, args.data_mode, args.dataset)
        elif args.command == "market-snapshot":
            _reject_mismatched_as_of(args.universe, args.data_mode, args.dataset, args.as_of)
            payload = _snapshot(args.universe, args.data_mode, args.dataset)
        elif args.command == "screen":
            payload = _screen(args.run_id)
        elif args.command == "stock-research":
            payload = research_payload(args.run_id, _symbols(args.symbols))
        elif args.command == "check-risk":
            payload = risk_payload(args.run_id)
        elif args.command == "report":
            payload = report_payload(args.run_id)
        elif args.command == "freeze-fixture":
            target = freeze_fixture(limit=args.limit)
            payload = envelope(
                ok=True,
                tool="freeze_fixture",
                run_id=None,
                data_date=None,
                source={"provider": "akshare", "dataset": target.name, "adjustment": "qfq"},
                data={"dataset": target.name},
            )
        else:
            raise TraderError(INVALID_ARGUMENT, f"未知命令 {args.command}")
    except TraderError as exc:
        _emit(_failure(args.command, exc))
        return 1 if exc.code == INVALID_ARGUMENT else 2
    except Exception:
        _emit(_failure(args.command, TraderError(INTERNAL, "未分类异常")))
        return 2
    _emit(payload)
    return 0


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--universe", default="demo")
    parser.add_argument("--data-mode", default="fixture", choices=["fixture", "live"])
    parser.add_argument("--json", action="store_true")


def _reject_mismatched_as_of(
    universe: str,
    data_mode: str,
    dataset: str | None,
    as_of: str | None,
) -> None:
    if not as_of:
        return
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of) is None:
        raise TraderError(INVALID_ARGUMENT, "as_of 必须是 YYYY-MM-DD")
    if data_mode != "fixture":
        raise TraderError(INVALID_ARGUMENT, "Day 3 的 as_of 只用于核对 fixture 数据日期")
    manifest = load_manifest(resolve_dataset(universe, dataset))
    if str(manifest.get("data_date")) != as_of:
        raise TraderError(
            INVALID_ARGUMENT,
            f"样本数据日期是 {manifest.get('data_date')}，不能改成 {as_of}",
        )


def _snapshot(universe: str, data_mode: str, dataset: str | None) -> dict[str, Any]:
    result = run_daily(universe, data_mode, dataset)
    result["tool"] = "get_market_snapshot"
    result["data"] = result["data"]["market"]
    return result


def _screen(run_id: str) -> dict[str, Any]:
    with connect() as conn:
        found = load_run(conn, run_id)
    if found is None:
        raise TraderError(INVALID_ARGUMENT, f"找不到 run_id {run_id}")
    return envelope(
        ok=True,
        tool="screen_stocks",
        run_id=run_id,
        data_date=found["data_date"],
        source={"provider": "sqlite", "dataset": "data/trader.sqlite", "adjustment": "qfq"},
        data=found["screening"],
    )


def _failure(command: str, exc: TraderError) -> dict[str, Any]:
    tool = {
        "daily": "run_daily_research",
        "market-snapshot": "get_market_snapshot",
        "screen": "screen_stocks",
        "stock-research": "get_stock_research_data",
        "check-risk": "check_stock_risk",
        "report": "generate_daily_report",
        "freeze-fixture": "freeze_fixture",
    }.get(command, command)
    if command in {"stock-research", "check-risk", "report"}:
        return failure_envelope(tool, exc)
    return envelope(
        ok=False,
        tool=tool,
        run_id=None,
        data_date=None,
        source={"provider": None, "dataset": None, "adjustment": "qfq"},
        data=None,
        error=error_body(exc),
    )


def _symbols(value: str | None) -> list[str] | None:
    if value is None:
        return None
    return [item for item in value.split(",") if item]


def _emit(payload: dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
