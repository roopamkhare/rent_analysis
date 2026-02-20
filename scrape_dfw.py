#!/usr/bin/env python3
"""
DFW Metroplex multi-zipcode scraper.

Runs zillow_zip_search.scrape_zipcode() for every zipcode in the DFW area,
merges all results into a single listings.json, and (optionally) updates
historical snapshots.

Usage:
    python scrape_dfw.py                   # headless (CI / GitHub Actions)
    python scrape_dfw.py --headful         # headed browser (local, bypasses PerimeterX)
    python scrape_dfw.py --headful --max-pages 3
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from zillow_zip_search import scrape_zipcode

# ── DFW Zipcodes ────────────────────────────────────────────────
# Northern DFW corridor — suburbs popular for buy-and-rent investment
DFW_ZIPCODES = [
    # McKinney
    "75069", "75070", "75071",
    # Frisco
    "75033", "75034", "75035",
    # Prosper / Celina
    "75078", "75009",
    # Allen
    "75002", "75013",
    # Plano
    "75023", "75024", "75025", "75074", "75075", "75093",
    # Richardson
    "75080", "75081", "75082",
    # Little Elm / The Colony
    "75056", "75068",
    # Denton
    "76201", "76205", "76210",
]


async def scrape_all(
    zipcodes: list[str],
    headless: bool = True,
    max_pages: int = 20,
) -> dict:
    """Scrape every zipcode and merge into one dataset."""
    all_listings = []
    seen_zpids: set[str] = set()
    per_zip_stats: dict[str, int] = {}

    for i, zipcode in enumerate(zipcodes, 1):
        print(f"\n{'='*60}")
        print(f"  [{i}/{len(zipcodes)}] Scraping zipcode {zipcode} …")
        print(f"{'='*60}")

        try:
            result = await scrape_zipcode(
                zipcode,
                headless=headless,
                max_pages=max_pages,
            )
            new_count = 0
            for listing in result.get("listings", []):
                zpid = str(listing.get("zpid", ""))
                if zpid and zpid not in seen_zpids:
                    seen_zpids.add(zpid)
                    all_listings.append(listing)
                    new_count += 1
            per_zip_stats[zipcode] = new_count
            print(f"  ✓ {zipcode}: {new_count} new unique listings")
        except Exception as e:
            print(f"  ✗ {zipcode}: FAILED — {e}")
            per_zip_stats[zipcode] = 0

        # Polite delay between zipcodes to avoid blocking
        if i < len(zipcodes):
            delay = 8
            print(f"  Waiting {delay}s before next zipcode …")
            await asyncio.sleep(delay)

    # ── Build merged output ─────────────────────────────────────
    today = time.strftime("%Y-%m-%d")
    output = {
        "region": "dfw",
        "scraped_at": today,
        "zipcodes": zipcodes,
        "total_listings": len(all_listings),
        "per_zipcode": per_zip_stats,
        "listings": all_listings,
    }

    # Save merged JSON
    Path("json").mkdir(exist_ok=True)
    merged_path = Path("json/dfw_listings.json")
    merged_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"\n{'='*60}")
    print(f"  TOTAL: {len(all_listings)} unique listings across {len(zipcodes)} zipcodes")
    print(f"  Saved → {merged_path}")

    # Also copy to frontend/public for static build
    frontend_path = Path("frontend/public/listings.json")
    if frontend_path.parent.exists():
        frontend_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
        print(f"  Copied → {frontend_path}")

    # Print per-zipcode summary
    print(f"\n  Per-zipcode breakdown:")
    for zc, count in sorted(per_zip_stats.items()):
        print(f"    {zc}: {count} listings")

    return output


def main():
    headful = "--headful" in sys.argv
    max_pages = 20
    if "--max-pages" in sys.argv:
        idx = sys.argv.index("--max-pages")
        if idx + 1 < len(sys.argv):
            max_pages = int(sys.argv[idx + 1])

    # Allow filtering to specific zipcodes via --zipcodes 75071,75070
    zipcodes = DFW_ZIPCODES
    if "--zipcodes" in sys.argv:
        idx = sys.argv.index("--zipcodes")
        if idx + 1 < len(sys.argv):
            zipcodes = sys.argv[idx + 1].split(",")

    print(f"Scraping {len(zipcodes)} DFW zipcodes (headless={not headful}, max_pages={max_pages})")
    print(f"Zipcodes: {', '.join(zipcodes)}")

    asyncio.run(scrape_all(zipcodes, headless=not headful, max_pages=max_pages))


if __name__ == "__main__":
    main()
