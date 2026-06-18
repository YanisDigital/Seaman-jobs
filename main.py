"""CLI: собрать вакансии с сайтов, отфильтровать и сохранить в Excel.

Примеры:
    python main.py                      # все сайты из config.yaml
    python main.py --site crewell       # только один сайт
    python main.py --limit 2            # не больше 2 страниц списка с каждого сайта
    python main.py --no-details         # быстро, без дозагрузки страниц-деталей
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import List

from scraper.excel_writer import write_xlsx
from scraper.filtering import filter_vacancies
from scraper.http_client import HttpClient
from scraper.models import Vacancy
from scraper.settings import Settings, load_settings
from scraper.sites import SCRAPERS


def _setup_console() -> None:
    # Windows-консоль по умолчанию cp1252 — переключаем на utf-8 ради кириллицы.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        datefmt="%H:%M:%S")


def _build_scraper(site: str, http: HttpClient, max_pages: int, settings: Settings):
    cls = SCRAPERS[site]
    if site == "maritime_zone":
        mz = settings.maritime_zone
        return cls(http, max_pages, headless=mz.headless,
                   challenge_wait=mz.challenge_wait, delay=settings.request.delay_seconds)
    return cls(http, max_pages)


def _scrape_site(site: str, http: HttpClient, settings: Settings,
                 max_pages: int, fetch_details: bool, log: logging.Logger) -> List[Vacancy]:
    scraper = _build_scraper(site, http, max_pages, settings)
    log.info("=== %s: сбор списка ===", site)
    scraper.start()
    try:
        listed = scraper.collect()
        log.info("%s: собрано %d вакансий со списка", site, len(listed))

        matched = filter_vacancies(listed, settings.positions, settings.vessel_types)
        log.info("%s: после фильтра осталось %d", site, len(matched))

        if fetch_details:
            for i, vac in enumerate(matched, start=1):
                scraper.enrich(vac)
                if i % 10 == 0:
                    log.info("%s: детали %d/%d", site, i, len(matched))
    finally:
        scraper.finish()
    for vac in matched:
        vac.parse_salary()
    return matched


def main(argv: "List[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="Сбор вакансий моряков с 3 сайтов")
    parser.add_argument("--config", default="config.yaml", help="путь к config.yaml")
    parser.add_argument("--site", action="append",
                        help="опросить только этот сайт (можно указать несколько раз)")
    parser.add_argument("--limit", type=int, default=None,
                        help="максимум страниц списка с каждого сайта (для отладки)")
    parser.add_argument("--no-details", action="store_true",
                        help="не дозагружать страницы-детали")
    parser.add_argument("--output", default=None, help="папка для .xlsx (переопределяет config)")
    args = parser.parse_args(argv)

    _setup_console()
    log = logging.getLogger("scraper.main")

    settings = load_settings(args.config)
    sites = args.site or settings.sites
    sites = [s for s in sites if s in SCRAPERS]
    if not sites:
        log.error("Не выбрано ни одного известного сайта. Доступно: %s",
                  ", ".join(SCRAPERS))
        return 2

    max_pages = args.limit if args.limit is not None else settings.request.max_pages_per_site
    fetch_details = settings.request.fetch_details and not args.no_details
    output_dir = args.output or settings.output_dir

    http = HttpClient(timeout=settings.request.timeout,
                      delay_seconds=settings.request.delay_seconds,
                      retries=settings.request.retries)

    all_matched: List[Vacancy] = []
    for site in sites:
        try:
            all_matched.extend(
                _scrape_site(site, http, settings, max_pages, fetch_details, log))
        except Exception as exc:  # noqa: BLE001 - ошибка одного сайта не валит остальные
            log.exception("%s: ошибка сбора (%s) — продолжаю с другими сайтами", site, exc)

    if not all_matched:
        log.warning("Подходящих вакансий не найдено. Проверьте фильтры в config.yaml.")
    path = write_xlsx(all_matched, output_dir)
    log.info("Готово: %d вакансий -> %s", len(all_matched), path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
