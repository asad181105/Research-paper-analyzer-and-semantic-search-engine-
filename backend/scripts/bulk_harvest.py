"""Discover papers from multiple sources and queue bulk import.

Usage:
  python scripts/bulk_harvest.py --query "dense retrieval" --max 50
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from app.services.bulk_import import import_item  # noqa: E402
from app.services.discovery import discover  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--query", required=True)
    p.add_argument("--max", type=int, default=30, help="max per source")
    p.add_argument("--sync", action="store_true", help="import synchronously (slow)")
    args = p.parse_args()

    app = create_app()
    with app.app_context():
        d = discover(args.query, max_per_source=args.max)
        items = []
        for row in d["merged"]:
            if row.get("arxiv_id") or row.get("pdf_url"):
                items.append(row)
        print(f"Found {len(items)} importable items (of {d['total']} merged)")
        if args.sync:
            for row in items:
                print(import_item(row))
        else:
            from app.services.bulk_import import queue_bulk_import

            queue_bulk_import(items, delay_sec=2.0)
            print(f"Queued {len(items)} imports in background")


if __name__ == "__main__":
    main()
