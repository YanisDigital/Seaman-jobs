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


# Статусы, которые имеет смысл повторить (429 = слишком много запросов / rate limit).
_RETRYABLE = (429, 500, 502, 503, 504)
_MAX_DELAY = 10.0   # потолок для само-замедления, сек
_MAX_WAIT = 60.0    # потолок ожидания между повторами, сек


class HttpClient:
    def __init__(self, timeout: int = 25, delay_seconds: float = 1.0, retries: int = 4):
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

    def _retry_wait(self, attempt: int, resp: requests.Response) -> float:
        """Сколько ждать перед повтором. Уважаем заголовок Retry-After."""
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                return min(_MAX_WAIT, float(retry_after) + 0.5)
            except ValueError:
                pass
        base = 5.0 if resp.status_code == 429 else self.delay_seconds
        return min(_MAX_WAIT, base * (2 ** (attempt - 1)))

    def get(self, url: str, *, referer: Optional[str] = None) -> requests.Response:
        headers = {"Referer": referer} if referer else None
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            self._throttle()
            try:
                resp = self.session.get(url, timeout=self.timeout, headers=headers)
            except requests.RequestException as exc:
                self._last_request_ts = time.monotonic()
                last_exc = exc
                if attempt >= self.retries:
                    break
                wait = min(_MAX_WAIT, self.delay_seconds * (2 ** (attempt - 1)))
                log.warning("GET %s: сеть (%s); попытка %d/%d, повтор через %.1fс",
                            url, exc, attempt, self.retries, wait)
                time.sleep(wait)
                continue

            self._last_request_ts = time.monotonic()
            if resp.status_code not in _RETRYABLE:
                return resp

            # Сайт ограничивает темп — замедляемся на остаток прогона.
            if resp.status_code == 429:
                self.delay_seconds = min(self.delay_seconds * 1.5, _MAX_DELAY)
            last_exc = HttpError(f"HTTP {resp.status_code}")
            if attempt >= self.retries:
                break
            wait = self._retry_wait(attempt, resp)
            log.warning("GET %s: HTTP %d (ограничение темпа); попытка %d/%d, повтор через %.0fс",
                        url, resp.status_code, attempt, self.retries, wait)
            time.sleep(wait)

        raise HttpError(f"GET {url}: не удалось за {self.retries} попыток ({last_exc})")

    def get_soup(self, url: str, *, referer: Optional[str] = None) -> BeautifulSoup:
        resp = self.get(url, referer=referer)
        resp.encoding = resp.apparent_encoding or resp.encoding
        return BeautifulSoup(resp.text, "lxml")
