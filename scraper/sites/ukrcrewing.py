"""Скрейпер ukrcrewing.com.ua (статический HTML, таблица)."""
from __future__ import annotations

import re
from typing import Iterator, Set
from urllib.parse import urljoin

from ..http_client import HttpError
from ..models import Vacancy
from .base import BaseScraper, clean, text_block

_HARD_PAGE_CAP = 300
_ID_RE = re.compile(r"/vacancy/(\d+)")


class UkrCrewingScraper(BaseScraper):
    name = "ukrcrewing"
    base_url = "https://ukrcrewing.com.ua"
    lang = "en"  # язык контента (en -> английские названия должностей/судов)

    def _list_url(self, page: int) -> str:
        if page <= 1:
            return f"{self.base_url}/{self.lang}/vacancy"
        return f"{self.base_url}/{self.lang}/vacancy/p{page}/"

    def list_vacancies(self) -> Iterator[Vacancy]:
        seen: Set[str] = set()
        page = 1
        while True:
            if self._page_limit_reached(page) or page > _HARD_PAGE_CAP:
                break
            try:
                soup = self.http.get_soup(self._list_url(page))
            except HttpError as exc:
                self.log.warning(
                    "остановка на странице %d (%s) — сохраняю собранное с предыдущих страниц",
                    page, exc)
                break
            rows = [a.find_parent("tr") for a in soup.select("a.var")]
            rows = [r for r in rows if r is not None]
            if not rows:
                break
            new_on_page = 0
            for tr in rows:
                vac = self._parse_row(tr)
                if not vac or vac.vacancy_id in seen:
                    continue
                seen.add(vac.vacancy_id)
                new_on_page += 1
                yield vac
            self.log.info("page %s: %d new vacancies", page, new_on_page)
            if new_on_page == 0:
                break
            page += 1

    def _parse_row(self, tr) -> "Vacancy | None":
        link = tr.select_one("a.var")
        if not link:
            return None
        href = link.get("href", "")
        m = _ID_RE.search(href)
        vac_id = m.group(1) if m else ""
        position = clean(link.get_text(" ", strip=True))

        tds = tr.find_all("td", recursive=False) or tr.find_all("td")
        price_td = tr.select_one("td.price")
        salary = clean(price_td.get_text(" ", strip=True)) if price_td else ""

        vessel_type = clean(tds[1].get_text(" ", strip=True)) if len(tds) > 1 else ""
        duration = clean(tds[2].get_text(" ", strip=True)) if len(tds) > 2 else ""
        # Две последние ячейки строки — даты (посадка, опубликовано).
        join_date = clean(tds[-2].get_text(" ", strip=True)) if len(tds) >= 5 else ""
        posted = clean(tds[-1].get_text(" ", strip=True)) if len(tds) >= 5 else ""

        detail_url = urljoin(self.base_url, f"/{self.lang}/vacancy/{vac_id}") if vac_id \
            else urljoin(self.base_url, href.split("?")[0])

        return Vacancy(
            source=self.name,
            vacancy_id=vac_id,
            position=position,
            vessel_type=vessel_type,
            contract_duration=duration,
            salary=salary,
            join_date=join_date,
            posted=posted,
            url=detail_url,
        )

    def enrich(self, vacancy: Vacancy) -> None:
        try:
            soup = self.http.get_soup(vacancy.url)
        except Exception as exc:  # noqa: BLE001
            self.log.warning("detail failed %s: %s", vacancy.url, exc)
            return
        container = (soup.select_one("div.vacancy-page-content")
                     or soup.select_one("div#left")
                     or soup.select_one("div.page-content"))
        if not container:
            return
        # Убрать похожие вакансии / формы / скрипты из контейнера.
        for junk in container.select("table, form, script, style, .pager"):
            junk.decompose()
        desc = text_block(container.get_text("\n", strip=True))
        # Отрезать хвост "Схожі вакансії" / "Similar vacancies", если попал.
        for marker in ("Схожі вакансії", "Similar vacancies", "Похожие вакансии"):
            idx = desc.find(marker)
            if idx != -1:
                desc = desc[:idx].strip()
        if desc:
            vacancy.description = desc
