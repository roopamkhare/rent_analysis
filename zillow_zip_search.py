"""
Zillow zipcode search scraper – fetches ALL listed properties in a zip code
by parsing the embedded __NEXT_DATA__ JSON from search result pages.

Requires --headful mode to bypass PerimeterX.

Usage:
    python zillow_zip_search.py 75071 [--headful] [--max-pages 5]
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


# Fields to extract for each listing
LISTING_FIELDS = [
    "zpid", "streetAddress", "city", "state", "zipcode",
    "price", "zestimate", "rentZestimate", "taxAssessedValue",
    "bedrooms", "bathrooms", "livingArea", "lotAreaValue", "lotAreaUnits",
    "homeType", "homeStatus", "yearBuilt",
    "daysOnZillow", "timeOnZillow",
    "latitude", "longitude",
    "imgSrc", "detailUrl", "statusText",
    "brokerName", "mlsid",
    "propertyTaxRate", "monthlyHoaFee",
    "priceChange", "datePriceChanged",
    "isZillowOwned", "isFeatured", "isPreforeclosureAuction",
    "newConstructionType", "listingSubType",
    "country", "currency",
]


def _find_search_results(next_data: dict) -> dict | None:
    """Recursively search __NEXT_DATA__ for the search results cache."""
    if not isinstance(next_data, dict):
        return None

    # Zillow puts search results in queryState / cat1 / searchResults
    # or inside gdpClientCache / apiCache for search pages
    for key in ["cat1", "categoryTotals"]:
        if key in next_data:
            return next_data

    # Check for searchPageState in gdpClientCache-style blobs
    for k, v in next_data.items():
        if isinstance(v, str) and len(v) > 500:
            try:
                parsed = json.loads(v)
                if isinstance(parsed, dict):
                    r = _find_search_results(parsed)
                    if r:
                        return r
            except (json.JSONDecodeError, RecursionError):
                pass
        elif isinstance(v, dict):
            r = _find_search_results(v)
            if r:
                return r
    return None


def _extract_listings_from_search(next_data: dict) -> list[dict]:
    """Pull individual listing dicts from the __NEXT_DATA__ blob."""
    listings = []

    # Strategy 1: Walk into cat1.searchResults.listResults
    def _deep_find_key(obj, target_key, max_depth=10):
        if max_depth <= 0:
            return None
        if isinstance(obj, dict):
            if target_key in obj:
                return obj[target_key]
            for v in obj.values():
                r = _deep_find_key(v, target_key, max_depth - 1)
                if r is not None:
                    return r
        return None

    # Try to find listResults (main search results)
    list_results = _deep_find_key(next_data, "listResults")
    if isinstance(list_results, list) and list_results:
        print(f"  Found {len(list_results)} listings in listResults")
        listings.extend(list_results)

    # Also try mapResults (sometimes has more data per listing)
    map_results = _deep_find_key(next_data, "mapResults")
    if isinstance(map_results, list) and map_results:
        print(f"  Found {len(map_results)} listings in mapResults")
        # Merge map results — they often have zpid-keyed extra data
        existing_zpids = {l.get("zpid") for l in listings}
        for mr in map_results:
            if mr.get("zpid") not in existing_zpids:
                listings.append(mr)

    return listings


def normalize_listing(raw: dict) -> dict:
    """Flatten a raw Zillow listing into a clean dict."""
    out = {}
    for field in LISTING_FIELDS:
        val = raw.get(field)
        if val is not None:
            out[field] = val

    # Try nested address object
    addr = raw.get("address") or raw.get("addressWithZip") or ""
    if isinstance(addr, dict):
        for k in ["streetAddress", "city", "state", "zipcode"]:
            if k not in out and addr.get(k):
                out[k] = addr[k]
    elif isinstance(addr, str) and addr and "streetAddress" not in out:
        out["addressRaw"] = addr

    # hdpData often has deeper property info
    hdp = raw.get("hdpData", {}).get("homeInfo", {})
    if hdp:
        for field in LISTING_FIELDS:
            if field not in out and hdp.get(field) is not None:
                out[field] = hdp[field]

    # Ensure detailUrl is absolute
    if out.get("detailUrl") and not out["detailUrl"].startswith("http"):
        out["detailUrl"] = "https://www.zillow.com" + out["detailUrl"]

    # Price formatting
    if "price" in out and isinstance(out["price"], str):
        out["priceRaw"] = out["price"]
        cleaned = re.sub(r"[^\d.]", "", out["price"])
        if cleaned:
            try:
                out["price"] = int(float(cleaned))
            except ValueError:
                pass

    # units
    if "units" in raw:
        out["units"] = raw["units"]  # multi-family units list
    if "variableData" in raw:
        out["variableData"] = raw["variableData"]

    return out


def _get_total_pages(next_data: dict) -> int:
    """Try to find pagination info."""
    def _deep_find(obj, key, depth=8):
        if depth <= 0:
            return None
        if isinstance(obj, dict):
            if key in obj:
                return obj[key]
            for v in obj.values():
                r = _deep_find(v, key, depth - 1)
                if r is not None:
                    return r
        return None

    total_pages = _deep_find(next_data, "totalPages")
    if total_pages:
        return int(total_pages)

    total_count = _deep_find(next_data, "totalResultCount")
    if total_count:
        return max(1, (int(total_count) + 39) // 40)  # ~40 per page

    return 1


async def scrape_zipcode(
    zipcode: str,
    headless: bool = True,
    max_pages: int = 20,
):
    """Scrape all Zillow listings for a given zipcode."""
    all_listings = []
    seen_zpids = set()

    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=headless)
        ctx = await browser.new_context(
            viewport={"width": 1366, "height": 768},
        )
        page = await ctx.new_page()

        # Warm up — visit Zillow homepage first
        print("Warming up session …")
        try:
            await page.goto("https://www.zillow.com/", wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(random.randint(2000, 4000))
        except Exception:
            pass

        total_pages = None
        page_num = 1

        while page_num <= max_pages:
            if page_num == 1:
                url = f"https://www.zillow.com/homes/{zipcode}_rb/"
            else:
                url = f"https://www.zillow.com/homes/{zipcode}_rb/{page_num}_p/"

            print(f"\n── Page {page_num} ──  {url}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            except Exception as e:
                print(f"  Navigation error: {e}")
                break

            await page.wait_for_timeout(random.randint(3000, 6000))

            title = await page.title()
            print(f"  Title: {title}")

            if "denied" in title.lower() or "captcha" in title.lower():
                print("  ❌ Blocked by PerimeterX!")
                if page_num == 1:
                    print("  Try --headful mode or wait and retry.")
                break

            html = await page.content()
            print(f"  HTML: {len(html):,} chars")

            # Save page HTML for debugging
            Path(f"zillow_search_p{page_num}.html").write_text(html, encoding="utf-8")

            # Extract __NEXT_DATA__
            m = re.search(
                r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>',
                html, re.DOTALL,
            )
            if not m:
                print("  ✗ No __NEXT_DATA__ found")
                break

            next_data = json.loads(m.group(1))
            print(f"  ✓ __NEXT_DATA__ ({len(m.group(1)):,} chars)")

            # Get total pages on first run
            if total_pages is None:
                total_pages = _get_total_pages(next_data)
                print(f"  Total pages estimated: {total_pages}")
                max_pages = min(max_pages, total_pages)

            # Extract listings
            raw_listings = _extract_listings_from_search(next_data)
            if not raw_listings:
                print("  ✗ No listings found on this page")
                break

            new_count = 0
            for raw in raw_listings:
                cleaned = normalize_listing(raw)
                zpid = cleaned.get("zpid")
                if zpid and zpid not in seen_zpids:
                    seen_zpids.add(zpid)
                    all_listings.append(cleaned)
                    new_count += 1

            print(f"  ✓ {new_count} new listings (total so far: {len(all_listings)})")

            if new_count == 0:
                print("  No new listings — stopping pagination.")
                break

            page_num += 1

            # Random delay between pages
            if page_num <= max_pages:
                delay = random.uniform(3.0, 7.0)
                print(f"  Waiting {delay:.1f}s before next page …")
                await page.wait_for_timeout(int(delay * 1000))

        await ctx.close()

    # ── Save results ──────────────────────────────────────────────────
    output = {
        "zipcode": zipcode,
        "total_listings": len(all_listings),
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "listings": all_listings,
    }

    Path("json").mkdir(exist_ok=True)
    out_file = Path(f"json/zillow_{zipcode}_listings.json")
    out_file.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"\n{'='*60}")
    print(f"Saved {len(all_listings)} listings → {out_file}")

    # Summary
    if all_listings:
        prices = [l["price"] for l in all_listings if isinstance(l.get("price"), (int, float))]
        print(f"\nSummary for {zipcode}:")
        print(f"  Listings: {len(all_listings)}")
        if prices:
            print(f"  Price range: ${min(prices):,.0f} – ${max(prices):,.0f}")
            print(f"  Median price: ${sorted(prices)[len(prices)//2]:,.0f}")

        home_types = {}
        for l in all_listings:
            ht = l.get("homeType", "Unknown")
            home_types[ht] = home_types.get(ht, 0) + 1
        print(f"  Home types: {home_types}")

        statuses = {}
        for l in all_listings:
            s = l.get("homeStatus") or l.get("statusText") or "Unknown"
            statuses[s] = statuses.get(s, 0) + 1
        print(f"  Statuses: {statuses}")

    return output


def main():
    if len(sys.argv) < 2:
        print("Usage: python zillow_zip_search.py <zipcode> [--headful] [--max-pages N]")
        sys.exit(1)

    zipcode = sys.argv[1]
    headful = "--headful" in sys.argv
    max_pages = 20
    if "--max-pages" in sys.argv:
        idx = sys.argv.index("--max-pages")
        if idx + 1 < len(sys.argv):
            max_pages = int(sys.argv[idx + 1])

    asyncio.run(scrape_zipcode(zipcode, headless=not headful, max_pages=max_pages))


if __name__ == "__main__":
    main()
