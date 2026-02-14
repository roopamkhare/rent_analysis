"""
Zillow detail-page scraper – extracts property data from the embedded
__NEXT_DATA__ JSON in server-rendered HTML.  Headful mode is required
to bypass PerimeterX.

Usage:
    python zillow_detail.py <zillow_detail_url> [--headful]

Example:
    python zillow_detail.py \
      "https://www.zillow.com/homedetails/304-Sparrow-Hawk-McKinney-TX-75072/53109906_zpid/" \
      --headful
"""

import asyncio
import json
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright
from playwright_stealth import Stealth


# ── helpers ───────────────────────────────────────────────────────────

def _find_gdp_cache(next_data: dict) -> dict | None:
    """Recursively search __NEXT_DATA__ for the gdpClientCache dict."""
    if not isinstance(next_data, dict):
        return None
    if "gdpClientCache" in next_data:
        raw = next_data["gdpClientCache"]
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None
        return raw
    for v in next_data.values():
        if isinstance(v, dict):
            found = _find_gdp_cache(v)
            if found:
                return found
    return None


def _extract_property(gdp_cache: dict) -> dict | None:
    """Pull a 'property' blob from any value inside gdpClientCache."""
    for key, val in gdp_cache.items():
        if isinstance(val, str):
            try:
                val = json.loads(val)
            except Exception:
                continue
        if isinstance(val, dict) and "property" in val:
            return val["property"]
    return None


DISPLAY_FIELDS = [
    "zpid", "streetAddress", "city", "state", "zipcode",
    "bedrooms", "bathrooms", "livingArea", "livingAreaValue",
    "lotSize", "lotAreaValue", "lotAreaUnits",
    "price", "zestimate", "rentZestimate",
    "homeType", "homeStatus", "yearBuilt",
    "propertyTaxRate", "monthlyHoaFee",
    "latitude", "longitude",
    "mlsid", "daysOnZillow", "timeOnZillow",
    "pageViewCount", "favoriteCount",
    "description",
]


# ── main scraping routine ────────────────────────────────────────────

async def scrape_zillow_detail(url: str, headless: bool = True):
    """Navigate to a Zillow detail page and extract property data."""
    import tempfile, random

    async with Stealth().use_async(async_playwright()) as p:
        # Use a fresh temp profile each run to avoid cookie/fingerprint taint
        user_data_dir = tempfile.mkdtemp(prefix="zillow_")
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=headless,
            viewport={"width": 1366, "height": 768},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        # Visit Zillow homepage first to build up cookies
        print("Warming up session …")
        try:
            await page.goto("https://www.zillow.com/", wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(random.randint(2000, 4000))
        except Exception:
            pass

        print(f"Navigating to {url} …")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        except Exception as e:
            print(f"Navigation error: {e}")

        # Human-like wait
        await page.wait_for_timeout(random.randint(4000, 7000))

        title = await page.title()
        print(f"Page title: {title}")
        if "denied" in title.lower() or "captcha" in title.lower():
            print("❌  Blocked by PerimeterX — try again later or with --headful")
            await ctx.close()
            return

        html = await page.content()
        Path("zillow_page.html").write_text(html, encoding="utf-8")
        print(f"Saved full HTML ({len(html):,} chars) → zillow_page.html")
        await ctx.close()

    # Delegate parsing to the shared function
    parse_zillow_html(html, url)


def parse_zillow_html(html: str, url: str = ""):
    """Parse property data from Zillow HTML (no browser needed)."""
    m = re.search(
        r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not m:
        print("✗ Could not find __NEXT_DATA__ in the HTML.")
        return None

    next_data = json.loads(m.group(1))
    print(f"  ✓ __NEXT_DATA__ ({len(m.group(1)):,} chars)")

    gdp_cache = _find_gdp_cache(next_data) or {}
    prop = _extract_property(gdp_cache)

    if prop is None:
        def _deep_find(obj, key):
            if isinstance(obj, dict):
                if key in obj and isinstance(obj[key], dict):
                    return obj[key]
                for v in obj.values():
                    r = _deep_find(v, key)
                    if r:
                        return r
            if isinstance(obj, list):
                for item in obj:
                    r = _deep_find(item, key)
                    if r:
                        return r
            return None
        prop = _deep_find(next_data, "property")

    if prop:
        print("\n── Property Details ─────────────────────────")
        for field in DISPLAY_FIELDS:
            val = prop.get(field)
            if val is not None:
                if field == "description" and len(str(val)) > 120:
                    val = str(val)[:120] + "…"
                print(f"  {field:20s}: {val}")

        addr = prop.get("address", {})
        if addr:
            print(f"\n  Full address: {addr.get('streetAddress')}, "
                  f"{addr.get('city')}, {addr.get('state')} {addr.get('zipcode')}")

        attr = prop.get("attributionInfo", {})
        if attr:
            print(f"  Agent: {attr.get('agentName')}  |  Broker: {attr.get('brokerName')}")
            print(f"  MLS: {attr.get('mlsName')} ({attr.get('mlsId')})")

    result = {"url": url, "property": prop}
    Path("json").mkdir(exist_ok=True)
    out = Path("json") / "zillow_detail_data.json"
    out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved → {out}")
    return prop


def main():
    if len(sys.argv) < 2:
        print("Usage: python zillow_detail.py <url> [--headful] [--from-html FILE]")
        sys.exit(1)

    # --from-html mode: parse a previously-saved HTML file
    if "--from-html" in sys.argv:
        idx = sys.argv.index("--from-html")
        html_path = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "zillow_page.html"
        html = Path(html_path).read_text(encoding="utf-8")
        print(f"Parsing {html_path} ({len(html):,} chars) …")
        parse_zillow_html(html, url=sys.argv[1] if sys.argv[1] != "--from-html" else "")
        return

    url = sys.argv[1]
    headful = "--headful" in sys.argv
    asyncio.run(scrape_zillow_detail(url, headless=not headful))


if __name__ == "__main__":
    main()
