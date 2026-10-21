"""Local trace store. JSON files remain the human-readable copy."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from trader.paths import data_dir


def connect(path: Path | None = None) -> sqlite3.Connection:
    database = path or data_dir() / "trader.sqlite"
    database.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            data_date TEXT NOT NULL,
            universe TEXT NOT NULL,
            data_mode TEXT NOT NULL,
            status TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS snapshots (
            run_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS screen_hits (
            run_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT,
            rank INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (run_id, symbol)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bars (
            symbol TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            adjustment TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            PRIMARY KEY (symbol, trade_date, adjustment)
        )
        """
    )
    return conn


def save_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    data_date: str,
    universe: str,
    data_mode: str,
    created_at: str,
    market: dict[str, Any],
    screening: dict[str, Any],
    bars: Any,
) -> None:
    payload = {"market": market, "screening": screening}
    conn.execute(
        """
        INSERT OR REPLACE INTO runs
        (run_id, data_date, universe, data_mode, status, payload_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, data_date, universe, data_mode, "screened", json.dumps(payload, ensure_ascii=False), created_at),
    )
    conn.execute(
        "INSERT OR REPLACE INTO snapshots (run_id, payload_json) VALUES (?, ?)",
        (run_id, json.dumps(market, ensure_ascii=False)),
    )
    conn.execute("DELETE FROM screen_hits WHERE run_id = ?", (run_id,))
    for rank, row in enumerate(screening["candidates"], start=1):
        conn.execute(
            """
            INSERT INTO screen_hits (run_id, symbol, name, rank, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, row["symbol"], row.get("name"), rank, json.dumps(row, ensure_ascii=False)),
        )
    rows = [
        (
            str(item.symbol),
            str(item.trade_date),
            str(item.adjustment),
            _num(item.open),
            _num(item.high),
            _num(item.low),
            _num(item.close),
            _num(item.volume),
            _num(item.amount),
        )
        for item in bars.itertuples(index=False)
    ]
    conn.executemany(
        """
        INSERT OR REPLACE INTO bars
        (symbol, trade_date, adjustment, open, high, low, close, volume, amount)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()


def load_run(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    found = conn.execute("SELECT payload_json, data_date FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if found is None:
        return None
    payload = json.loads(found[0])
    payload["data_date"] = found[1]
    return payload


def _num(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and value != value):
        return None
    return float(value)
