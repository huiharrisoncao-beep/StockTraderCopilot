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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS research_cards (
            run_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            position INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (run_id, symbol)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS risk_flags (
            run_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            code TEXT NOT NULL,
            severity TEXT NOT NULL,
            message TEXT NOT NULL,
            PRIMARY KEY (run_id, symbol, code)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            run_id TEXT PRIMARY KEY,
            markdown_path TEXT NOT NULL,
            json_path TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
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
    source: dict[str, Any] | None = None,
) -> None:
    payload = {"market": market, "screening": screening, "source": source or {}}
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
    found = conn.execute(
        """
        SELECT payload_json, data_date, created_at, universe, data_mode, status
        FROM runs WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if found is None:
        return None
    payload = json.loads(found[0])
    payload["data_date"] = found[1]
    payload["created_at"] = found[2]
    payload["universe"] = found[3]
    payload["data_mode"] = found[4]
    payload["status"] = found[5]
    return payload


def load_bars(conn: sqlite3.Connection, symbols: list[str]) -> Any:
    import pandas as pd

    columns = ["symbol", "trade_date", "adjustment", "open", "high", "low", "close", "volume", "amount"]
    if not symbols:
        return pd.DataFrame(columns=columns)
    marks = ",".join("?" for _ in symbols)
    rows = conn.execute(
        f"""
        SELECT symbol, trade_date, adjustment, open, high, low, close, volume, amount
        FROM bars WHERE symbol IN ({marks})
        ORDER BY symbol, trade_date
        """,
        symbols,
    ).fetchall()
    return pd.DataFrame(rows, columns=columns)


def save_research(conn: sqlite3.Connection, run_id: str, cards: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM research_cards WHERE run_id = ?", (run_id,))
    conn.executemany(
        """
        INSERT INTO research_cards (run_id, symbol, position, payload_json)
        VALUES (?, ?, ?, ?)
        """,
        [
            (run_id, card["symbol"], index, json.dumps(card, ensure_ascii=False))
            for index, card in enumerate(cards)
        ],
    )
    conn.execute("UPDATE runs SET status = ? WHERE run_id = ?", ("researched", run_id))
    conn.commit()


def load_research(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT payload_json FROM research_cards WHERE run_id = ? ORDER BY position",
        (run_id,),
    ).fetchall()
    return [json.loads(row[0]) for row in rows]


def save_risk(conn: sqlite3.Connection, run_id: str, flags: list[dict[str, str]]) -> None:
    conn.execute("DELETE FROM risk_flags WHERE run_id = ?", (run_id,))
    conn.executemany(
        """
        INSERT INTO risk_flags (run_id, symbol, code, severity, message)
        VALUES (?, ?, ?, ?, ?)
        """,
        [(run_id, flag["symbol"], flag["code"], flag["severity"], flag["message"]) for flag in flags],
    )
    conn.execute("UPDATE runs SET status = ? WHERE run_id = ?", ("risk_checked", run_id))
    conn.commit()


def load_risk(conn: sqlite3.Connection, run_id: str) -> list[dict[str, str]]:
    rows = conn.execute(
        """
        SELECT symbol, code, severity, message FROM risk_flags
        WHERE run_id = ? ORDER BY symbol, code
        """,
        (run_id,),
    ).fetchall()
    return [
        {"symbol": row[0], "code": row[1], "severity": row[2], "message": row[3]}
        for row in rows
    ]


def save_report(
    conn: sqlite3.Connection,
    run_id: str,
    markdown_path: str,
    json_path: str,
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO reports
        (run_id, markdown_path, json_path, status, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (run_id, markdown_path, json_path, "written", created_at),
    )
    conn.execute("UPDATE runs SET status = ? WHERE run_id = ?", ("reported", run_id))
    conn.commit()


def _num(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and value != value):
        return None
    return float(value)
