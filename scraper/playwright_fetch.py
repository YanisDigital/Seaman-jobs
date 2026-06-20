"""Получение HTML через headless-браузер (для сайтов за Cloudflare).

Используется только для maritime-zone.com. Требует установленного playwright:
    pip install playwright
    python -m playwright install chromium
"""
from __future__ import annotations

import logging
import os
import sys
import time
from typing import Optional

log = logging.getLogger("scraper.playwright")


def _configure_bundled_browser() -> None:
    """В собранном .exe указать playwright на упакованный Chromium.

    PyInstaller кладёт данные в каталог bundle (`sys._MEIPASS`). Если там есть
    папка `ms-playwright`, направляем туда PLAYWRIGHT_BROWSERS_PATH — иначе
    playwright ищет браузер в профиле пользователя (которого на чужом ПК нет).
    """
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        return
    if not getattr(sys, "frozen", False):
        return
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(sys.executable)
    bundled = os.path.join(base, "ms-playwright")
    if os.path.isdir(bundled):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = bundled
        log.info("Использую упакованный браузер: %s", bundled)

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

_CHALLENGE_MARKERS = ("Just a moment", "Enable JavaScript and cookies",
                      "challenge-platform", "cf-chl")


class PlaywrightNotInstalled(RuntimeError):
    pass


class CloudflareBrowser:
    """Контекст-менеджер: один браузер на весь прогон, проходит Cloudflare."""

    def __init__(self, headless: bool = True, challenge_wait: int = 25, delay: float = 1.0):
        self.headless = headless
        self.challenge_wait = challenge_wait
        self.delay = delay
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    def __enter__(self) -> "CloudflareBrowser":
        _configure_bundled_browser()
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # noqa: F841
            raise PlaywrightNotInstalled(
                "playwright не установлен. Установите: pip install playwright "
                "&& python -m playwright install chromium"
            )
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        self._context = self._browser.new_context(
            user_agent=_UA,
            locale="en-US",
            viewport={"width": 1366, "height": 900},
        )
        self._page = self._context.new_page()
        return self

    def __exit__(self, *exc) -> None:
        for closer in (self._context, self._browser):
            try:
                if closer:
                    closer.close()
            except Exception:  # noqa: BLE001
                pass
        if self._pw:
            try:
                self._pw.stop()
            except Exception:  # noqa: BLE001
                pass

    def _looks_like_challenge(self, html: str, title: str) -> bool:
        if "just a moment" in (title or "").lower():
            return True
        head = html[:4000]
        return any(m.lower() in head.lower() for m in _CHALLENGE_MARKERS)

    def fetch(self, url: str, wait_selector: Optional[str] = None) -> str:
        """Загрузить URL, дождаться прохождения Cloudflare, вернуть HTML."""
        page = self._page
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        deadline = time.monotonic() + self.challenge_wait
        while time.monotonic() < deadline:
            html = page.content()
            title = page.title()
            if not self._looks_like_challenge(html, title):
                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=4000)
                    except Exception:  # noqa: BLE001
                        pass
                time.sleep(self.delay)
                return page.content()
            page.wait_for_timeout(1500)  # ждём, пока challenge решится
        log.warning("Cloudflare challenge не пройден за %ss: %s", self.challenge_wait, url)
        return page.content()
