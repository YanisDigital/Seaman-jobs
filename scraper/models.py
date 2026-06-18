"""Единая модель данных вакансии и разбор зарплаты."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import Optional, Tuple


@dataclass
class Vacancy:
    """Одна вакансия. Поля общие для всех сайтов; недостающее = пустая строка."""

    source: str = ""               # сайт-источник
    vacancy_id: str = ""           # ID вакансии на сайте
    position: str = ""             # должность / ранг
    vessel_type: str = ""          # тип судна
    fleet: str = ""                # тип флота (если есть)
    salary: str = ""               # зарплата как на сайте (например "3000-3200$")
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    currency: str = ""             # USD / EUR / ...
    join_date: str = ""            # дата посадки / начала контракта
    contract_duration: str = ""    # длительность контракта
    company: str = ""              # крюинг / судовладелец
    posted: str = ""               # когда опубликовано (как на сайте)
    extra: str = ""                # доп. поля со страницы списка (просмотры и т.п.)
    description: str = ""          # подробности со страницы-деталь
    url: str = ""                  # кликабельная ссылка на вакансию
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def parse_salary(self) -> None:
        """Заполнить salary_min/max/currency из строки salary."""
        self.salary_min, self.salary_max, self.currency = parse_salary(self.salary)


# Порядок и заголовки колонок для Excel (ключ поля -> заголовок).
COLUMNS: "list[Tuple[str, str]]" = [
    ("source", "Сайт"),
    ("position", "Должность"),
    ("vessel_type", "Тип судна"),
    ("fleet", "Флот"),
    ("salary", "Зарплата"),
    ("salary_min", "ЗП min"),
    ("salary_max", "ЗП max"),
    ("currency", "Валюта"),
    ("join_date", "Дата посадки"),
    ("contract_duration", "Контракт"),
    ("company", "Компания"),
    ("posted", "Опубликовано"),
    ("extra", "Доп."),
    ("description", "Описание / детали"),
    ("vacancy_id", "ID"),
    ("url", "Ссылка"),
    ("scraped_at", "Собрано"),
]


def _valid_field_keys() -> set:
    return {f.name for f in fields(Vacancy)}


# Сопоставление символов/слов валют к коду.
_CURRENCY = {
    "$": "USD", "usd": "USD", "дол": "USD",
    "€": "EUR", "eur": "EUR", "евро": "EUR",
    "£": "GBP", "gbp": "GBP",
}

_NUM_RE = re.compile(r"\d[\d\s.,]*")


def _to_number(token: str) -> Optional[float]:
    token = token.replace(" ", "").replace(" ", "")
    # "3.200" / "3,200" -> убираем разделители тысяч; десятичные в зарплатах редки
    token = token.replace(",", "").replace(".", "")
    if not token:
        return None
    try:
        return float(token)
    except ValueError:
        return None


def parse_salary(raw: str) -> "Tuple[Optional[float], Optional[float], str]":
    """Разобрать строку зарплаты в (min, max, currency).

    Понимает форматы: "3000-3200$", "to 7000 $", "from 4000 $",
    "2200-2500 €", "$3000 - 3200", "6300-6800 $".
    """
    if not raw:
        return None, None, ""
    low = raw.lower()

    currency = ""
    for token, code in _CURRENCY.items():
        if token in low:
            currency = code
            break

    numbers = [n for n in (_to_number(m.group(0)) for m in _NUM_RE.finditer(raw)) if n]
    if not numbers:
        return None, None, currency

    if len(numbers) == 1:
        only = numbers[0]
        if "to" in low or "до" in low or low.strip().startswith("<"):
            return None, only, currency        # "to 7000" -> верхняя граница
        if "from" in low or "от" in low or "от " in low:
            return only, None, currency         # "from 4000" -> нижняя граница
        return only, only, currency
    return min(numbers), max(numbers), currency
