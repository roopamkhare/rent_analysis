import argparse
import asyncio
import json
from urllib.parse import quote_plus

from playwright.async_api import async_playwright
from playwright_stealth import Stealth


async def search_mls(query: str, headless: bool = True, timeout_ms: int = 5000):
    slug = quote_plus(query)
    url = f"https://mls.foreclosure.com/listing/search?q={slug}"
    out_file = f"mls_search_{slug}.json"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)

        print(f"Navigating to {url}...")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(timeout_ms)

        # Collect anchors that look like listing links and some surrounding text
        listings = await page.evaluate(r"""
        () => {
            const anchors = Array.from(document.querySelectorAll('a'));
            const out = [];
            const seen = new Set();
            for (const a of anchors) {
                const href = a.href || '';
                if (!href) continue;
                if (href.includes('/address/') || href.includes('/listing/') || href.includes('listingid') || href.includes('/listings/')) {
                    if (seen.has(href)) continue;
                    seen.add(href);
                    // try to find nearby price/address text
                    const card = a.closest('li') || a.closest('div') || a;
                    const text = card?.innerText || a.innerText || '';
                    out.push({url: href, text: text.slice(0, 300)});
                }
            }
            return out;
        }
        """)

        with open(out_file, 'w') as f:
            json.dump(listings, f, indent=2)

        print(f"Saved {len(listings)} results to {out_file}")
        await browser.close()


def main():
    parser = argparse.ArgumentParser(description='Search MLS.foreclosure.com')
    parser.add_argument('query', nargs='+')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--timeout', type=int, default=5000)
    args = parser.parse_args()
    query = ' '.join(args.query)
    asyncio.run(search_mls(query, headless=True, timeout_ms=args.timeout))


if __name__ == '__main__':
    main()
