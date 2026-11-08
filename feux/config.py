from __future__ import annotations

import pathlib
from functools import lru_cache

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
SERIES_DIR = DATA_DIR / "series"
DOCS_DIR = ROOT / "docs"
RULES_PATH = ROOT / "rules.yaml"

for _d in (RAW_DIR, SERIES_DIR, DOCS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def rules() -> dict:
    with open(RULES_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)
