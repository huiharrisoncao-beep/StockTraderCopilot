"""Live A-share reads. Only this module imports AKShare."""

from __future__ import annotations

import os
from datetime import date
from importlib.metadata import version
from typing import Any

os.environ.setdefault("TQDM_DISABLE", "1")

import pandas as pd
import requests

from trader.contracts import DATA_SOURCE_UNAVAILABLE, TraderError
from trader.data.transport import install_akshare_transport

# AKShare 1.19.1 names verified on 2026-10-21.
HIST_INTERFACE = "stock_zh_a_hist"
TX_HIST_INTERFACE = "stock_zh_a_hist_tx"
INDEX_DAILY_INTERFACE = "stock_zh_index_daily_em"
SPOT_INTERFACE = "stock_zh_a_spot_em"
SINA_SPOT_INTERFACE = "sina_market_center_amount_page"

INDEXES = (
    ("sh000001", "000001", "上证指数"),
    ("sz399001", "399001", "深证成指"),
    ("sz399006", "399006", "创业板指"),
)
ADJUSTMENT = "qfq"
VOLUME_UNIT = "lot"


def _akshare() -> Any:
    install_akshare_transport()
    import akshare as ak

    return ak


def fetch_daily_bars(
    symbol: str,
    start_date: str,
    end_date: str,
    backend: str = "eastmoney",
) -> pd.DataFrame:
    """Return qfq daily bars. Eastmoney is preferred; Tencent is the fallback."""
    if backend == "eastmoney":
        try:
            frame = _akshare().stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=ADJUSTMENT,
                timeout=20,
            )
        except Exception as exc:
            raise TraderError(
                DATA_SOURCE_UNAVAILABLE,
                f"AKShare {HIST_INTERFACE} 失败: {symbol}",
                retryable=True,
            ) from exc
        out = _normalize_hist(frame, symbol)
        out.attrs["volume_unit"] = "手"
        out.attrs["interface"] = HIST_INTERFACE
        return out
    if backend == "tencent":
        try:
            frame = _akshare().stock_zh_a_hist_tx(
                symbol=_tx_symbol(symbol),
                start_date=start_date,
                end_date=end_date,
                adjust=ADJUSTMENT,
                timeout=20,
            )
        except Exception as exc:
            raise TraderError(
                DATA_SOURCE_UNAVAILABLE,
                f"AKShare {TX_HIST_INTERFACE} 失败: {symbol}",
                retryable=True,
            ) from exc
        out = _normalize_tx(frame, symbol)
        out.attrs["volume_unit"] = "股"
        out.attrs["interface"] = TX_HIST_INTERFACE
        return out
    raise TraderError(DATA_SOURCE_UNAVAILABLE, f"未知日线来源 {backend}")


def detect_bar_backend(start_date: str, end_date: str) -> str:
    for backend in ("eastmoney", "tencent"):
        try:
            fetch_daily_bars("600519", start_date, end_date, backend=backend)
        except TraderError:
            continue
        return backend
    raise TraderError(DATA_SOURCE_UNAVAILABLE, "前复权日线来源都不可用", retryable=True)


