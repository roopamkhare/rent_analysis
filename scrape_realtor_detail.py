import asyncio
import json
from pathlib import Path
import sys

from playwright.async_api import async_playwright
from playwright_stealth import Stealth


async def scrape_detail(url: str, headful: bool = False, profile_dir: str | None = None):
    out_html = Path('realtor_detail.html')
    Path("json").mkdir(exist_ok=True)
    out_json = Path('json/realtor_detail.json')

    profile_dir = profile_dir or '.profiles/realtor'
    Path(profile_dir).mkdir(parents=True, exist_ok=True)

    # Use Stealth().use_async to instrument contexts so stealth is applied automatically
    async with Stealth().use_async(async_playwright()) as p:
        if headful:
            # launch persistent context to reuse a real profile
            context = await p.chromium.launch_persistent_context(profile_dir, headless=False)
            page = context.pages[0] if context.pages else await context.new_page()
        else:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

        print(f"Navigating to {url}...")
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        except Exception as e:
            print('goto error:', e)
        await page.wait_for_timeout(3000)

        html = await page.content()
        out_html.write_text(html, encoding='utf-8')

        js = r"""
        () => {
            const get = s => document.querySelector(s)?.innerText || '';
            const data = {};
            data.price = get('[data-testid="ldp-price"]') || get('.ldp__price') || get('.price') || '';
            data.address = get('[data-testid="ldp-address"]') || get('.ldp__address') || get('[itemprop="streetAddress"]') || '';
            data.beds = get('[data-label="property-meta-beds"]') || '';
            data.baths = get('[data-label="property-meta-baths"]') || '';
            data.sqft = get('[data-label="property-meta-sqft"]') || '';
            data.title = document.title || '';
            return data;
        }
        """

        try:
            data = await page.evaluate(js)
        except Exception as e:
            print('evaluate error:', e)
            data = {}

        out_json.write_text(json.dumps(data, indent=2), encoding='utf-8')
        print('Saved', out_html, 'and', out_json)

        # close depending on mode
        try:
            await context.close()
        except Exception:
            pass


def main():
    if len(sys.argv) < 2:
        print('Usage: python scrape_realtor_detail.py <url>')
        return
    url = sys.argv[1]
    asyncio.run(scrape_detail(url))


if __name__ == '__main__':
    main()
