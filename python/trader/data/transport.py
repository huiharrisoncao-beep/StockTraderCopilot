"""Make AKShare's HTTP calls succeed when requests is blocked by the local proxy.

Verified on 2026-10-21: curl and httpx can read Eastmoney, but requests follows
HTTP_PROXY and is reset. AKShare 1.19.1 still owns the URL, parameters, and
column names; this module only replaces the transport.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import requests

_INSTALLED = False
_CLIENTS = (
    httpx.Client(
        trust_env=False,
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
    ),
    httpx.Client(
        trust_env=True,
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
    ),
)


def install_akshare_transport() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    def request(
        self: requests.Session,
        method: str,
        url: str,
        params: Any = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> requests.Response:
        if method.upper() != "GET":
            raise RuntimeError(f"unexpected AKShare method: {method}")
        rewritten = url.replace("://48.push2.eastmoney.com", "://82.push2.eastmoney.com")
        last: Exception | None = None
        for attempt in range(2):
            for client in _CLIENTS:
                try:
                    downloaded = client.get(rewritten, params=params, timeout=timeout or 30)
                    response = requests.Response()
                    response.status_code = downloaded.status_code
                    response._content = downloaded.content
                    response.url = str(downloaded.url)
                    response.encoding = "utf-8"
                    response.headers = requests.structures.CaseInsensitiveDict(
                        {"Content-Type": downloaded.headers.get("content-type", "application/json")}
                    )
                    response.raise_for_status()
                    return response
                except Exception as exc:
                    last = exc
            time.sleep(0.4 * (attempt + 1))
        assert last is not None
        raise last

    requests.Session.request = request  # type: ignore[method-assign]
    _INSTALLED = True
