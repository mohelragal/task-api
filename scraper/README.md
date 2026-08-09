# The Polite Scraper

A Python pipeline that collects the first three catalogue pages from Books to Scrape and produces validated JSON records.

## Target classification

- Target: `https://books.toscrape.com`, a public sandbox created for scraping practice.
- Scope: exactly the first three catalogue pages and their 60 book detail pages.
- Data: title, URL, price, availability, rating, description, source page, and fetch time.
- Robots result: `https://books.toscrape.com/robots.txt` returned 404, so no robots file was found. This is not treated as permission; the site's stated sandbox purpose is the basis for this limited exercise.
- This use is appropriate because the target explicitly exists for scraping practice and the collection is small, cached, delayed, and non-sensitive.

I will not reuse this code on another site without checking its rules and terms first.

## Pipeline

The crawler starts at `catalogue/page-1.html`, follows the catalogue's own next links, and stops after page 3. It converts every relative link with `urljoin`, removes duplicate canonical URLs, and then visits the 60 discovered detail pages.

Each real request identifies this project in its user-agent, times out after 10 seconds, checks for HTTP 200, and waits at least 500 ms after the previous request. A timeout or 5xx response is retried once. A 403 or 404 is immediately logged and skipped. Cached pages never create network traffic or delays.

## Run in under five minutes

```bash
cd scraper
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python src/main.py --include-broken
pytest -q
```

On macOS or Linux, activate with `source .venv/bin/activate`. Remove `--include-broken` for a clean 60-page run. Add `--refresh` only when a fresh network collection is genuinely needed.

## Outputs

- `output/books.json`: exactly 60 unique, validated books.
- `output/errors.json`: records rejected by schema validation and their reasons.
- `output/run-report.json`: timing, fetch, cache, validation, and failure counts.

The cache is deliberately excluded from GitHub. One sample set of validated outputs is committed as evidence.

## Record schema

| Field | Type | Rule |
| --- | --- | --- |
| `title` | string | Required and non-empty |
| `product_url` | HTTPS URL | Canonical identity |
| `price_text` | string | Original scraped value |
| `price_gbp` | number | Normalized GBP value |
| `availability_text` | string | Original scraped value |
| `rating_text` | string | Original one-to-five word |
| `rating` | integer | Between 1 and 5 |
| `description` | string or null | Never invented when absent |
| `source_page` | HTTPS URL | Catalogue provenance |
| `fetched_at` | ISO timestamp | Fetch provenance |

Pydantic validates every normalized record before it reaches `books.json`. Invalid records are written to `errors.json`. Records are keyed by canonical product URL, so a rerun updates the same 60 identities instead of appending duplicates.

## Verified run report

```json
{
  "duration_seconds": 3.094,
  "catalogue_pages": 3,
  "detail_pages": 61,
  "pages_fetched": 0,
  "cache_hits": 63,
  "valid_records": 60,
  "invalid_records": 0,
  "failed_pages": 1
}
```

The deliberate 404 was logged and skipped while all 60 valid records survived. The cached rerun demonstrates idempotency and creates no repeat load on the target.

## Why no browser was needed

All required catalogue and product data already exists in the HTML returned by the server. A browser would add startup time and memory cost without revealing any additional data for this assignment.

## Ethics

Prefer an official API when one exists. Never bypass logins, paywalls, access controls, or blocks. Check a site's rules and terms before collecting, identify the client honestly, request slowly, cache aggressively, and collect only the minimum data needed.

## Honest limitation

The selectors are designed for the current Books to Scrape product markup. A major redesign could require selector updates, which the fixture tests help detect but cannot automatically repair.
