import argparse
import asyncio
import json
from urllib.parse import quote_plus

from playwright.async_api import async_playwright
from playwright_stealth import Stealth


async def scrape_address(address: str, headless: bool = True, timeout_ms: int = 5000):
    """Search Zillow for the given address and save matching listings to a JSON file.

    The function navigates to a Zillow search URL for the address, listens
    for the internal JSON responses, and filters listings whose `address`
    contains the input address (case-insensitive).
    """

    slug = quote_plus(address)
    search_url = f"https://www.zillow.com/homes/{slug}_rb/"
    output_file = f"zillow_{slug}.json"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/119.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)

        matched = []

        async def handle_response(response):
            try:
                if "search-page-state" in response.url:
                    data = await response.json()
                    results = (
                        data.get("cat1", {})
                        .get("searchResults", {})
                        .get("listResults", [])
                    )
                    for house in results:
                        addr = (house.get("address") or "").lower()
                        if address.lower() in addr:
                            matched.append(
                                {
                                    "address": house.get("address"),
                                    "price": house.get("price"),
                                    "rent": house.get("hdpData", {})
                                    .get("homeInfo", {})
                                    .get("rentZestimate"),
                                    "lat": house.get("latLong", {}).get("latitude"),
                                    "lng": house.get("latLong", {}).get("longitude"),
                                    "zpid": house.get("zpid"),
                                    "detailUrl": house.get("detailUrl"),
                                }
                            )
            except Exception:
                return

        page.on("response", handle_response)

        print(f"Navigating to {search_url}...")
        await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(timeout_ms)

        with open(output_file, "w") as f:
            json.dump(matched, f, indent=2)

        print(f"Saved {len(matched)} matching listings to {output_file}")
        await browser.close()


def main():
    parser = argparse.ArgumentParser(description="Scrape Zillow by address")
    parser.add_argument("address", help="Street address or query to search for", nargs="+")
    parser.add_argument("--headless", action="store_true", help="Run browser headless (default: True)")
    parser.add_argument("--timeout", type=int, default=5000, help="Additional wait time (ms) after navigation")
    args = parser.parse_args()
    address = " ".join(args.address)

    asyncio.run(scrape_address(address, headless=True, timeout_ms=args.timeout))


if __name__ == "__main__":
    main()
