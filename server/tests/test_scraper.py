"""Unit tests for the lead scraper (no network)."""
from typing import Any, Dict, List, Optional

import pytest

from app.config.config import settings
from app.schemas.schemas import Lead
from app.scraper.scraper import (
    IG_RESERVED_PATHS,
    LeadScraper,
)


@pytest.fixture
def scraper() -> LeadScraper:
    return LeadScraper()


# ── Phone cleaning ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+234 802 777 7666", "+2348027777666"),
        ("0803 123 4567", "+2348031234567"),
        ("8031234567", "+2348031234567"),
        ("+1 (415) 555-2671", "+14155552671"),
        ("12345", None),
        ("", None),
        (None, None),
        ("tel:+2349012345678", "+2349012345678"),
    ],
)
def test_clean_phone(scraper: LeadScraper, raw, expected):
    assert scraper._clean_phone(raw) == expected


# ── Email extraction ──────────────────────────────────────────────────────────

def test_extract_email_prefers_mailto(scraper: LeadScraper):
    html = '<a href="mailto:info@business.com">Mail</a> contact@example.com'
    assert scraper._extract_first_email(html) == "info@business.com"


def test_extract_email_skips_blocked_domains(scraper: LeadScraper):
    html = "Reach us at info@wix.com or team@realbusiness.com"
    assert scraper._extract_first_email(html) == "team@realbusiness.com"


def test_extract_email_none(scraper: LeadScraper):
    assert scraper._extract_first_email("no contact here") is None


# ── Phone extraction from text ────────────────────────────────────────────────

def test_extract_phone_from_text(scraper: LeadScraper):
    text = "Call our Lagos office at +234 809 555 1234 today."
    assert scraper._extract_first_phone(text) == "+2348095551234"


def test_extract_phone_ignores_short_numbers(scraper: LeadScraper):
    assert scraper._extract_first_phone("Order ref 12345 confirmed") is None


# ── DuckDuckGo helpers ────────────────────────────────────────────────────────

def test_decode_ddg_redirect(scraper: LeadScraper):
    href = (
        "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.example.com%2Fbiz&rut=abc"
    )
    assert scraper._decode_ddg_href(href) == "https://www.example.com/biz"


def test_decode_ddg_passthrough(scraper: LeadScraper):
    assert scraper._decode_ddg_href("https://example.com") == "https://example.com"
    assert scraper._decode_ddg_href("//example.com/page") == "https://example.com/page"
    assert scraper._decode_ddg_href("") is None


def test_extract_ig_handles_filters_reserved():
    results = [
        {"url": "https://instagram.com/cactuslagos/", "snippet": ""},
        {"url": "https://instagram.com/p/Cx123abc/", "snippet": ""},
        {"url": "https://instagram.com/explore/tags/food/", "snippet": ""},
        {"url": "", "snippet": "see instagram.com/nest.lagos for more"},
    ]
    handles = LeadScraper._extract_ig_handles(results)
    assert "cactuslagos" in handles
    assert "nest.lagos" in handles
    assert "p" not in handles
    assert "explore" not in handles


def test_ig_reserved_paths_no_duplicates():
    assert "p" in IG_RESERVED_PATHS
    assert "explore" in IG_RESERVED_PATHS


def test_ig_profile_to_lead_full(scraper: LeadScraper):
    profile: Dict[str, Any] = {
        "full_name": "Cactus Lagos",
        "biography": "Best brunch in Lagos. Bookings: hello@cactuslagos.com",
        "business_email": "bookings@cactuslagos.com",
        "external_url": "https://cactuslagos.com",
        "edge_followed_by": {"count": 15200},
        "is_business": True,
        "business_category_name": "Restaurants",
    }
    lead = scraper._ig_profile_to_lead(profile, "cactuslagos", ["restaurant"], "Lagos, Nigeria")
    assert lead.name == "Cactus Lagos"
    assert lead.email == "bookings@cactuslagos.com"
    assert lead.website == "https://cactuslagos.com"
    assert lead.instagram_handle == "cactuslagos"
    assert lead.source == "instagram"
    assert lead.raw_data["followers"] == 15200
    assert lead.raw_data["is_business"] is True


