import argparse
import asyncio
import json
from urllib.parse import quote_plus

from playwright.async_api import async_playwright
from playwright_stealth import Stealth


async def scrape_redfin(query: str, headless: bool = True, timeout_ms: int = 5000):
    slug = quote_plus(query)
    url = f"https://www.redfin.com/search?q={slug}"
    out_file = f"redfin_{slug}.json"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)

        print(f"Navigating to {url}...")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(timeout_ms)

        listings = await page.evaluate(r"""
        () => {
            const anchors = Array.from(document.querySelectorAll('a'))
                .filter(a => (a.href || '').includes('/home/') || (a.href || '').includes('/property/'));
            import argparse
            import asyncio
            import json
            from urllib.parse import quote_plus
            from pathlib import Path
                if (!href || seen.has(href)) continue;
                seen.add(href);
                const card = a.closest('div') || a.closest('li') || a;
                const text = card?.innerText || a.innerText || '';
                const priceMatch = text.match(/\$[0-9,]+/);
                const price = priceMatch ? priceMatch[0] : '';
                const addr = text.split('\n')[0] || '';
                Path("json").mkdir(exist_ok=True)
                out_file = Path("json") / f"redfin_{slug}.json"
            }
            return out;
        }
        """)

        with open(out_file, 'w') as f:
            json.dump(listings, f, indent=2)

        print(f"Saved {len(listings)} listings to {out_file}")
        await browser.close()


def main():
    parser = argparse.ArgumentParser(description='Scrape Redfin search results')
    parser.add_argument('query', nargs='+')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--timeout', type=int, default=5000)
    args = parser.parse_args()
    query = ' '.join(args.query)
    asyncio.run(scrape_redfin(query, headless=True, timeout_ms=args.timeout))


if __name__ == '__main__':
    main()
