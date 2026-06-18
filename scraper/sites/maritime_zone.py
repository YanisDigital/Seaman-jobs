"""Скрейпер maritime-zone.com (за Cloudflare — через headless-браузер).

Селекторы списка/детали финализируются по реальному HTML (см. verify-этап).
"""
from __future__ import annotations

from typing import Iterator, List, Set
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import Vacancy
from ..playwright_fetch import CloudflareBrowser, PlaywrightNotInstalled
from .base import BaseScraper, clean, text_block

_HARD_PAGE_CAP = 300


class MaritimeZoneScraper(BaseScraper):
    name = "maritime_zone"
    base_url = "https://maritime-zone.com"

    LIST_SELECTOR = "div.item[data-key]"

    # метка li -> поле Vacancy
    _LABELS = {
        "wage": "salary",
        "vessel type": "vessel_type",
        "start date": "join_date",
        "contract duration": "contract_duration",
        "fleet": "fleet",
    }

    def __init__(self, http, max_pages: int = 0, *, headless: bool = True,
                 challenge_wait: int = 25, delay: float = 1.0):
        super().__init__(http, max_pages)
        self.headless = headless
        self.challenge_wait = challenge_wait
        self.delay = delay
        self._cf: "CloudflareBrowser | None" = None
        self._browser: "CloudflareBrowser | None" = None
        self._unavailable = False
        self._detail_blocked = False

    def start(self) -> None:
        """Открыть браузер один раз на весь прогон (список + детали)."""
        if self._browser is not None or self._unavailable:
            return
        try:
            self._cf = CloudflareBrowser(headless=self.headless,
                                         challenge_wait=self.challenge_wait,
                                         delay=self.delay)
            self._browser = self._cf.__enter__()
        except PlaywrightNotInstalled as exc:
            self._unavailable = True
            self.log.error("%s — пропускаю maritime-zone.", exc)

    def finish(self) -> None:
        if self._cf is not None:
            self._cf.__exit__(None, None, None)
        self._cf = None
        self._browser = None
        self._detail_blocked = False

    def _list_url(self, page: int) -> str:
        base = f"{self.base_url}/en/vacancy"
        return base if page <= 1 else f"{base}?page={page}"

    def list_vacancies(self) -> Iterator[Vacancy]:
        self.start()  # на случай прямого вызова без start()
        if self._browser is None:
            return
        yield from self._iterate(self._browser)

    def _iterate(self, browser: CloudflareBrowser) -> Iterator[Vacancy]:
        seen: Set[str] = set()
        page = 1
        while True:
            if self._page_limit_reached(page) or page > _HARD_PAGE_CAP:
                break
            html = browser.fetch(self._list_url(page), wait_selector=self.LIST_SELECTOR)
            vacs = self._parse_list(html)
            if not vacs:
                break
            new_on_page = 0
            for vac in vacs:
                if vac.vacancy_id and vac.vacancy_id in seen:
                    continue
                if vac.vacancy_id:
                    seen.add(vac.vacancy_id)
                new_on_page += 1
                yield vac
            self.log.info("page %s: %d new vacancies", page, new_on_page)
            if new_on_page == 0:
                break
            page += 1

    # --- парсинг (финализируется по реальному HTML) ---

    def _parse_list(self, html: str) -> List[Vacancy]:
        soup = BeautifulSoup(html, "lxml")
        results: List[Vacancy] = []
        for card in soup.select("div.item[data-key]"):
            title = card.select_one("a.card-title")
            if not title:
                continue
            href = title.get("href", "")
            vac = Vacancy(
                source=self.name,
                vacancy_id=clean(card.get("data-key", "")),
                position=clean(title.get_text(" ", strip=True)),
                url=urljoin(self.base_url, href),
            )
            # пары label -> value из ul.column li
            for li in card.select("ul.column li"):
                label_el = li.select_one("span.pull-left")
                value_el = li.select_one("strong")
                if not label_el or not value_el:
                    continue
                key = self._LABELS.get(clean(label_el.get_text(strip=True)).rstrip(":").lower())
                if key:
                    setattr(vac, key, clean(value_el.get_text(" ", strip=True)))
            # компания (alt у ссылки на крюинг) + страна
            comp = card.select_one("div.col-md-3 a[href*='/crewing/']")
            if comp:
                vac.company = clean(comp.get("alt") or
                                    (comp.find("img").get("alt") if comp.find("img") else ""))
            # просмотры + дата публикации
            views = card.select_one("span.views")
            status = card.select_one("div.single-status span")
            extra_parts = []
            if views:
                extra_parts.append("Views: " + clean(views.get_text(" ", strip=True)).replace(" viewed", ""))
            if status:
                vac.posted = clean(status.get_text(" ", strip=True))
            vac.extra = " | ".join(extra_parts)
            results.append(vac)
        return results

    def enrich(self, vacancy: Vacancy) -> None:
        """Best-effort: данные списка уже богаты; деталь добавляет полное описание.

        В headless-режиме страницы-детали часто не проходят Cloudflare — тогда
        пробуем один раз и дальше не тратим время (данные списка остаются).
        """
        if not self._browser or self._detail_blocked:
            return
        try:
            html = self._browser.fetch(vacancy.url, wait_selector="div.single-left, div.white-box")
        except Exception as exc:  # noqa: BLE001
            self.log.warning("detail failed %s: %s", vacancy.url, exc)
            return
        soup = BeautifulSoup(html, "lxml")
        if soup.title and "just a moment" in soup.title.get_text(strip=True).lower():
            self._detail_blocked = True
            self.log.warning(
                "Детали maritime-zone заблокированы Cloudflare в headless-режиме — "
                "оставляю данные списка. Чтобы получать полное описание, поставьте "
                "maritime_zone.headless: false в config.yaml.")
            return
        main = (soup.select_one("div.col-md-8.single-left")
                or soup.select_one("div.single-left")
                or soup.select_one("div.white-box")
                or soup.body)
        if not main:
            return
        for junk in main.select("form, button, .btn, script, style, .single-hot"):
            junk.decompose()
        vacancy.description = text_block(main.get_text("\n", strip=True))[:4000]
