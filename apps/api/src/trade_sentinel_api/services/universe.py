"""Curated ticker universes for bounded market scans."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

_SP100_PATH = Path(__file__).resolve().parents[3] / "data" / "sp100_universe.json"
_SP500_PATH = Path(__file__).resolve().parents[3] / "data" / "sp500_universe.json"

UniverseName = Literal["sp100", "sp500"]


def _load_tickers(path: Path) -> list[str]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [str(t).upper().strip() for t in data.get("tickers", []) if str(t).strip()]


@lru_cache(maxsize=1)
def load_sp100_tickers() -> list[str]:
    return _load_tickers(_SP100_PATH)


@lru_cache(maxsize=1)
def load_sp500_tickers() -> list[str]:
    return _load_tickers(_SP500_PATH)


def load_universe_tickers(name: UniverseName | str) -> list[str]:
    key = name.strip().lower()
    if key == "sp500":
        return load_sp500_tickers()
    return load_sp100_tickers()
