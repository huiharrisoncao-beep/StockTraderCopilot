"""JSON envelope shared by the CLI and, later, the Harness plugin."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")

DATA_SOURCE_UNAVAILABLE = "DATA_SOURCE_UNAVAILABLE"
DATA_QUALITY_FAILED = "DATA_QUALITY_FAILED"
MISSING_FIELDS = "MISSING_FIELDS"
EMPTY_UNIVERSE = "EMPTY_UNIVERSE"
NO_CANDIDATES = "NO_CANDIDATES"
INVALID_ARGUMENT = "INVALID_ARGUMENT"
REPORT_WRITE_FAILED = "REPORT_WRITE_FAILED"
TIMEOUT = "TIMEOUT"
INTERNAL = "INTERNAL"


class TraderError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def now_shanghai() -> datetime:
    return datetime.now(SHANGHAI)


def envelope(
    *,
    ok: bool,
    tool: str,
    run_id: str | None,
    data_date: str | None,
    source: dict[str, Any],
    data: Any,
    warnings: list[str] | None = None,
    error: dict[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    stamp = generated_at or now_shanghai()
    return {
        "ok": ok,
        "tool": tool,
        "run_id": run_id,
        "data_date": data_date,
        "generated_at": stamp.isoformat(timespec="seconds"),
        "source": source,
        "warnings": warnings or [],
        "error": error,
        "data": data,
    }


def error_body(exc: TraderError) -> dict[str, Any]:
    return {
        "code": exc.code,
        "message": str(exc),
        "retryable": exc.retryable,
    }
