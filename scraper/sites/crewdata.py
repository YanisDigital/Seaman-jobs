"""Скрейпер crewdata.com (статический HTML, список карточек).

Очень большой агрегатор (сотни тысяч вакансий) — ВСЕГДА используйте лимит страниц.
Должность и тип судна берём из параметров ссылки (for=/on=), они на английском,
поэтому фильтр по ключевым словам работает как для остальных сайтов.
"""
from __future__ import annotations

from typing import Iterator, Set
from urllib.parse import parse_qs, urljoin, urlparse

from ..http_client import HttpError
from ..models import Vacancy
from .base import BaseScraper, clean, text_block

_HARD_PAGE_CAP = 1000


class CrewDataScraper(BaseScraper):
    name = "crewdata"
    base_url = "https://crewdata.com"

    LIST_URL = "https://crewdata.com/jobs.php?lang=rus&page={page}"

    def list_vacancies(self) -> Iterator[Vacancy]:
        seen: Set[str] = set()
        page = 1
        while True:
            if self._page_limit_reached(page) or page > _HARD_PAGE_CAP:
                break
            try:
                soup = self.http.get_soup(self.LIST_URL.format(page=page))
            except HttpError as exc:
                self.log.warning(
                    "остановка на странице %d (%s) — сохраняю собранное с предыдущих страниц",
                    page, exc)
                break
            rows = soup.select("div.rowFlex")
            new_on_page = 0
            for row in rows:
                vac = self._parse_row(row)
                if not vac or vac.vacancy_id in seen:
                    continue
                seen.add(vac.vacancy_id)
                new_on_page += 1
                yield vac
            self.log.info("page %s: %d new vacancies", page, new_on_page)
            if new_on_page == 0:          # нет новых вакансий — дальше нет смысла
                break
            page += 1

    def _parse_row(self, row) -> "Vacancy | None":
        link = row.select_one("a.nameLink[href*='job.php']")
        if not link:
            return None                    # рекламные/служебные строки пропускаем
        href = link.get("href", "")
        qs = parse_qs(urlparse(href).query)
        vac_id = (qs.get("id") or [""])[0]
        if not vac_id:
            return None
        position = (qs.get("for") or [""])[0].title()
        vessel = (qs.get("on") or [""])[0]

        return Vacancy(
            source=self.name,
            vacancy_id=vac_id,
            position=position or clean(link.get_text(" ", strip=True)),
            vessel_type=vessel,
            salary=self._cell(row, "div.cellSalary"),
            join_date=self._cell(row, "div.cellBoarding"),
            contract_duration=self._cell(row, "div.cellDurationOfContract"),
            posted=self._cell(row, "div.cellPublishDate"),
            url=urljoin(self.base_url + "/", href),
        )

    @staticmethod
    def _cell(row, css: str) -> str:
        """Текст ячейки без подписи (span.memo)."""
        cell = row.select_one(css)
        if not cell:
            return ""
        memo = cell.select_one("span.memo")
        if memo:
            memo.extract()
        return clean(cell.get_text(" ", strip=True))

    def enrich(self, vacancy: Vacancy) -> None:
        try:
            soup = self.http.get_soup(vacancy.url)
        except Exception as exc:  # noqa: BLE001
            self.log.warning("detail failed %s: %s", vacancy.url, exc)
            return
        info = soup.select_one("div.jobInfo") or soup.select_one("div.additionalInfo")
        if info:
            vacancy.description = text_block(info.get_text("\n", strip=True))[:4000]