def fetch_index_daily(symbol: str, start_date: str, end_date: str, backend: str = "eastmoney") -> pd.DataFrame:
    """Return index daily bars. Eastmoney is preferred; Tencent is the fallback."""
    if backend == "eastmoney":
        try:
            return _akshare().stock_zh_index_daily_em(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as exc:
            raise TraderError(
                DATA_SOURCE_UNAVAILABLE,
                f"AKShare {INDEX_DAILY_INTERFACE} 失败: {symbol}",
                retryable=True,
            ) from exc
    if backend == "tencent":
        try:
            return _akshare().stock_zh_a_hist_tx(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                adjust="",
                timeout=20,
            )
        except Exception as exc:
            raise TraderError(
                DATA_SOURCE_UNAVAILABLE,
                f"AKShare {TX_HIST_INTERFACE} 指数失败: {symbol}",
                retryable=True,
            ) from exc
    raise TraderError(DATA_SOURCE_UNAVAILABLE, f"未知指数来源 {backend}")


def detect_index_backend(start_date: str, end_date: str) -> str:
    for backend in ("eastmoney", "tencent"):
        try:
            frame = fetch_index_daily("sh000001", start_date, end_date, backend=backend)
        except TraderError:
            continue
        if frame is not None and not frame.empty:
            return backend
    raise TraderError(DATA_SOURCE_UNAVAILABLE, "指数日线来源都不可用", retryable=True)


def fetch_spot() -> pd.DataFrame:
    """Return the A-share spot table from ak.stock_zh_a_spot_em."""
    try:
        return _akshare().stock_zh_a_spot_em()
    except Exception as exc:
        raise TraderError(
            DATA_SOURCE_UNAVAILABLE,
            f"AKShare {SPOT_INTERFACE} 失败",
            retryable=True,
        ) from exc


def fetch_spot_top_by_amount(page_size: int = 200) -> pd.DataFrame:
    """One Eastmoney page sorted by amount. Used when full pagination fails."""
    install_akshare_transport()
    params = {
        "pn": "1",
        "pz": str(page_size),
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f6",
        "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048",
        "fields": "f2,f3,f6,f12,f14",
    }
    try:
        response = requests.Session().get(
            "https://82.push2.eastmoney.com/api/qt/clist/get",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        diff = response.json()["data"]["diff"]
    except Exception as exc:
        raise TraderError(
            DATA_SOURCE_UNAVAILABLE,
            f"AKShare {SPOT_INTERFACE} 单页成交额快照失败",
            retryable=True,
        ) from exc
    frame = pd.DataFrame(diff)
    if frame.empty or "f12" not in frame.columns:
        raise TraderError(
            DATA_SOURCE_UNAVAILABLE,
            f"AKShare {SPOT_INTERFACE} 单页成交额快照为空",
            retryable=True,
        )
    return pd.DataFrame(
        {
            "代码": frame["f12"].astype(str).str.zfill(6),
            "名称": frame["f14"].astype(str),
            "最新价": pd.to_numeric(frame["f2"], errors="coerce"),
            "涨跌幅": pd.to_numeric(frame["f3"], errors="coerce"),
            "成交额": pd.to_numeric(frame["f6"], errors="coerce"),
        }
    )


def fetch_sina_top_by_amount(page_size: int = 100, pages: int = 3) -> pd.DataFrame:
    """Sina amount-sorted pages. Eastmoney clist was unreachable on 2026-10-21 evening."""
    import httpx

    frames: list[pd.DataFrame] = []
    last: Exception | None = None
    for page in range(1, pages + 1):
        try:
            response = httpx.get(
                "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData",
                params={"page": page, "num": page_size, "sort": "amount", "asc": 0, "node": "hs_a"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30,
                trust_env=False,
                follow_redirects=True,
            )
            response.raise_for_status()
            rows = response.json()
        except Exception as exc:
            last = exc
            break
        frame = pd.DataFrame(rows)
        if frame.empty or "code" not in frame.columns:
            break
        frames.append(frame)
    if not frames:
        raise TraderError(DATA_SOURCE_UNAVAILABLE, "新浪成交额快照失败", retryable=True) from last
    combined = pd.concat(frames, ignore_index=True)
    return pd.DataFrame(
        {
            "代码": combined["code"].astype(str).str.zfill(6),
            "名称": combined["name"].astype(str),
            "最新价": pd.to_numeric(combined["trade"], errors="coerce"),
            "涨跌幅": pd.to_numeric(combined["changepercent"], errors="coerce"),
            "成交额": pd.to_numeric(combined["amount"], errors="coerce"),
        }
    )


def load_spot() -> tuple[pd.DataFrame, str]:
    """Prefer Eastmoney spot; fall back to one amount-sorted page, then Sina."""
    try:
        return fetch_spot(), "all_a_spot"
    except TraderError:
        pass
    try:
        return fetch_spot_top_by_amount(), "top_amount_page"
    except TraderError:
        return fetch_sina_top_by_amount(), "sina_amount_page"


def akshare_version() -> str:
    return version("akshare")


def select_liquid_universe(spot: pd.DataFrame, limit: int = 150) -> pd.DataFrame:
    frame = spot.copy()
    frame["代码"] = frame["代码"].astype(str).str.zfill(6)
    name = frame["名称"].astype(str)
    listed = frame["代码"].str.match(r"(00|30|60)\d{4}")
    clean = ~name.str.contains("ST|退", regex=True)
    priced = pd.to_numeric(frame["最新价"], errors="coerce").gt(0)
    amount = pd.to_numeric(frame["成交额"], errors="coerce")
    chosen = frame.loc[listed & clean & priced].assign(_amount=amount)
    chosen = chosen.dropna(subset=["_amount"]).sort_values(
        ["_amount", "代码"], ascending=[False, True]
    )
    return chosen.head(limit)[["代码", "名称"]].rename(columns={"代码": "symbol", "名称": "name"})


def _tx_symbol(symbol: str) -> str:
    code = str(symbol).zfill(6)
    if code.startswith("6"):
        return "sh" + code
    if code.startswith(("0", "3")):
        return "sz" + code
    raise TraderError(DATA_SOURCE_UNAVAILABLE, f"腾讯日线不支持代码 {code}")


def _normalize_tx(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if frame is None or frame.empty:
        raise TraderError(
            DATA_SOURCE_UNAVAILABLE,
            f"AKShare {TX_HIST_INTERFACE} 返回空表: {symbol}",
            retryable=True,
        )
    out = pd.DataFrame(
        {
            "symbol": symbol,
            "trade_date": pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d"),
            "open": pd.to_numeric(frame["open"], errors="coerce"),
            "high": pd.to_numeric(frame["high"], errors="coerce"),
            "low": pd.to_numeric(frame["low"], errors="coerce"),
            "close": pd.to_numeric(frame["close"], errors="coerce"),
            "volume": pd.to_numeric(frame["volume"], errors="coerce"),
            "amount": pd.to_numeric(frame["amount"], errors="coerce"),
            "adjustment": ADJUSTMENT,
        }
    )
    return out.sort_values("trade_date")


def _normalize_hist(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if frame is None or frame.empty:
        raise TraderError(
            DATA_SOURCE_UNAVAILABLE,
            f"AKShare {HIST_INTERFACE} 返回空表: {symbol}",
            retryable=True,
        )
    out = pd.DataFrame(
        {
            "symbol": symbol,
            "trade_date": pd.to_datetime(frame["日期"]).dt.strftime("%Y-%m-%d"),
            "open": pd.to_numeric(frame["开盘"], errors="coerce"),
            "high": pd.to_numeric(frame["最高"], errors="coerce"),
            "low": pd.to_numeric(frame["最低"], errors="coerce"),
            "close": pd.to_numeric(frame["收盘"], errors="coerce"),
            "volume": pd.to_numeric(frame["成交量"], errors="coerce"),
            "amount": pd.to_numeric(frame["成交额"], errors="coerce"),
            "adjustment": ADJUSTMENT,
        }
    )
    return out.sort_values("trade_date")


def iso_date(value: date) -> str:
    return value.isoformat()
