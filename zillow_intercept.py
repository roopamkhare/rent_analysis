import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright
from playwright_stealth import Stealth


async def intercept_zillow(url: str, headless: bool = True, timeout_ms: int = 10000):
    captured = []   # list of {url, status, content_type, body}

    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        async def on_response(response):
            resp_url = response.url
            content_type = response.headers.get('content-type', '')

            # Log every response
            print(f"[{response.status}] {resp_url[:120]}")

            # Save JSON responses
            if 'json' in content_type or 'async-create-search' in resp_url or 'search-page-state' in resp_url:
                try:
                    body = await response.json()
                    captured.append({
                        'url': resp_url,
                        'status': response.status,
                        'content_type': content_type,
                        'body': body,
                    })
                    print(f"  >>> CAPTURED JSON from {resp_url[:100]}")
                except Exception:
                    pass

        page.on('response', on_response)

        print(f"Navigating to {url} ...")
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        except Exception as e:
            print(f"goto error: {e}")

        # Wait extra time for async requests
        await page.wait_for_timeout(timeout_ms)

        # Also grab the page HTML title to check if we got the real page
        title = await page.title()
        print(f"Page title: {title}")

        out_dir = Path('json')
        out_dir.mkdir(exist_ok=True)
        out_file = out_dir / 'zillow_intercepted.json'
        out_file.write_text(json.dumps(captured, indent=2, default=str))
        print(f"\nSaved {len(captured)} JSON responses to {out_file}")

        await browser.close()


def main():
    if len(sys.argv) < 2:
        print('Usage: python zillow_intercept.py <url> [--headful]')
        sys.exit(1)
    url = sys.argv[1]
    headful = '--headful' in sys.argv
    asyncio.run(intercept_zillow(url, headless=not headful))


if __name__ == '__main__':
    main()
