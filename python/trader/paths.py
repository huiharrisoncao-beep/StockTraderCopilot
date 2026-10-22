"""Repository paths. The CLI does not accept arbitrary data paths from a model."""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    return project_root() / "data"


def reports_dir() -> Path:
    return project_root() / "reports"


def fixture_root() -> Path:
    return data_dir() / "fixtures"


def current_fixture_index() -> Path:
    return fixture_root() / "current.json"
