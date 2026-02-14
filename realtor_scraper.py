import argparse
import asyncio
import json
from urllib.parse import quote_plus
from pathlib import Path

from playwright.async_api import async_playwright
from playwright_stealth import Stealth


async def scrape_realtor(address: str, headless: bool = True, timeout_ms: int = 5000):
    slug = quote_plus(address)
    url = f"https://www.realtor.com/realestateandhomes-search/{slug}"
    Path("json").mkdir(exist_ok=True)
    out_file = Path("json") / f"realtor_{slug}.json"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)

        print(f"Navigating to {url}...")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(timeout_ms)

        # Try to extract listing links and simple metadata from the rendered page
        listings = await page.evaluate("""
        () => {
            const anchors = Array.from(document.querySelectorAll('a[href*="/realestateandhomes-detail/"]'));
            const seen = new Set();
            const out = [];
            for (const a of anchors) {
                const href = a.href;
                if (seen.has(href)) continue;
                seen.add(href);
                const card = a.closest('li') || a.closest('div');
                const price = card?.querySelector('[data-label="pc-price"]')?.innerText || card?.querySelector('.price')?.innerText || '';
                const addr = card?.querySelector('[data-label="pc-address"]')?.innerText || a.innerText || '';
                out.push({address: addr, price: price, url: href});
            }
            return out;
        }
        """)

        with open(out_file, "w") as f:
            json.dump(listings, f, indent=2)

        print(f"Saved {len(listings)} listings to {out_file}")
        await browser.close()


def main():
    parser = argparse.ArgumentParser(description="Scrape Realtor.com search results for an address or zip")
    parser.add_argument('address', nargs='+')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--timeout', type=int, default=5000)
    args = parser.parse_args()
    address = ' '.join(args.address)
    asyncio.run(scrape_realtor(address, headless=True, timeout_ms=args.timeout))


if __name__ == '__main__':
    main()
