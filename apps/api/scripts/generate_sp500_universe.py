#!/usr/bin/env python3
"""Refresh apps/api/data/sp500_universe.json from Wikipedia S&P 500 constituents."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "sp500_universe.json"


def fetch_sp500_tickers() -> list[str]:
    resp = httpx.get(
        WIKI_URL,
        headers={"User-Agent": "TradeSentinelAI/1.0"},
        follow_redirects=True,
        timeout=30.0,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", {"id": "constituents"})
    if table is None:
        raise RuntimeError("Could not find constituents table on Wikipedia page")
    tickers: list[str] = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if not cells:
            continue
        sym = cells[0].get_text(strip=True).upper().replace(".", "-")
        if sym:
            tickers.append(sym)
    return sorted(set(tickers))


def main() -> int:
    tickers = fetch_sp500_tickers()
    payload = {
        "description": (
            "Curated S&P 500 snapshot from Wikipedia constituents. "
            "Not live index membership."
        ),
        "tickers": tickers,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(tickers)} tickers to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
