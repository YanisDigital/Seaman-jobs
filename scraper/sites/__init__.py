"""Скрейперы конкретных сайтов."""
from __future__ import annotations

from typing import Dict, Type

from .base import BaseScraper
from .crewell import CrewellScraper
from .maritime_zone import MaritimeZoneScraper
from .ukrcrewing import UkrCrewingScraper

# Реестр: имя сайта (как в config.yaml) -> класс скрейпера.
SCRAPERS: "Dict[str, Type[BaseScraper]]" = {
    CrewellScraper.name: CrewellScraper,
    UkrCrewingScraper.name: UkrCrewingScraper,
    MaritimeZoneScraper.name: MaritimeZoneScraper,
}
