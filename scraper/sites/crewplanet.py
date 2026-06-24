"""Скрейпер crewplanet.eu (статический HTML, карточки с микроразметкой schema.org).

Только для десктоп-версии (в облако не добавляем). Защиты нет, обычные запросы.
"""
from __future__ import annotations

from typing import Iterator, Set
from urllib.parse import urljoin

from ..http_client import HttpError
from ..models import Vacancy
from .base import BaseScraper, clean, text_block

_HARD_PAGE_CAP = 200

# Базовый URL списка со «сброшенными» фильтрами (так делает сам сайт); пагинация — /page/N.
_FILTER = ("/v2/en/vacancies/search/filter/VacFilter%5BpositionId%5D/0/"
           "VacFilter%5BfleetId%5D/0/VacFilter%5Benglish_level%5D/0/"
           "VacFilter%5BtypeOfCandidates%5D/all/VacFilter%5Bdepartment%5D/0/"
           "VacFilter%5BminSalary%5D/0/VacFilter%5BmaxSalary%5D/0/"
           "VacFilter%5BminGrt%5D/0/VacFilter%5BmaxGrt%5D/0/"
           "VacFilter%5BminHp%5D/0/VacFilter%5BmaxHp%5D/0/VacFilter%5Bcompany%5D/")


class CrewPlanetScraper(BaseScraper):
    name = "crewplanet"
    base_url = "https://crewplanet.eu"

    def _list_url(self, page: int) -> str:
        # сайт использует двойной слэш перед page (…%5Bcompany%5D//page/N) — иначе
        # пагинация не срабатывает и возвращается первая страница.
        path = _FILTER if page <= 1 else _FILTER + "/page/" + str(page)
        return urljoin(self.base_url, path)

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
            cards = soup.select("a.vacancy_card[data-id]")
            new_on_page = 0
            for card in cards:
                vac = self._parse_card(card)
                if not vac or vac.vacancy_id in seen:
                    continue
                seen.add(vac.vacancy_id)
                new_on_page += 1
                yield vac
            self.log.info("page %s: %d new vacancies", page, new_on_page)
            if new_on_page == 0:
                break
            page += 1

    def _parse_card(self, card) -> "Vacancy | None":
        vac_id = clean(card.get("data-id", ""))
        if not vac_id:
            return None
        # должность (без значков-флагов) + тип судна
        title_el = card.select_one("div.left .title")
        if title_el:
            for f in title_el.select(".flags"):
                f.decompose()
        position = clean(title_el.get_text(" ", strip=True)) if title_el else ""
        vessel = self._cell(card, "div.title2")
        if vessel.lower().startswith("on "):
            vessel = vessel[3:].strip()

        created = self._cell(card, "div.created")
        posted, company = created, ""
        if "," in created:
            posted, company = (p.strip() for p in created.rsplit(",", 1))

        return Vacancy(
            source=self.name,
            vacancy_id=vac_id,
            position=position,
            vessel_type=vessel,
            salary=self._cell(card, "div.salary"),
            contract_duration=self._cell(card, "div.tenure"),
            join_date=self._cell(card, "div.loading"),
            posted=posted,
            company=company,
            url=urljoin(self.base_url, card.get("href", "")),
        )

    @staticmethod
    def _cell(card, css: str) -> str:
        el = card.select_one(css)
        return clean(el.get_text(" ", strip=True)) if el else ""

    def enrich(self, vacancy: Vacancy) -> None:
        try:
            soup = self.http.get_soup(vacancy.url)
        except Exception as exc:  # noqa: BLE001
            self.log.warning("detail failed %s: %s", vacancy.url, exc)
            return
        block = (soup.select_one("[itemprop='description']")
                 or soup.select_one("div.vacancy_text")
                 or soup.select_one("div.description"))
        if block:
            vacancy.description = text_block(block.get_text("\n", strip=True))[:4000]
