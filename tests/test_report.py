"""Report skeleton. Numbers come from the stored payload, not from a model."""

from __future__ import annotations

import json
from pathlib import Path

from trader.reporting.render import DISCLAIMER, render_markdown, write_report
from trader.contracts import REPORT_WRITE_FAILED, TraderError
from tests.test_cli_contract import _run, _write_fixture


def _context(**overrides: object) -> dict:
    context = {
        "run_id": "research-20261021-120000",
        "data_date": "2026-10-21",
        "generated_at": "2026-10-22T09:00:00+08:00",
        "universe": "demo",
        "source": {"provider": "fixture", "dataset": "data/fixtures/demo", "adjustment": "qfq", "note": "样本"},
        "market": {
            "data_date": "2026-10-21",
            "indices": [],
            "advance_count": 0,
            "decline_count": 0,
            "flat_count": 0,
            "breadth_scope": "demo_universe",
            "breadth_note": "测试",
        },
        "screening": {
            "rule_set": "trend_volume_v1",
            "rules": {"note": "演示用可解释规则，不是经过验证的交易策略，也不构成投资建议。"},
            "candidates": [],
            "excluded_counts": {},
        },
        "cards": [],
        "flags": [],
    }
    context.update(overrides)
    return context


def test_empty_candidates_still_render_disclaimer() -> None:
    markdown = render_markdown(_context())
    assert "data_date: 2026-10-21" in markdown
    assert "trend_volume_v1" in markdown
    assert "候选行业分布" in markdown
    assert "不是全市场板块涨幅排名" in markdown
    assert DISCLAIMER in markdown
    assert "买入" not in markdown
    assert "卖出" not in markdown


def test_daily_report_close_matches_fixture_csv(monkeypatch, capsys, tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    code, payload = _run(
        monkeypatch,
        capsys,
        tmp_path,
        ["daily", "--universe", "demo", "--data-mode", "fixture", "--json"],
    )
    assert code == 0
    report_path = _stored(tmp_path, payload["data"]["report"]["json_path"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    bars = (tmp_path / "data/fixtures/demo-20261021/bars.csv").read_text(encoding="utf-8")
    close = report["cards"][0]["close"]
    assert report["cards"][0]["symbol"] == "600519"
    assert f",{close}," in bars or f",{close}.0," in bars
    markdown = _stored(tmp_path, payload["data"]["report"]["markdown_path"]).read_text(encoding="utf-8")
    assert DISCLAIMER in markdown
    assert "候选行业分布" in markdown


def test_unwritable_report_raises(monkeypatch, tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr("trader.reporting.render.reports_dir", lambda: blocker / "reports")
    try:
        write_report(_context())
    except TraderError as exc:
        assert exc.code == REPORT_WRITE_FAILED
    else:
        raise AssertionError("expected report write failure")


def _stored(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path
