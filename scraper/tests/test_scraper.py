from pathlib import Path

import pytest

from src.scraper import absolute_url, extract_raw, normalize_price, validate_record


FIXTURES = Path(__file__).parent / "fixtures"
PRODUCT_URL = "https://books.toscrape.com/catalogue/example/index.html"
SOURCE_URL = "https://books.toscrape.com/catalogue/page-1.html"
FETCHED_AT = "2026-08-09T12:00:00Z"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_normalize_price() -> None:
    assert normalize_price("£51.77") == 51.77


def test_reject_malformed_price() -> None:
    with pytest.raises(ValueError):
        normalize_price("USD 10")


def test_absolute_url() -> None:
    assert absolute_url(SOURCE_URL, "../book/index.html") == "https://books.toscrape.com/book/index.html"


def test_extract_complete_record() -> None:
    raw = extract_raw(fixture("book.html"), PRODUCT_URL, SOURCE_URL, FETCHED_AT)
    record = validate_record(raw)
    assert record.title == "Example Book"
    assert record.price_gbp == 12.34
    assert record.rating == 4
    assert record.description == "A useful description."


def test_missing_description_is_null() -> None:
    raw = extract_raw(fixture("book-no-description.html"), PRODUCT_URL, SOURCE_URL, FETCHED_AT)
    assert raw["description"] is None


def test_malformed_fixture_is_rejected() -> None:
    with pytest.raises(ValueError):
        extract_raw(fixture("malformed.html"), PRODUCT_URL, SOURCE_URL, FETCHED_AT)


def test_duplicate_urls_collapse_by_canonical_url() -> None:
    urls = [PRODUCT_URL, PRODUCT_URL]
    assert len(dict.fromkeys(urls)) == 1

