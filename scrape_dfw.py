#!/usr/bin/env python3
"""
DFW Metroplex multi-zipcode scraper.

Uses a SINGLE persistent browser session across all zipcodes to avoid
PerimeterX bot detection. Aborts after repeated consecutive blocks.

Usage:
    python scrape_dfw.py                   # headless (CI / GitHub Actions)
    python scrape_dfw.py --headful         # headed browser (local, bypasses PerimeterX)
    python scrape_dfw.py --headful --max-pages 3
    python scrape_dfw.py --headful --zipcodes 75071,75070
"""

import asyncio
import json
import random
import re
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from zillow_zip_search import (
    _extract_listings_from_search,
    _get_total_pages,
    normalize_listing,
)

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

MAX_CONSECUTIVE_FAILURES = 3


async def _scrape_one_zipcode(
    page,
    zipcode: str,
    max_pages: int,
    global_seen: set[str],
) -> list[dict]:
    """Scrape a single zipcode using an EXISTING browser page.
    Returns list of NEW (globally deduped) listing dicts."""
    listings: list[dict] = []
    total_pages = None
    page_num = 1

    while page_num <= max_pages:
        url = f"https://www.zillow.com/homes/{zipcode}_rb/"
        if page_num > 1:
            url = f"https://www.zillow.com/homes/{zipcode}_rb/{page_num}_p/"

        print(f"\n── Page {page_num} ──  {url}")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        except Exception as e:
            print(f"  Navigation error: {e}")
            return listings

        await page.wait_for_timeout(random.randint(3000, 6000))

        title = await page.title()
        print(f"  Title: {title}")

        if "denied" in title.lower() or "captcha" in title.lower():
            print("  ❌ Blocked by PerimeterX!")
            return listings  # empty → caller counts as failure

        html = await page.content()
        print(f"  HTML: {len(html):,} chars")

        m = re.search(
            r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>',
            html, re.DOTALL,
        )
        if not m:
            print("  ✗ No __NEXT_DATA__ found")
            return listings

        next_data = json.loads(m.group(1))
        print(f"  ✓ __NEXT_DATA__ ({len(m.group(1)):,} chars)")

        if total_pages is None:
            total_pages = _get_total_pages(next_data)
            print(f"  Total pages estimated: {total_pages}")
            max_pages = min(max_pages, total_pages)

        raw_listings = _extract_listings_from_search(next_data)
        if not raw_listings:
            print("  ✗ No listings found on this page")
            break

        new_count = 0
        for raw in raw_listings:
            cleaned = normalize_listing(raw)
            zpid = str(cleaned.get("zpid", ""))
            if zpid and zpid not in global_seen:
                listings.append(cleaned)
                new_count += 1

        print(f"  ✓ {new_count} new listings (zip total: {len(listings)})")

        if new_count == 0:
            print("  No new listings — stopping pagination.")
            break

        page_num += 1
        if page_num <= max_pages:
            delay = random.uniform(3.0, 7.0)
            print(f"  Waiting {delay:.1f}s before next page …")
            await page.wait_for_timeout(int(delay * 1000))

    return listings


