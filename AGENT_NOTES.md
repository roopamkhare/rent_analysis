**Project Overview**

- Purpose: address-based property data collection, scraping, and enrichment for rent/analysis workflows.
- Repo root scripts are small scrapers, lookup utilities, and helpers that gather property details from Zillow, Realtor, Redfin, HUD datasets, MLS and public APIs.

**Environment**

- Python: 3.14 (project uses a `.venv/` virtual environment). See `requirements.txt` for dependencies.
- Playwright is used for browser automation; stealth helpers from `playwright-stealth` are used to reduce bot detection.
- Large data outputs live under the `json/` directory; HUD spreadsheets are stored in `hud_data/`.

**High-level file map (what each script does)**

- `zillow_zip_search.py` — Scrapes Zillow search pages for a zipcode by parsing `__NEXT_DATA__` embedded JSON on each search result page. Outputs `json/zillow_<zip>_listings.json`. Use `--headful` if blocked.
- `zillow_detail.py` — Loads a Zillow detail page (headful recommended) and extracts property data from `__NEXT_DATA__` → `gdpClientCache` → `property`. Outputs `json/zillow_detail_data.json` or use `--from-html` to parse saved HTML.
- `zillow_intercept.py` — Intercepts network responses on a Zillow page and saves JSON responses to `json/zillow_intercepted.json` (useful to inspect GraphQL/XHR payloads).
- `zillow_zip_search.py` (same as above) — paginates search results and normalizes listing objects.
- `scraper.py` — earlier address-based Zillow search that intercepts background JSON; writes `json/zillow_<slug>.json` and `json/zillow_<slug>_all.json`.
- `realtor_scraper.py`, `redfin_scraper.py`, `mls_search.py` — site-specific search scrapers for Realtor, Redfin, and MLS (foreclosure) respectively. They save results under `json/` after updates.
- `scrape_realtor_detail.py` — extracts detail-level fields and saves `json/realtor_detail.json`.
- `hud_lookup.py` — downloads HUD inspection spreadsheets to `hud_data/` and searches them for address matches; outputs `json/hud_lookup_<query>.json`.
- `all_lookups.py` — orchestrates multiple public APIs (Census geocoder, FCC, ACS, HUD) and emits `json/lookups_output.json`.
- `hello.py`, utility or scratch files — miscellaneous small helpers.

**Data layout & outputs**

- `json/` — canonical location for all JSON outputs (search results, detail outputs, intercept dumps, lookups).
- `hud_data/` — large HUD Excel files (not all files are necessary in repository; consider storing externally if large).

**Important runtime notes / caveats**

- PerimeterX (and other bot-detection services) block headless browser traffic. When you see "Access to this page has been denied" or 403 GraphQL responses, retry in `--headful` mode or use an interactive persistent context.
- Many Zillow site API calls are GraphQL and may return 403 when automated. The code base extracts property data from server-rendered `__NEXT_DATA__` which is more reliable.
- Repeated runs from the same IP can cause throttling; add pauses or use a different IP if you need many runs.

**How to run (examples)**

1) Scrape all listings in a zipcode (headful recommended):

```bash
.venv/bin/python zillow_zip_search.py 75071 --headful --max-pages 20
```

2) Parse an existing saved HTML produced by `zillow_detail.py` (useful to avoid reloading pages):

```bash
.venv/bin/python zillow_detail.py --from-html zillow_page.html
```

3) Intercept JSON responses from a detail page (inspect ad/GraphQL payloads):

```bash
.venv/bin/python zillow_intercept.py "<zillow_detail_url>" --headful
```

4) HUD lookup for an address:

```bash
.venv/bin/python hud_lookup.py "613 kappa way, mckinney, tx, 75071"
```

**Agent guidance (what an automated agent should know)**

- Prefer reading from `json/` for downstream processing — all scripts were updated to write outputs there.
- If a script fails due to blocking, try running the same command with `--headful` or using `--from-html` if a saved HTML is available.
- For large-scale scraping, implement rate limiting and rotating IPs; the code includes random delays between pages.
- When parsing Zillow, prefer `__NEXT_DATA__` → `gdpClientCache` → `property` or the `listResults` entries for search pages.
- The `zpid` field is the canonical unique identifier used across Zillow-listed objects.

**Developer notes & next improvements**

- Consider moving large HUD Excel files out of the repository and into an object store; store only references.
- Add a `config.py` for centralizing output paths (currently many scripts call `Path('json')` directly).
- Add small unit tests for the JSON parsing helpers (`_find_gdp_cache`, `_extract_property`, `_extract_listings_from_search`).
- Add a `README.md` section that documents `--headful` requirement and a checklist for debugging bot-blocking.

**Contacts / metadata**

- Repo user: `roopamkhare` (commits pushed to `origin/main`).
- Useful files: `requirements.txt` (dependencies), `.venv/` (local environment), `json/` (outputs), `hud_data/` (HUD XLSX)

---
Generated: 2026-02-14
