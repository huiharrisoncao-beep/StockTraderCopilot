"""Research CLI. stdout is one JSON object."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from trader.contracts import INVALID_ARGUMENT, INTERNAL, TraderError, envelope, error_body
from trader.data.freeze import freeze_fixture
from trader.pipeline import run_daily
from trader.store.sqlite_store import connect, load_run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trader.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    daily = sub.add_parser("daily")
    _add_common(daily)
    daily.add_argument("--dataset")

    snapshot = sub.add_parser("market-snapshot")
    _add_common(snapshot)
    snapshot.add_argument("--dataset")

    screen = sub.add_parser("screen")
    screen.add_argument("--run-id", required=True)
    screen.add_argument("--json", action="store_true")

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
            payload = _snapshot(args.universe, args.data_mode, args.dataset)
        elif args.command == "screen":
            payload = _screen(args.run_id)
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
        "freeze-fixture": "freeze_fixture",
    }.get(command, command)
    return envelope(
        ok=False,
        tool=tool,
        run_id=None,
        data_date=None,
        source={"provider": None, "dataset": None, "adjustment": "qfq"},
        data=None,
        error=error_body(exc),
    )


def _emit(payload: dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
