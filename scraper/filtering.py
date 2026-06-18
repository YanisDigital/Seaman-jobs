"""Локальная фильтрация вакансий по должности и типу судна."""
from __future__ import annotations

from typing import Iterable, List

from .models import Vacancy


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def _matches_any(value: str, keywords: Iterable[str]) -> bool:
    """True, если value содержит хотя бы одно ключевое слово (по подстроке).

    Пустой список ключевых слов = совпадение всегда (не фильтруем).
    """
    keys = [_norm(k) for k in keywords if _norm(k)]
    if not keys:
        return True
    v = _norm(value)
    return any(k in v for k in keys)


def matches(vacancy: Vacancy, positions: Iterable[str], vessel_types: Iterable[str]) -> bool:
    """Вакансия проходит, если совпали И должность, И тип судна."""
    return (_matches_any(vacancy.position, positions)
            and _matches_any(vacancy.vessel_type, vessel_types))


def filter_vacancies(vacancies: Iterable[Vacancy],
                     positions: Iterable[str],
                     vessel_types: Iterable[str]) -> List[Vacancy]:
    positions = list(positions)
    vessel_types = list(vessel_types)
    return [v for v in vacancies if matches(v, positions, vessel_types)]
