"""Готовые списки для галочек в интерфейсе.

Каждый пункт: (подпись, [ключевые слова]). Подпись показывается в окне;
при выборе в фильтр уходят все ключевые слова пункта. Совпадение —
регистронезависимое, по подстроке (см. scraper/filtering.py), поэтому,
например, «tanker» поймает «Crude oil tanker».
"""
from __future__ import annotations

from typing import List, Tuple

Option = Tuple[str, List[str]]

# Должности (ранги). Несколько ключевых слов = учёт синонимов/сокращений.
POSITIONS: List[Option] = [
    ("Master / Captain", ["master", "captain"]),
    ("Chief Officer", ["chief officer", "chief mate", "c/o"]),
    ("2nd Officer", ["2nd officer", "second officer", "2/o"]),
    ("3rd Officer", ["3rd officer", "third officer", "3/o"]),
    ("Deck Cadet", ["deck cadet"]),
    ("Chief Engineer", ["chief engineer"]),
    ("2nd Engineer", ["2nd engineer", "second engineer"]),
    ("3rd Engineer", ["3rd engineer", "third engineer"]),
    ("4th Engineer", ["4th engineer", "fourth engineer"]),
    ("ETO / Electrician", ["eto", "electro", "electrician"]),
    ("Engine Cadet", ["engine cadet"]),
    ("Bosun", ["bosun", "boatswain"]),
    ("AB / Able Seaman", ["able seaman", "a/b"]),
    ("OS / Ordinary Seaman", ["ordinary seaman", "o/s"]),
    ("Fitter / Welder", ["fitter", "welder"]),
    ("Motorman", ["motorman"]),
    ("Oiler", ["oiler"]),
    ("Pumpman", ["pumpman"]),
    ("Cook", ["cook"]),
    ("Messman", ["messman"]),
    ("Steward", ["steward"]),
]

# Типы судов.
VESSEL_TYPES: List[Option] = [
    ("Bulk Carrier", ["bulk"]),
    ("Container", ["container"]),
    ("General Cargo", ["general cargo"]),
    ("Tanker (любой)", ["tanker"]),
    ("Oil Tanker", ["oil tanker", "crude", "product tanker"]),
    ("Chemical Tanker", ["chemical"]),
    ("Gas Carrier (LPG/LNG)", ["gas carrier", "lpg", "lng"]),
    ("Reefer", ["reefer"]),
    ("Multi-Purpose (MPP)", ["multi-purpose", "multipurpose", "mpp"]),
    ("Ro-Ro / Car Carrier", ["ro-ro", "roro", "car carrier", "pctc", "ro-pax", "ropax"]),
    ("Passenger / Cruise", ["passenger", "cruise"]),
    ("Offshore (PSV/AHTS)", ["offshore", "psv", "ahts", "supply"]),
    ("Tug", ["tug"]),
    ("Heavy Lift", ["heavy lift", "heavy-lift"]),
    ("Livestock", ["livestock"]),
]

# Сайты: (подпись, ключ сайта в SCRAPERS).
SITES: List[Tuple[str, str]] = [
    ("crewell.net", "crewell"),
    ("ukrcrewing.com.ua", "ukrcrewing"),
    ("maritime-zone.com", "maritime_zone"),
    ("crewdata.com", "crewdata"),
]
