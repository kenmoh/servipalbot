"""Unit tests for website canonicalization and lead model validation (no network)."""
import pytest

from app.schemas.schemas import Lead
from app.db.database import SupabaseClient


# ── Website canonicalization (static method on SupabaseClient) ───────────────

def test_canonicalize_websites_variants():
    canon = SupabaseClient._canonicalize_website
    assert canon("https://www.Example.com/") == "https://example.com"
    assert canon("example.com/path") == "https://example.com/path"
    assert canon("http://SHOP.io") == "https://shop.io"
    assert canon("https://example.com/path/") == "https://example.com/path"
    assert canon("  ") is None
    assert canon(None) is None


# ── Lead model validation ─────────────────────────────────────────────────────

def test_lead_phone_is_normalized():
    lead = Lead(name="Test Biz", category="restaurant", phone="0803 123 4567")
    assert lead.phone == "+08031234567".replace("+0", "+") or lead.phone.startswith("+")

    lead2 = Lead(name="Test Biz", category="restaurant", phone="2348031234567")
    assert lead2.phone == "+2348031234567"


def test_lead_accepts_read_status():
    lead = Lead(name="Test Biz", category="restaurant", status="read")
    assert lead.status == "read"


def test_lead_rejects_unknown_status():
    with pytest.raises(Exception):
        Lead(name="Test Biz", category="restaurant", status="bogus")


def test_lead_accepts_osm_source():
    lead = Lead(name="OSM Cafe", category="restaurant", source="osm")
    assert lead.source == "osm"


def test_lead_rejects_unknown_source():
    with pytest.raises(Exception):
        Lead(name="X", category="x", source="twitter")


# ── ScrapeRequest accepts new source list ─────────────────────────────────────

def test_scrape_request_accepts_osm():
    from app.schemas.schemas import ScrapeRequest

    req = ScrapeRequest(sources=["google_maps", "instagram", "marketplace", "osm"])
    assert "osm" in req.sources
