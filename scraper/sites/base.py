"""Базовый интерфейс скрейпера и общие помощники парсинга."""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import Iterator, List

from ..http_client import HttpClient
from ..models import Vacancy


def clean(text: str) -> str:
    """Свернуть пробелы/переводы строк в один пробел."""
    return " ".join((text or "").split())


def text_block(text: str) -> str:
    """Нормализовать многострочный текст: убрать лишние пустые строки."""
    lines = [clean(ln) for ln in (text or "").splitlines()]
    return "\n".join(ln for ln in lines if ln)


_SPLIT_ON = re.compile(r"\s+on\s+", re.IGNORECASE)


def split_position_vessel(title: str) -> "tuple[str, str]":
    """'Chief Engineer on Bulk Carrier' -> ('Chief Engineer', 'Bulk Carrier')."""
    title = clean(title)
    parts = _SPLIT_ON.split(title, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return title, ""


class BaseScraper(ABC):
    """Каждый сайт реализует list_vacancies() и enrich()."""

    name: str = ""        # ключ в config.yaml
    base_url: str = ""    # https://example.com

    def __init__(self, http: HttpClient, max_pages: int = 0):
        self.http = http
        self.max_pages = max_pages          # 0 = все страницы
        self.log = logging.getLogger(f"scraper.{self.name}")

    @abstractmethod
    def list_vacancies(self) -> Iterator[Vacancy]:
        """Пройти страницы списка и выдать вакансии с базовыми полями."""

    def enrich(self, vacancy: Vacancy) -> None:
        """Дозагрузить страницу-деталь и дополнить vacancy (по умолчанию — ничего)."""
        return None

    def start(self) -> None:
        """Подготовка ресурсов (например, браузера). По умолчанию — ничего."""
        return None

    def finish(self) -> None:
        """Освобождение ресурсов. По умолчанию — ничего."""
        return None

    def __enter__(self) -> "BaseScraper":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.finish()

    # --- утилиты для наследников ---

    def _page_limit_reached(self, page: int) -> bool:
        return self.max_pages and page > self.max_pages

    def collect(self) -> List[Vacancy]:
        return list(self.list_vacancies())
