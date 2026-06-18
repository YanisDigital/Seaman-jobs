"""Скрейпер crewell.net (статический HTML)."""
from __future__ import annotations

import re
from typing import Dict, Iterator
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import Vacancy
from .base import BaseScraper, clean, split_position_vessel, text_block

_HARD_PAGE_CAP = 500


class CrewellScraper(BaseScraper):
    name = "crewell"
    base_url = "https://crewell.net"

    LIST_URL = "https://crewell.net/en/vacancies/?page={page}"

    def list_vacancies(self) -> Iterator[Vacancy]:
        last_page = None
        page = 1
        while True:
            if self._page_limit_reached(page) or page > _HARD_PAGE_CAP:
                break
            url = self.LIST_URL.format(page=page)
            soup = self.http.get_soup(url)
            items = soup.select("div.vacancy-item[data-item-id]")
            if not items:
                break
            self.log.info("page %s: %d vacancies", page, len(items))
            for item in items:
                vac = self._parse_item(item)
                if vac:
                    yield vac
            if last_page is None:
                last_page = self._detect_last_page(soup)
            if last_page and page >= last_page:
                break
            page += 1

    def _detect_last_page(self, soup: BeautifulSoup) -> "int | None":
        pages = []
        for a in soup.select("a[href*='page=']"):
            m = re.search(r"page=(\d+)", a.get("href", ""))
            if m:
                pages.append(int(m.group(1)))
        return max(pages) if pages else None

    def _parse_item(self, item) -> "Vacancy | None":
        title_a = item.select_one("a.vacancyTitle")
        if not title_a:
            return None
        position, vessel = split_position_vessel(title_a.get_text(" ", strip=True))
        href = title_a.get("href", "")
        rows = self._info_rows(item)

        company_a = item.select_one("div.company-wrapper a")
        posted_el = item.select_one("[title='Date of publication'] strong")
        views_el = None
        eye = item.select_one("i.icon-eye")
        if eye:
            parent = eye.find_parent()
            if parent:
                views_el = parent.find("strong")

        return Vacancy(
            source=self.name,
            vacancy_id=clean(item.get("data-item-id", "")),
            position=position,
            vessel_type=vessel,
            salary=rows.get("salary", ""),
            join_date=rows.get("join date", ""),
            contract_duration=rows.get("duration", ""),
            company=clean(company_a.get_text(" ", strip=True)) if company_a else "",
            posted=clean(posted_el.get_text(" ", strip=True)) if posted_el else "",
            extra=("Views: " + clean(views_el.get_text(strip=True))) if views_el else "",
            url=urljoin(self.base_url, href),
        )

    @staticmethod
    def _info_rows(item) -> Dict[str, str]:
        """Собрать label->value из div.info-row / div.info-row-sm."""
        result: Dict[str, str] = {}
        for row in item.select("div.info-row, div.info-row-sm"):
            label_el = row.select_one("span.row-title")
            if not label_el:
                continue
            label = clean(label_el.get_text(strip=True)).rstrip(":").lower()
            full = clean(row.get_text(" ", strip=True))
            value = full[len(label_el.get_text(strip=True)):].strip() if full else ""
            # убрать остаток метки, если регистр/двоеточие отличаются
            value = re.sub(r"^[:\s]+", "", value)
            result[label] = value
        return result

    def enrich(self, vacancy: Vacancy) -> None:
        try:
            soup = self.http.get_soup(vacancy.url, referer=self.LIST_URL.format(page=1))
        except Exception as exc:  # noqa: BLE001 - одна вакансия не должна валить процесс
            self.log.warning("detail failed %s: %s", vacancy.url, exc)
            return
        pairs = []
        for tr in soup.select("div.inner table tr"):
            title_td = tr.select_one("td.rowTitle")
            if not title_td:
                continue
            cells = tr.find_all("td")
            if len(cells) < 2:
                continue
            label = clean(title_td.get_text(" ", strip=True)).rstrip(":")
            value = clean(cells[-1].get_text(" ", strip=True))
            if not value or value.lower().startswith("please complete"):
                continue
            pairs.append((label.lower(), label, value))

        for low, _, value in pairs:
            if low.startswith("vessel type") and value:
                vacancy.vessel_type = value
            elif low.startswith("salary") and value:
                vacancy.salary = value

        skip = {"position", "salary", "join date", "duration"}
        details = [f"{label}: {value}" for low, label, value in pairs if low not in skip]
        if details:
            vacancy.description = text_block("\n".join(details))
