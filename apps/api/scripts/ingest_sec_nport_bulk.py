#!/usr/bin/env python3
"""CLI: ingest SEC Form N-PORT bulk dataset."""

from __future__ import annotations

import argparse
import sys

from trade_sentinel_api.services.sec.nport_bulk import ingest_latest_nport_quarter


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest SEC N-PORT bulk ZIP")
    parser.add_argument("--quarter", help="Quarter label e.g. 2024q4")
    args = parser.parse_args()
    result = ingest_latest_nport_quarter(args.quarter)
    print(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
