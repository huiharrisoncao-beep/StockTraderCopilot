"""Day 5 failure drills. No network. Assertions lock the recorded behavior."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

from trader.cli import main
from trader.screening.rules import RULES
from tests.test_cli_contract import _redirect, _run, _write_fixture


def test_missing_fixture_is_unavailable(monkeypatch, capsys, tmp_path: Path) -> None:
    code, payload = _run(
        monkeypatch,
        capsys,
        tmp_path,
        ["daily", "--universe", "demo", "--data-mode", "fixture", "--dataset", "missing-demo", "--json"],
    )
    assert code == 2
    assert payload["ok"] is False
    assert payload["error"]["code"] == "DATA_SOURCE_UNAVAILABLE"
    assert payload["data"] is None


def test_missing_indicator_excludes_that_symbol(monkeypatch, capsys, tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    bars_path = tmp_path / "data/fixtures/demo-20261021/bars.csv"
    bars = pd.read_csv(bars_path, dtype={"symbol": str})
    last = str(bars["trade_date"].max())
    bars.loc[(bars["symbol"] == "600519") & (bars["trade_date"].astype(str).eq(last)), "close"] = None
    bars.to_csv(bars_path, index=False)
    code, payload = _run(
        monkeypatch, capsys, tmp_path, ["daily", "--universe", "demo", "--data-mode", "fixture", "--json"]
    )
    assert code == 0
    reasons = {item["symbol"]: item["reason"] for item in payload["data"]["screening"]["exclusions"]}
    assert reasons["600519"] == "DATA_INCOMPLETE"
    assert "600519" not in {row["symbol"] for row in payload["data"]["screening"]["candidates"]}


def test_impossible_rule_writes_empty_report(monkeypatch, capsys, tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    patched = dict(RULES)
    patched["min_return_20d"] = 9.0
    monkeypatch.setattr("trader.screening.screener.RULES", patched)
    code, payload = _run(
        monkeypatch, capsys, tmp_path, ["daily", "--universe", "demo", "--data-mode", "fixture", "--json"]
    )
    assert code == 0
    assert payload["ok"] is True
    assert payload["error"] is None
    assert payload["data"]["screening"]["candidates"] == []
    report = json.loads((tmp_path / payload["data"]["report"]["json_path"]).read_text(encoding="utf-8"))
    markdown = (tmp_path / payload["data"]["report"]["markdown_path"]).read_text(encoding="utf-8")
    assert report["screening"]["candidates"] == []
    assert "trend_volume_v1" in markdown
    assert "不构成投资建议" in markdown
    assert "买入" not in markdown
    assert "建议卖出" not in markdown


def test_unwritable_report_keeps_screening(monkeypatch, capsys, tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    _redirect(monkeypatch, tmp_path)
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr("trader.reporting.render.reports_dir", lambda: blocker / "reports")
    code = main(["daily", "--universe", "demo", "--data-mode", "fixture", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert payload["error"]["code"] == "REPORT_WRITE_FAILED"
    assert payload["run_id"]
    assert payload["data"] is None
    database = sqlite3.connect(tmp_path / "data/trader.sqlite")
    hits = database.execute(
        "SELECT COUNT(*) FROM screen_hits WHERE run_id = ?", (payload["run_id"],)
    ).fetchone()[0]
    cards = database.execute(
        "SELECT COUNT(*) FROM research_cards WHERE run_id = ?", (payload["run_id"],)
    ).fetchone()[0]
    reports = database.execute(
        "SELECT COUNT(*) FROM reports WHERE run_id = ?", (payload["run_id"],)
    ).fetchone()[0]
    assert hits == 1
    assert cards == 1
    assert reports == 0
    monkeypatch.setattr("trader.reporting.render.reports_dir", lambda: tmp_path / "reports")
    retry = main(["report", "--run-id", payload["run_id"], "--json"])
    retried = json.loads(capsys.readouterr().out)
    assert retry == 0
    assert retried["ok"] is True
    assert retried["data"]["markdown_path"].endswith(".md")
    written = database.execute(
        "SELECT COUNT(*) FROM reports WHERE run_id = ?", (payload["run_id"],)
    ).fetchone()[0]
    assert written == 1