def test_ig_profile_to_lead_bare_handle(scraper: LeadScraper):
    lead = scraper._ig_profile_to_lead(None, "gras_lagos", ["restaurant"], "Lagos")
    assert lead.name == "gras_lagos"
    assert lead.instagram_handle == "gras_lagos"
    assert lead.raw_data["scrape_method"] == "ddg_discovery"


# ── SerpAPI result parsing ────────────────────────────────────────────────────

def test_parse_serpapi_result(scraper: LeadScraper):
    result = {
        "title": "Cactus Restaurant",
        "address": "20/24 Ozumba Mbadiwe Ave, Victoria Island, Lagos",
        "phone": "+234 802 777 7666",
        "website": "https://www.facebook.com/CactusBakery",
        "rating": 4.4,
        "reviews": 512,
        "place_id": "ChIJabc123",
    }
    lead = scraper._parse_serpapi_result(result, "restaurant")
    assert lead is not None
    assert lead.name == "Cactus Restaurant"
    assert lead.phone == "+2348027777666"
    assert lead.source == "google_maps"
    assert lead.raw_data["scrape_method"] == "serpapi"
    assert lead.raw_data["place_id"] == "ChIJabc123"


def test_parse_serpapi_result_requires_some_contact(scraper: LeadScraper):
    assert scraper._parse_serpapi_result({"title": "Ghost Business"}, "restaurant") is None


# ── Dedupe ────────────────────────────────────────────────────────────────────

def test_dedupe_leads_by_phone(scraper: LeadScraper):
    a = Lead(name="Alpha Biz", category="x", phone="+2348011111111", location="Lagos")
    b = Lead(name="Beta Biz", category="x", phone="+234 801 111 1111", location="Lagos")
    deduped = scraper._dedupe_leads([a, b], limit=10)
    assert len(deduped) == 1


def test_dedupe_leads_by_identity(scraper: LeadScraper):
    a = Lead(name="Same Name", category="x", location="Lagos")
    b = Lead(name="Same Name", category="x", location="Lagos")
    deduped = scraper._dedupe_leads([a, b], limit=10)
    assert len(deduped) == 1


def test_dedupe_respects_limit(scraper: LeadScraper):
    leads = [Lead(name=f"Biz Number {i}", category="x", phone=f"+23480123456{i:02d}") for i in range(5)]
    deduped = scraper._dedupe_leads(leads, limit=2)
    assert len(deduped) == 2


# ── Jiji parsing ──────────────────────────────────────────────────────────────

JIJI_HTML = """
<div class="b-list-advert-base">
  <div class="b-list-advert-base__item-title">
    <div class="b-advert-title-inner qa-advert-title">Mama's Kitchen Catering Services</div>
  </div>
  <div class="b-list-advert-base__data">
    <div class="qa-advert-price">NGN 25,000</div>
  </div>
</div>
<div class="b-list-advert-base">
  <div class="b-list-advert-base__item-title">
    <div class="b-advert-title-inner qa-advert-title">Toyota Corolla 2008</div>
  </div>
</div>
"""


def test_parse_jiji_titles(scraper: LeadScraper):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(JIJI_HTML, "html.parser")
    items = scraper._parse_jiji_titles(soup)
    titles = [t for t, _ in items]
    assert "Mama's Kitchen Catering Services" in titles
    assert "Toyota Corolla 2008" in titles
    prices = dict(items)
    assert prices["Mama's Kitchen Catering Services"] == "NGN 25,000"


def test_jiji_city_slug():
    assert LeadScraper._jiji_city_slug("Lagos, Nigeria") == "lagos"
    assert LeadScraper._jiji_city_slug("Abuja") == "abuja"


# ── Contact page discovery ────────────────────────────────────────────────────

def test_find_contact_pages(scraper: LeadScraper):
    from bs4 import BeautifulSoup  # noqa: F401

    html = """
    <a href="/contact-us">Contact</a>
    <a href="/menu">Menu</a>
    <a href="/about">About Us</a>
    """
    pages = scraper._find_contact_pages(html, "https://example.com")
    assert "https://example.com/contact-us" in pages
    assert "https://example.com/about" in pages
    assert "https://example.com/menu" not in pages
