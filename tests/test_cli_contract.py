"""CLI envelope and exit codes against a tiny fixture. No network."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from trader.cli import main


def _redirect(monkeypatch, root: Path) -> None:
    data = root / "data"
    fixtures = data / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("trader.pipeline.data_dir", lambda: data)
    monkeypatch.setattr("trader.pipeline.project_root", lambda: root)
    monkeypatch.setattr("trader.store.sqlite_store.data_dir", lambda: data)
    monkeypatch.setattr("trader.data.fixture_source.fixture_root", lambda: fixtures)
    monkeypatch.setattr("trader.data.fixture_source.current_fixture_index", lambda: fixtures / "current.json")


def _write_fixture(root: Path, *, missing_close: bool = False) -> None:
    dataset = root / "data" / "fixtures" / "demo-20261021"
    dataset.mkdir(parents=True)
    dates = pd.bdate_range("2026-07-27", periods=60)
    rows = []
    for symbol, closes, volumes in (
        ("600519", [10.0] * 40 + [12.0] * 19 + [13.0], [100.0] * 59 + [200.0]),
        ("000001", [10.0] * 60, [100.0] * 60),
    ):
        for trade_date, close, volume in zip(dates, closes, volumes, strict=True):
            rows.append(
                {
                    "symbol": symbol,
                    "trade_date": trade_date.strftime("%Y-%m-%d"),
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": volume,
                    "amount": close * volume,
                    "adjustment": "qfq",
                }
            )
    bars = pd.DataFrame(rows)
    if missing_close:
        bars.loc[(bars["symbol"] == "000001") & (bars["trade_date"] == "2026-10-16"), "close"] = None
    bars.to_csv(dataset / "bars.csv", index=False)
    pd.DataFrame({"symbol": ["600519", "000001"], "name": ["贵州茅台", "平安银行"]}).to_csv(
        dataset / "universe.csv", index=False
    )
    (dataset / "industry.csv").write_text("symbol,industry\n", encoding="utf-8")
    market = {
        "data_date": "2026-10-16",
        "indices": [],
        "advance_count": 1,
        "decline_count": 1,
        "flat_count": 0,
        "breadth_scope": "demo_universe",
        "breadth_note": "测试样本",
    }
    # bdate_range end depends on the calendar; pin manifest to the last generated bar.
    data_date = bars["trade_date"].max()
    market["data_date"] = data_date
    if missing_close:
        bars.loc[(bars["symbol"] == "000001") & (bars["trade_date"] == data_date), "close"] = None
        bars.to_csv(dataset / "bars.csv", index=False)
    (dataset / "market.json").write_text(json.dumps(market), encoding="utf-8")
    (dataset / "manifest.json").write_text(
        json.dumps(
            {
                "dataset": "demo-20261021",
                "data_date": data_date,
                "adjustment": "qfq",
                "note": "本地历史样本，不是实时行情",
            }
        ),
        encoding="utf-8",
    )
    (root / "data" / "fixtures" / "current.json").write_text(
        json.dumps({"demo": "demo-20261021"}),
        encoding="utf-8",
    )


def _run(monkeypatch, capsys, root: Path, argv: list[str]) -> tuple[int, dict]:
    _redirect(monkeypatch, root)
    code = main(argv)
    payload = json.loads(capsys.readouterr().out)
    return code, payload


def test_daily_envelope_is_stable(monkeypatch, capsys, tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    first_code, first = _run(
        monkeypatch, capsys, tmp_path, ["daily", "--universe", "demo", "--data-mode", "fixture", "--json"]
    )
    second_code, second = _run(
        monkeypatch, capsys, tmp_path, ["daily", "--universe", "demo", "--data-mode", "fixture", "--json"]
    )
    assert first_code == second_code == 0
    assert first["ok"] is True
    assert first["error"] is None
    assert first["tool"] == "run_daily_research"
    assert first["source"]["dataset"] == "data/fixtures/demo-20261021"
    assert [row["symbol"] for row in first["data"]["screening"]["candidates"]] == ["600519"]
    assert [row["symbol"] for row in second["data"]["screening"]["candidates"]] == ["600519"]
    assert "NO_CANDIDATES" not in json.dumps(first["error"])


def test_missing_close_is_excluded(monkeypatch, capsys, tmp_path: Path) -> None:
    _write_fixture(tmp_path, missing_close=True)
    code, payload = _run(
        monkeypatch, capsys, tmp_path, ["daily", "--universe", "demo", "--data-mode", "fixture", "--json"]
    )
    assert code == 0
    reasons = {item["symbol"]: item["reason"] for item in payload["data"]["screening"]["exclusions"]}
    assert reasons["000001"] == "DATA_INCOMPLETE"
    assert [row["symbol"] for row in payload["data"]["screening"]["candidates"]] == ["600519"]


def test_business_and_usage_exits(monkeypatch, capsys, tmp_path: Path) -> None:
    missing_code, missing = _run(
        monkeypatch, capsys, tmp_path, ["daily", "--universe", "demo", "--data-mode", "fixture", "--json"]
    )
    assert missing_code == 2
    assert missing["ok"] is False
    assert missing["error"]["code"] == "DATA_SOURCE_UNAVAILABLE"

    usage_code, usage = _run(
        monkeypatch, capsys, tmp_path, ["daily", "--universe", "csi300", "--data-mode", "fixture", "--json"]
    )
    assert usage_code == 1
    assert usage["error"]["code"] == "INVALID_ARGUMENT"

    bad_code, bad = _run(monkeypatch, capsys, tmp_path, ["daily", "--universe"])
    assert bad_code == 1
    assert bad["error"]["code"] == "INVALID_ARGUMENT"