async def scrape_all(
    zipcodes: list[str],
    headless: bool = True,
    max_pages: int = 20,
) -> dict:
    """Scrape all zipcodes using ONE shared browser session."""
    all_listings: list[dict] = []
    seen_zpids: set[str] = set()
    per_zip_stats: dict[str, int] = {}
    consecutive_failures = 0
    captcha_retries = 0
    max_captcha_retries = 3

    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=headless)
        ctx = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = await ctx.new_page()

        # ── Warm up session ─────────────────────────────────────
        print("Warming up session — visiting Zillow homepage …")
        try:
            await page.goto("https://www.zillow.com/", wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(random.randint(3000, 5000))
            await page.evaluate("window.scrollBy(0, 300)")
            await page.wait_for_timeout(random.randint(1000, 2000))
            title = await page.title()
            print(f"  Homepage title: {title}")
            if "denied" in title.lower() or "captcha" in title.lower():
                print("  ⚠️  Blocked even on homepage — PerimeterX is aggressive.")
                print("  Waiting 60s for you to solve the CAPTCHA in the browser …")
                await page.wait_for_timeout(60_000)
                # Re-check after wait
                try:
                    await page.goto("https://www.zillow.com/", wait_until="domcontentloaded", timeout=30_000)
                    await page.wait_for_timeout(3000)
                    title2 = await page.title()
                    if "denied" in title2.lower() or "captcha" in title2.lower():
                        print("  Still blocked. Aborting.")
                        await browser.close()
                        return _empty_output(zipcodes)
                    print("  ✓ CAPTCHA solved! Continuing …")
                except Exception:
                    print("  Still blocked after wait. Aborting.")
                    await browser.close()
                    return _empty_output(zipcodes)
        except Exception as e:
            print(f"  Warmup error: {e}")

        print("Session ready. Starting scrape …\n")

        # ── Main loop ───────────────────────────────────────────
        for i, zipcode in enumerate(zipcodes, 1):
            print(f"\n{'='*60}")
            print(f"  [{i}/{len(zipcodes)}] Scraping zipcode {zipcode} …")
            print(f"{'='*60}")

            zip_listings = await _scrape_one_zipcode(page, zipcode, max_pages, seen_zpids)

            if not zip_listings:
                consecutive_failures += 1
                per_zip_stats[zipcode] = 0
                print(f"  ✗ {zipcode}: 0 listings "
                      f"(consecutive failures: {consecutive_failures}/{MAX_CONSECUTIVE_FAILURES})")

                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    captcha_retries += 1
                    if captcha_retries > max_captcha_retries:
                        print(f"\n  🛑 Exhausted {max_captcha_retries} CAPTCHA retries — aborting for real.")
                        break
                    print(f"\n  🛑 {MAX_CONSECUTIVE_FAILURES} consecutive failures — pausing.")
                    print(f"  PerimeterX is blocking. Waiting 60s for CAPTCHA solve … "
                          f"(attempt {captcha_retries}/{max_captcha_retries})")
                    await page.wait_for_timeout(60_000)
                    consecutive_failures = 0
                    print("  Retrying …")
                    continue

                wait = random.randint(15, 25)
                print(f"  Waiting {wait}s before next zipcode (cooldown) …")
                await page.wait_for_timeout(wait * 1000)
            else:
                consecutive_failures = 0
                for listing in zip_listings:
                    zpid = str(listing.get("zpid", ""))
                    seen_zpids.add(zpid)
                    all_listings.append(listing)
                per_zip_stats[zipcode] = len(zip_listings)
                print(f"  ✓ {zipcode}: {len(zip_listings)} new unique listings")

                # Save per-zipcode JSON too
                Path("json").mkdir(exist_ok=True)
                per_zip_out = {
                    "zipcode": zipcode,
                    "total_listings": len(zip_listings),
                    "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "listings": zip_listings,
                }
                Path(f"json/zillow_{zipcode}_listings.json").write_text(
                    json.dumps(per_zip_out, indent=2, default=str), encoding="utf-8"
                )

                if i < len(zipcodes):
                    delay = random.randint(8, 15)
                    print(f"  Waiting {delay}s before next zipcode …")
                    await page.wait_for_timeout(delay * 1000)

        await ctx.close()

    # ── Save merged output ──────────────────────────────────────
    today = time.strftime("%Y-%m-%d")
    output = {
        "region": "dfw",
        "scraped_at": today,
        "zipcodes": zipcodes,
        "total_listings": len(all_listings),
        "per_zipcode": per_zip_stats,
        "listings": all_listings,
    }

    Path("json").mkdir(exist_ok=True)
    merged_path = Path("json/dfw_listings.json")
    merged_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"\n{'='*60}")
    print(f"  TOTAL: {len(all_listings)} unique listings across {len(zipcodes)} zipcodes")
    print(f"  Saved → {merged_path}")

    frontend_path = Path("frontend/public/listings.json")
    if frontend_path.parent.exists():
        frontend_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
        print(f"  Copied → {frontend_path}")

    successful = sum(1 for v in per_zip_stats.values() if v > 0)
    failed = sum(1 for v in per_zip_stats.values() if v == 0)
    print(f"\n  Summary: {successful} succeeded, {failed} failed")
    print(f"  Per-zipcode breakdown:")
    for zc, count in sorted(per_zip_stats.items()):
        print(f"    {'✓' if count > 0 else '✗'} {zc}: {count} listings")

    return output


def _empty_output(zipcodes: list[str]) -> dict:
    return {
        "region": "dfw", "scraped_at": time.strftime("%Y-%m-%d"),
        "zipcodes": zipcodes, "total_listings": 0,
        "per_zipcode": {}, "listings": [],
    }


def main():
    headful = "--headful" in sys.argv
    max_pages = 20
    if "--max-pages" in sys.argv:
        idx = sys.argv.index("--max-pages")
        if idx + 1 < len(sys.argv):
            max_pages = int(sys.argv[idx + 1])

    zipcodes = DFW_ZIPCODES
    if "--zipcodes" in sys.argv:
        idx = sys.argv.index("--zipcodes")
        if idx + 1 < len(sys.argv):
            zipcodes = sys.argv[idx + 1].split(",")

    print(f"Scraping {len(zipcodes)} DFW zipcodes (headless={not headful}, max_pages={max_pages})")
    print(f"Zipcodes: {', '.join(zipcodes)}")
    print(f"Will abort after {MAX_CONSECUTIVE_FAILURES} consecutive failures.\n")

    asyncio.run(scrape_all(zipcodes, headless=not headful, max_pages=max_pages))


if __name__ == "__main__":
    main()
