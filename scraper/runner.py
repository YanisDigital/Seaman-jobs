"""Оркестрация прогона: сбор → фильтр → детали → Excel.

Используется и из CLI (main.py), и из графического интерфейса (gui.py),
чтобы логика была в одном месте.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from .excel_writer import write_xlsx
from .filtering import filter_vacancies
from .http_client import HttpClient
from .models import Vacancy
from .settings import Settings
from .sites import SCRAPERS

log = logging.getLogger("scraper.runner")

# Функция-флаг «пользователь нажал Стоп» (для GUI). Возвращает True — прервать.
StopFlag = Optional[Callable[[], bool]]


def _stopped(should_stop: StopFlag) -> bool:
    return bool(should_stop and should_stop())


def build_scraper(site: str, http: HttpClient, max_pages: int, settings: Settings):
    cls = SCRAPERS[site]
    if site == "maritime_zone":
        mz = settings.maritime_zone
        return cls(http, max_pages, headless=mz.headless,
                   challenge_wait=mz.challenge_wait, delay=settings.request.delay_seconds)
    return cls(http, max_pages)


def scrape_site(site: str, http: HttpClient, settings: Settings,
                max_pages: int, fetch_details: bool,
                should_stop: StopFlag = None) -> List[Vacancy]:
    scraper = build_scraper(site, http, max_pages, settings)
    log.info("=== %s: сбор списка ===", site)
    scraper.start()
    try:
        listed = scraper.collect()
        log.info("%s: собрано %d вакансий со списка", site, len(listed))

        matched = filter_vacancies(listed, settings.positions, settings.vessel_types)
        log.info("%s: после фильтра осталось %d", site, len(matched))

        if fetch_details:
            for i, vac in enumerate(matched, start=1):
                if _stopped(should_stop):
                    log.info("%s: остановлено пользователем (детали %d/%d)", site, i, len(matched))
                    break
                scraper.enrich(vac)
                if i % 10 == 0:
                    log.info("%s: детали %d/%d", site, i, len(matched))
    finally:
        scraper.finish()
    for vac in matched:
        vac.parse_salary()
    return matched


def resolve_sites(settings: Settings, sites: Optional[Sequence[str]]) -> List[str]:
    """Отобрать известные сайты, учесть флаг maritime_zone.enabled."""
    chosen = list(sites) if sites else list(settings.sites)
    chosen = [s for s in chosen if s in SCRAPERS]
    if "maritime_zone" in chosen and not settings.maritime_zone.enabled:
        chosen = [s for s in chosen if s != "maritime_zone"]
    return chosen


def run_scrape(settings: Settings,
               sites: Optional[Sequence[str]] = None,
               max_pages: Optional[int] = None,
               fetch_details: Optional[bool] = None,
               output_dir: Optional[str] = None,
               should_stop: StopFlag = None) -> "Tuple[List[Vacancy], Path]":
    """Собрать вакансии с выбранных сайтов и записать Excel. Вернуть (вакансии, путь)."""
    chosen = resolve_sites(settings, sites)
    if not chosen:
        raise ValueError("Не выбрано ни одного известного сайта. Доступно: "
                         + ", ".join(SCRAPERS))
    if max_pages is None:
        max_pages = settings.request.max_pages_per_site
    if fetch_details is None:
        fetch_details = settings.request.fetch_details
    output_dir = output_dir or settings.output_dir

    http = HttpClient(timeout=settings.request.timeout,
                      delay_seconds=settings.request.delay_seconds,
                      retries=settings.request.retries)

    all_matched: List[Vacancy] = []
    for site in chosen:
        if _stopped(should_stop):
            log.info("Остановлено пользователем — пропускаю оставшиеся сайты.")
            break
        try:
            all_matched.extend(
                scrape_site(site, http, settings, max_pages, fetch_details, should_stop))
        except Exception as exc:  # noqa: BLE001 - ошибка одного сайта не валит остальные
            log.exception("%s: ошибка сбора (%s) — продолжаю с другими сайтами", site, exc)

    if not all_matched:
        log.warning("Подходящих вакансий не найдено. Проверьте фильтры.")
    path = write_xlsx(all_matched, output_dir)
    log.info("Готово: %d вакансий -> %s", len(all_matched), path)
    return all_matched, path
