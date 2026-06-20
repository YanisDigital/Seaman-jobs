"""Загрузка и валидация config.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml


@dataclass
class RequestSettings:
    delay_seconds: float = 1.0
    timeout: int = 25
    retries: int = 4
    max_pages_per_site: int = 0
    fetch_details: bool = True


@dataclass
class MaritimeZoneSettings:
    enabled: bool = True
    headless: bool = True
    challenge_wait: int = 25


@dataclass
class Settings:
    positions: List[str] = field(default_factory=list)
    vessel_types: List[str] = field(default_factory=list)
    sites: List[str] = field(default_factory=lambda: ["crewell", "ukrcrewing", "maritime_zone"])
    request: RequestSettings = field(default_factory=RequestSettings)
    maritime_zone: MaritimeZoneSettings = field(default_factory=MaritimeZoneSettings)
    output_dir: str = "output"


def load_settings(path: "str | Path") -> Settings:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    req = RequestSettings(**(data.get("request") or {}))
    mz = MaritimeZoneSettings(**(data.get("maritime_zone") or {}))
    return Settings(
        positions=[str(p) for p in (data.get("positions") or [])],
        vessel_types=[str(v) for v in (data.get("vessel_types") or [])],
        sites=[str(s) for s in (data.get("sites") or ["crewell", "ukrcrewing", "maritime_zone"])],
        request=req,
        maritime_zone=mz,
        output_dir=str(data.get("output_dir") or "output"),
    )
