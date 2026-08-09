import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, HttpUrl, ValidationError, field_validator


BASE_URL = "https://books.toscrape.com/"
START_URL = urljoin(BASE_URL, "catalogue/page-1.html")
BROKEN_URL = urljoin(BASE_URL, "catalogue/this-book-does-not-exist/index.html")
USER_AGENT = "FlyRankInternship-A9/1.0 (+https://github.com/mohelragal/task-api)"
RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


class BookRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    product_url: HttpUrl
    price_text: str
    price_gbp: float
    availability_text: str
    rating_text: str
    rating: int
    description: str | None
    source_page: HttpUrl
    fetched_at: datetime

    @field_validator("title", "price_text", "availability_text", "rating_text")
    @classmethod
    def require_text(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("field must not be empty")
        return value

    @field_validator("rating")
    @classmethod
    def check_rating(cls, value: int) -> int:
        if value not in range(1, 6):
            raise ValueError("rating must be between 1 and 5")
        return value


class FetchError(Exception):
    def __init__(self, url: str, message: str, status: int | None = None):
        super().__init__(message)
        self.url = url
        self.status = status


class PoliteClient:
    def __init__(self, cache_dir: Path, delay: float = 0.5, timeout: float = 10.0):
        self.cache_dir = cache_dir
        self.delay = max(delay, 0.5)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.last_request = 0.0
        self.pages_fetched = 0
        self.cache_hits = 0
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def cache_path(self, url: str) -> Path:
        if url == START_URL:
            return self.cache_dir / "catalogue-page-1.html"
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
        return self.cache_dir / f"{digest}.html"

    def fetch(self, url: str, refresh: bool = False) -> tuple[str, str]:
        path = self.cache_path(url)
        if path.exists() and not refresh:
            text = path.read_text(encoding="utf-8")
            self.cache_hits += 1
            print(f"CACHE HIT bytes={len(text.encode('utf-8'))} url={url}")
            return text, path.stat().st_mtime_ns and iso_now(path.stat().st_mtime)

        for attempt in range(1, 3):
            elapsed = time.monotonic() - self.last_request
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
            try:
                response = self.session.get(url, timeout=self.timeout)
                self.last_request = time.monotonic()
            except requests.Timeout as exc:
                self.last_request = time.monotonic()
                if attempt == 1:
                    time.sleep(1)
                    continue
                raise FetchError(url, "request timed out") from exc
            except requests.RequestException as exc:
                raise FetchError(url, str(exc)) from exc

            if response.status_code == 200:
                path.write_bytes(response.content)
                self.pages_fetched += 1
                print(f"FETCH status=200 bytes={len(response.content)} url={url}")
                return response.text, iso_now()
            if response.status_code >= 500 and attempt == 1:
                time.sleep(1)
                continue
            raise FetchError(url, f"HTTP {response.status_code}", response.status_code)

        raise FetchError(url, "request failed")


def iso_now(timestamp: float | None = None) -> str:
    value = datetime.fromtimestamp(timestamp, timezone.utc) if timestamp else datetime.now(timezone.utc)
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_price(price_text: str) -> float:
    match = re.fullmatch(r"[^\d\s](\d+(?:\.\d{2})?)", price_text.strip())
    if not match:
        raise ValueError(f"invalid GBP price: {price_text}")
    return float(match.group(1))


def absolute_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href)


def discover_books(client: PoliteClient, refresh: bool = False) -> tuple[list[tuple[str, str]], int]:
    page_url = START_URL
    discovered: list[tuple[str, str]] = []
    pages = 0
    while page_url and pages < 3:
        html, _ = client.fetch(page_url, refresh)
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("article.product_pod h3 a[href]"):
            discovered.append((absolute_url(page_url, link["href"]), page_url))
        pages += 1
        next_link = soup.select_one("li.next a[href]")
        page_url = absolute_url(page_url, next_link["href"]) if next_link and pages < 3 else ""

    unique = list(dict.fromkeys(discovered))
    print(f"catalogue_pages={pages} discovered={len(discovered)} unique_urls={len(unique)}")
    return unique, pages


def extract_raw(html: str, product_url: str, source_page: str, fetched_at: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    product = soup.select_one("div.product_main")
    if product is None:
        raise ValueError("product area not found")
    title = product.select_one("h1")
    price = product.select_one("p.price_color")
    availability = product.select_one("p.availability")
    rating = product.select_one("p.star-rating")
    description_heading = soup.find(id="product_description")
    description_node = description_heading.find_next_sibling("p") if description_heading else None
    if not all((title, price, availability, rating)):
        raise ValueError("required product field missing")
    rating_text = next((name for name in RATING_WORDS if name in rating.get("class", [])), "")
    return {
        "title": title.get_text(" ", strip=True),
        "product_url": product_url,
        "price_text": price.get_text(" ", strip=True),
        "availability_text": availability.get_text(" ", strip=True),
        "rating_text": rating_text,
        "description": description_node.get_text(" ", strip=True) if description_node else None,
        "source_page": source_page,
        "fetched_at": fetched_at,
    }


def validate_record(raw: dict[str, Any]) -> BookRecord:
    return BookRecord.model_validate(
        {
            **raw,
            "price_gbp": normalize_price(raw["price_text"]),
            "rating": RATING_WORDS.get(raw["rating_text"], 0),
        }
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def run(root: Path, refresh: bool = False, include_broken: bool = False, delay: float = 0.5) -> dict[str, Any]:
    started = time.monotonic()
    started_at = iso_now()
    output_dir = root / "output"
    client = PoliteClient(root / "cache", delay=delay)
    records: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    failed_pages: list[dict[str, Any]] = []
    links, catalogue_pages = discover_books(client, refresh)
    if include_broken:
        links.append((BROKEN_URL, START_URL))

    first_raw: dict[str, Any] | None = None
    for product_url, source_page in links:
        try:
            html, fetched_at = client.fetch(product_url, refresh)
            raw = extract_raw(html, product_url, source_page, fetched_at)
            first_raw = first_raw or raw
            record = validate_record(raw)
            data = record.model_dump(mode="json")
            records[str(record.product_url)] = data
        except FetchError as exc:
            failed_pages.append({"url": exc.url, "status": exc.status, "reason": str(exc)})
            print(f"SKIP url={exc.url} reason={exc}")
        except (ValidationError, ValueError) as exc:
            errors.append({"url": product_url, "reason": str(exc)})
            print(f"INVALID url={product_url} reason={exc}")

    books = sorted(records.values(), key=lambda item: item["product_url"])
    write_json(output_dir / "books.json", books)
    write_json(output_dir / "errors.json", errors)
    report = {
        "started_at": started_at,
        "duration_seconds": round(time.monotonic() - started, 3),
        "catalogue_pages": catalogue_pages,
        "detail_pages": len(links),
        "pages_fetched": client.pages_fetched,
        "cache_hits": client.cache_hits,
        "valid_records": len(books),
        "invalid_records": len(errors),
        "failed_pages": len(failed_pages),
        "failures": failed_pages,
    }
    write_json(output_dir / "run-report.json", report)
    if first_raw:
        print(json.dumps(first_raw, ensure_ascii=False, indent=2))
    print(f"detail_pages={len(links)} valid_records={len(books)} failed_pages={len(failed_pages)}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect three Books to Scrape catalogue pages politely")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--include-broken", action="store_true")
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    run(root, refresh=args.refresh, include_broken=args.include_broken, delay=args.delay)
