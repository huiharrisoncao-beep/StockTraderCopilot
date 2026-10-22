"""Record Day 5 drill output. Does not change the frozen fixture or profile patch."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

from trader.cli import main
from trader.screening.rules import RULES

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data/fixtures/demo-20261021"
PYTHON = ROOT / ".venv/bin/python"


def main_record() -> None:
    sections = [
        _versions(),
        _drill_missing_dataset(),
        _drill_missing_indicator(),
        _drill_impossible_rule(),
        _drill_unwritable_report(),
        _drill_offline_python(),
    ]
    target = ROOT / "docs/day5-drill-log.md"
    target.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
    print(target)


def _versions() -> str:
    dsh = _run(["dsh", "--version"], cwd=ROOT).stdout.strip()
    node = _run(["node", "--version"], cwd=ROOT).stdout.strip()
    # The research plugins load from the bundle layer, so the fixture/timeout
    # config now lives in the bundle patch, not the profile user patch.
    bundle_patch = (ROOT / "harness/bundle/cordis.patch.yml").read_bytes()
    bundle_text = bundle_patch.decode("utf-8")
    config_ok = 'dataMode: "fixture"' in bundle_text and "timeoutMs: 120000" in bundle_text
    profile_pkg = (Path.home() / ".dsh/profiles/trading-research/package.json").read_text(encoding="utf-8")
    bundle_loaded = "@stock-trader/dsh-trading-bundle" in profile_pkg
    rules = (ROOT / "python/trader/screening/rules.py").read_text(encoding="utf-8")
    return "\n".join(
        [
            "# Day 5 故障演练记录",
            "",
            "记录的是命令实际输出，不是“已测试”。样本和 bundle patch 没有被改写。",
            "",
            f"- `dsh --version`: `{dsh}`",
            f"- Node: `{node}`",
            f"- bundle patch sha256: `{hashlib.sha256(bundle_patch).hexdigest()}`",
            f"- bundle patch 仍是 fixture / 120000ms: `{config_ok}`",
            f"- Profile 已把 @stock-trader/dsh-trading-bundle 加入 bundles: `{bundle_loaded}`",
            f"- 磁盘上的 `min_return_20d` 仍是 0.05: `{'0.05' in rules}`",
            "- 2026-10-22 上午尚未收盘。最近一个已完成交易日仍是 fixture 的 `2026-10-21`。这次没有重跑 `freeze-fixture`，避免换掉备用样本。",
        ]
    )


def _drill_missing_dataset() -> str:
    completed = _cli("daily", "--universe", "demo", "--data-mode", "fixture", "--dataset", "missing-demo", "--json")
    payload = json.loads(completed.stdout)
    return _section(
        "1. fixture 路径不存在",
        completed,
        {
            "exit": completed.returncode,
            "ok": payload["ok"],
            "tool": payload["tool"],
            "error": payload["error"],
            "data": payload["data"],
        },
    )


def _drill_missing_indicator() -> str:
    root = _copy_fixture()
    bars_path = root / "data/fixtures/demo-20261021/bars.csv"
    bars = pd.read_csv(bars_path, dtype={"symbol": str})
    last = bars["trade_date"].max()
    bars.loc[(bars["symbol"] == "300031") & (bars["trade_date"] == last), "close"] = None
    bars.to_csv(bars_path, index=False)
    code, payload = _daily_in(root)
    reasons = {item["symbol"]: item["reason"] for item in payload["data"]["screening"]["exclusions"]}
    symbols = [row["symbol"] for row in payload["data"]["screening"]["candidates"]]
    return _section(
        "2. 删掉候选 300031 最后一根收盘价",
        None,
        {
            "exit": code,
            "ok": payload["ok"],
            "error": payload["error"],
            "300031": reasons.get("300031"),
            "300031_in_candidates": "300031" in symbols,
            "first_candidate": symbols[0] if symbols else None,
        },
    )


def _drill_impossible_rule() -> str:
    root = _copy_fixture()
    patched = dict(RULES)
    patched["min_return_20d"] = 9.0
    import trader.screening.screener as screener

    original = screener.RULES
    screener.RULES = patched
    try:
        code, payload = _daily_in(root)
    finally:
        screener.RULES = original
    report = json.loads((root / payload["data"]["report"]["json_path"]).read_text(encoding="utf-8"))
    markdown = (root / payload["data"]["report"]["markdown_path"]).read_text(encoding="utf-8")
    return _section(
        "3. 规则临时改到不可能满足",
        None,
        {
            "exit": code,
            "ok": payload["ok"],
            "error": payload["error"],
            "candidate_count": payload["data"]["screening"]["candidate_count"],
            "excluded_RETURN_OUT_OF_RANGE": payload["data"]["screening"]["excluded_counts"].get(
                "RETURN_OUT_OF_RANGE"
            ),
            "report_candidates": len(report["screening"]["candidates"]),
            "disclaimer": report["disclaimer"],
            "markdown_has_buy": "买入" in markdown,
            "markdown_has_sell": "卖出" in markdown,
            "disk_rule_unchanged": "0.05" in (ROOT / "python/trader/screening/rules.py").read_text(encoding="utf-8"),
        },
    )


def _drill_unwritable_report() -> str:
    root = _copy_fixture()
    blocker = root / "not-a-directory"
    blocker.write_text("x", encoding="utf-8")
    code, payload = _daily_in(root, reports=blocker / "reports")
    database = sqlite3.connect(root / "data/trader.sqlite")
    run_id = payload["run_id"]
    counts = {
        "screen_hits": database.execute("SELECT COUNT(*) FROM screen_hits WHERE run_id = ?", (run_id,)).fetchone()[0],
        "research_cards": database.execute(
            "SELECT COUNT(*) FROM research_cards WHERE run_id = ?", (run_id,)
        ).fetchone()[0],
        "risk_flags": database.execute("SELECT COUNT(*) FROM risk_flags WHERE run_id = ?", (run_id,)).fetchone()[0],
        "reports": database.execute("SELECT COUNT(*) FROM reports WHERE run_id = ?", (run_id,)).fetchone()[0],
    }
    return _section(
        "4. 报告目录不可写",
        None,
        {
            "exit": code,
            "ok": payload["ok"],
            "tool": payload["tool"],
            "error": payload["error"],
            "run_id": run_id,
            "data_date": payload["data_date"],
            "data": payload["data"],
            "sqlite_counts": counts,
        },
    )


def _drill_offline_python() -> str:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(ROOT / "python"),
            "HTTP_PROXY": "http://127.0.0.1:9",
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "ALL_PROXY": "http://127.0.0.1:9",
            "NO_PROXY": "",
        }
    )
    command = [str(PYTHON), "-m", "trader.cli", "daily", "--universe", "demo", "--data-mode", "fixture", "--json"]
    started = time.perf_counter()
    first = _run(command, cwd=ROOT, env=env)
    elapsed = time.perf_counter() - started
    payload = json.loads(first.stdout)
    second = _run(command, cwd=ROOT, env=env)
    again = json.loads(second.stdout)
    first_symbols = [row["symbol"] for row in payload["data"]["screening"]["candidates"]]
    second_symbols = [row["symbol"] for row in again["data"]["screening"]["candidates"]]
    markdown = (ROOT / payload["data"]["report"]["markdown_path"]).read_text(encoding="utf-8")
    return _section(
        "5. 不配置模型，代理指向关闭端口",
        first,
        {
            "exit": first.returncode,
            "seconds": round(elapsed, 3),
            "ok": payload["ok"],
            "error": payload["error"],
            "data_date": payload["data_date"],
            "first_symbol": first_symbols[0],
            "first_close": payload["data"]["research"]["cards"][0]["close"],
            "report": payload["data"]["report"]["markdown_path"],
            "disclaimer_in_markdown": "不构成投资建议" in markdown,
            "repeat_same_order": first_symbols == second_symbols,
        },
    )


def _copy_fixture() -> Path:
    root = Path(os.environ.get("TMPDIR", "/tmp")) / f"day5-{time.time_ns()}"
    shutil.copytree(FIXTURE, root / "data/fixtures/demo-20261021")
    (root / "data/fixtures/current.json").write_text(
        json.dumps({"demo": "demo-20261021"}),
        encoding="utf-8",
    )
    return root


def _daily_in(root: Path, reports: Path | None = None) -> tuple[int, dict]:
    import trader.data.fixture_source as fixture_source
    import trader.pipeline as pipeline
    import trader.reporting.render as render
    import trader.store.sqlite_store as store

    data = root / "data"
    fixtures = data / "fixtures"
    saved = (
        fixture_source.fixture_root,
        fixture_source.current_fixture_index,
        pipeline.data_dir,
        pipeline.project_root,
        store.data_dir,
        render.reports_dir,
        render.project_root,
        sys.stdout,
    )
    fixture_source.fixture_root = lambda: fixtures
    fixture_source.current_fixture_index = lambda: fixtures / "current.json"
    pipeline.data_dir = lambda: data
    pipeline.project_root = lambda: root
    store.data_dir = lambda: data
    render.reports_dir = lambda: reports or (root / "reports")
    render.project_root = lambda: root
    buffer = _Stdout()
    sys.stdout = buffer
    try:
        code = main(["daily", "--universe", "demo", "--data-mode", "fixture", "--json"])
    finally:
        sys.stdout = saved[7]
        (
            fixture_source.fixture_root,
            fixture_source.current_fixture_index,
            pipeline.data_dir,
            pipeline.project_root,
            store.data_dir,
            render.reports_dir,
            render.project_root,
        ) = saved[:7]
    return code, json.loads(buffer.getvalue())


class _Stdout:
    def __init__(self) -> None:
        self.chunks: list[str] = []

    def write(self, text: str) -> int:
        self.chunks.append(text)
        return len(text)

    def flush(self) -> None:
        return None

    def getvalue(self) -> str:
        return "".join(self.chunks)


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "python")
    return _run([str(PYTHON), "-m", "trader.cli", *args], cwd=ROOT, env=env)


def _run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, check=False)


def _section(title: str, completed: subprocess.CompletedProcess[str] | None, summary: dict) -> str:
    lines = [f"## {title}", "", "```json", json.dumps(summary, ensure_ascii=False, indent=2), "```"]
    if completed is not None and completed.stderr.strip():
        lines.extend(["", "stderr:", "", "```text", completed.stderr.strip(), "```"])
    return "\n".join(lines)


if __name__ == "__main__":
    main_record()
