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

from scraper.runner import run_scrape
from scraper.settings import load_settings
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
    fetch_details = False if args.no_details else None  # None = взять из настроек
    try:
        run_scrape(settings,
                   sites=args.site,
                   max_pages=args.limit,
                   fetch_details=fetch_details,
                   output_dir=args.output)
    except ValueError as exc:
        log.error("%s", exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
