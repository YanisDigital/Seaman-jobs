"""HTTP-клиент: общая сессия, браузерные заголовки, задержки и повторы."""
from __future__ import annotations

import logging
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("scraper.http")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8,uk;q=0.7",
}


class HttpError(Exception):
    """Запрос не удался после всех повторов."""


class HttpClient:
    def __init__(self, timeout: int = 25, delay_seconds: float = 1.0, retries: int = 3):
        self.timeout = timeout
        self.delay_seconds = delay_seconds
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self._last_request_ts = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_ts
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)

    def get(self, url: str, *, referer: Optional[str] = None) -> requests.Response:
        headers = {"Referer": referer} if referer else None
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            self._throttle()
            try:
                resp = self.session.get(url, timeout=self.timeout, headers=headers)
                self._last_request_ts = time.monotonic()
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise HttpError(f"HTTP {resp.status_code}")
                return resp
            except (requests.RequestException, HttpError) as exc:
                last_exc = exc
                self._last_request_ts = time.monotonic()
                wait = self.delay_seconds * (2 ** (attempt - 1))
                log.warning("GET %s failed (attempt %d/%d): %s; retry in %.1fs",
                            url, attempt, self.retries, exc, wait)
                time.sleep(wait)
        raise HttpError(f"GET {url} failed after {self.retries} attempts: {last_exc}")

    def get_soup(self, url: str, *, referer: Optional[str] = None) -> BeautifulSoup:
        resp = self.get(url, referer=referer)
        resp.encoding = resp.apparent_encoding or resp.encoding
        return BeautifulSoup(resp.text, "lxml")
