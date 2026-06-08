#!/usr/bin/env python3
"""CLI: ingest SEC Form 13F bulk dataset for one or more quarters."""

from __future__ import annotations

import argparse
import sys

from trade_sentinel_api.services.sec.form13f_bulk import ingest_latest_13f_quarter


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest SEC Form 13F bulk ZIP into local index")
    parser.add_argument("--quarter", help="Quarter label e.g. 2024q4 (default: latest in manifest or 2024q4)")
    args = parser.parse_args()
    result = ingest_latest_13f_quarter(args.quarter)
    print(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
