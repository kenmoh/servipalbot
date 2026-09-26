"""
ServiPal Bot - Lead Scraper
============================
Scrapes vendor leads from:
1. Google Maps (SerpAPI primary; DuckDuckGo HTML fallback - no key required)
2. Instagram (business discovery via DuckDuckGo + public profile enrichment)
3. Marketplace listings (Jiji server-rendered category pages)
4. OpenStreetMap (experimental, opt-in via SCRAPER_OVERPASS_ENABLED)

All leads are deduped by phone number and stored in Supabase.
"""

import asyncio
import logging
import re
import urllib.parse
from urllib.parse import parse_qs, urljoin, urlparse
from typing import Any, List, Optional, Dict

import httpx
try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - optional dependency during setup
    BeautifulSoup = None

from app.config.config import settings
from app.schemas.schemas import Lead
from app.db.database import SupabaseClient

logger = logging.getLogger("servipal_bot.scraper")

EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)

PHONE_PATTERN = re.compile(r"\+?\d[\d\s\-()]{7,}\d")

# instagram.com/<reserved>/ are not profile handles
IG_RESERVED_PATHS = {
    "p", "reel", "reels", "tv", "explore", "accounts", "stories", "directory",
    "share", "s", "image", "sharedp", "about", "developer", "legal", "web",
}
IG_HANDLE_PATTERN = re.compile(r"instagram\.com/([A-Za-z0-9_.]{2,30})/?")
IG_APP_ID_HEADER = "936619743392459"  # public web app id used by instagram.com

# DuckDuckGo HTML endpoint (no JS, no key). Documented scraping-friendly.
DDG_HTML_URL = "https://html.duckduckgo.com/html/?q={query}"

# Jiji subcategory slugs (verified server-rendered). Bot categories map onto these.
JIJI_CATEGORY_MAP = {
    "restaurant": "catering",
    "food": "food",
    "delivery": "food-delivery",
    "delivery service": "food-delivery",
    "delivery services": "food-delivery",
    "laundry": "laundry",
    "grocery": "food",
    "grocery store": "food",
    "grocery stores": "food",
    "marketplace": "food",
}
JIJI_KEYWORDS = {
    "restaurant": ["restaurant", "food", "catering", "kitchen", "grill", "chop", "bar", "cafe", "chef", "shawarma"],
    "food": ["food", "catering", "restaurant", "kitchen", "foodstuff"],
    "delivery": ["delivery", "logistics", "courier", "dispatch", "rider", "bike", "haulage", "transport", "mover"],
    "delivery service": ["delivery", "logistics", "courier", "dispatch", "rider", "bike", "haulage", "transport", "mover"],
    "delivery services": ["delivery", "logistics", "courier", "dispatch", "rider", "bike", "haulage", "transport", "mover"],
    "laundry": ["laundry", "cleaning", "dry clean", "dryclean", "wash", "upholstery", "sofa"],
    "grocery": ["grocery", "supermarket", "store", "foodstuff", "provision"],
    "grocery store": ["grocery", "supermarket", "store", "foodstuff", "provision"],
    "grocery stores": ["grocery", "supermarket", "store", "foodstuff", "provision"],
    "marketplace": [],
}

# Overpass amenity/shop filters per bot category
OSM_FILTERS = {
    "restaurant": '["amenity"~"^(restaurant|cafe|fast_food|food_court)$"]',
    "food": '["amenity"~"^(restaurant|cafe|fast_food|food_court)$"]',
    "laundry": '["shop"~"^(laundry|dry_cleaning)$"]',
    "grocery": '["shop"~"^(supermarket|convenience|greengrocer)$"]',
    "grocery store": '["shop"~"^(supermarket|convenience|greengrocer)$"]',
    "delivery": '["office"="courier"]',
    "delivery service": '["office"="courier"]',
    "delivery services": '["office"="courier"]',
}

BLOCKED_EMAIL_DOMAINS = ("example.com", "wix.com", "sentry.io")


class LeadScraper:
    """
    Multi-source lead scraper for vendor discovery.
    Supports Google Maps (SerpAPI / DuckDuckGo fallback), Instagram,
    marketplace (Jiji) and optional OpenStreetMap sources.
    """

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=settings.REQUEST_TIMEOUT,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
            follow_redirects=True,
        )
        logger.info("🔍 Lead scraper initialized")

    # ── Main Entry Point ──────────────────────────────────────────────────────

    async def scrape_and_store(
        self,
        sources: List[str],
        categories: List[str],
        location: str,
        db: SupabaseClient,
        max_leads: int = 50,
    ) -> Dict[str, int]:
        """
        Scrape leads from all configured sources and store in Supabase.
        Returns dict with counts of newly saved leads per source.
        """
        results = {}
        leads_per_source = max_leads // max(len(sources), 1)

        for source in sources:
            logger.info(f"🔍 Scraping from: {source} ({location})")
            leads = []

            try:
                if source == "google_maps":
                    leads = await self.scrape_google_maps(categories, location, leads_per_source)
                elif source == "instagram":
                    leads = await self.scrape_instagram(categories, location, leads_per_source)
                elif source == "marketplace":
                    leads = await self.scrape_marketplace(categories, location, leads_per_source)
                elif source == "osm":
                    leads = await self.scrape_osm(categories, location, leads_per_source)
                else:
                    logger.warning(f"Unknown scraping source: {source}")

                leads = await self._enrich_leads_with_contact_details(leads)

                saved = 0
                updated = 0
                for lead in leads:
                    existing: Optional[Dict[str, Any]] = None
                    if lead.phone:
                        existing = await db.get_lead_by_phone(lead.phone)
                    else:
                        existing = await db.get_lead_by_identity(
                            name=lead.name,
                            location=lead.location,
                            website=lead.website,
                        )

                    # Never insert duplicates. If we discovered new contact info, fill it in.
                    if existing:
                        fields_to_update: Dict[str, Any] = {}
                        if lead.email and not existing.get("email"):
                            fields_to_update["email"] = lead.email
                        if lead.phone and not existing.get("phone"):
                            fields_to_update["phone"] = lead.phone
                        if lead.website and not existing.get("website"):
                            fields_to_update["website"] = lead.website

                        if fields_to_update and existing.get("id"):
                            if await db.update_lead(existing["id"], **fields_to_update):
                                updated += 1
                        continue

                    result = await db.insert_lead_if_new(lead)
                    if result:
                        saved += 1

                results[source] = saved
                logger.info(f"✅ {source}: {saved} new leads saved ({updated} updated)")

                await db.log_activity(
                    event_type="scrape_complete",
                    level="success",
                    message=f"Scraped {saved} new leads from {source} ({updated} updated)",
                    module="scraper",
                    details={
                        "source": source,
                        "location": location,
                        "saved": saved,
                        "updated": updated,
                        "found": len(leads),
                        "with_email": sum(1 for l in leads if l.email),
                        "with_phone": sum(1 for l in leads if l.phone),
                    },
                )

            except Exception as e:
                logger.error(f"❌ Scraping failed for {source}: {e}")
                results[source] = 0
                await db.log_activity(
                    event_type="scrape_error",
                    level="error",
                    message=f"Scraping failed for {source}: {str(e)}",
                    module="scraper",
                )

            # Polite delay between sources
            await asyncio.sleep(2)

        return results

    # ── Google Maps Scraping ──────────────────────────────────────────────────

    async def enrich_missing_emails_from_websites(
        self,
        db: SupabaseClient,
        limit: int = 50,
        dry_run: bool = False,
    ) -> Dict[str, int]:
        """
        For existing leads that have a website but no email, visit the website and try to discover an email.
        If found, update the lead record (unless dry_run=True).
        """
        try:
            records = await db.get_leads_missing_email_with_website(limit=limit)
        except Exception as e:
            logger.error(f"Failed to fetch leads missing email: {e}")
            return {"scanned": 0, "updated": 0}

        scanned = len(records)
        updated = 0

        for record in records:
            lead_id = record.get("id")
            website = record.get("website")
            if not lead_id or not website:
                continue

            try:
                lead = Lead(
                    id=lead_id,
                    name=record.get("name") or "unknown",
                    category=record.get("category") or "manual",
                    phone=record.get("phone"),
                    email=record.get("email"),
                    location=record.get("location"),
                    source=record.get("source") or "manual",
                    status=record.get("status") or "new",
                    quality_score=record.get("quality_score"),
                    priority=record.get("priority"),
                    instagram_handle=record.get("instagram_handle"),
                    website=website,
                    rating=record.get("rating"),
                    review_count=record.get("review_count"),
                    raw_data=record.get("raw_data"),
                )

                enriched = await self._enrich_lead_from_website(lead)
                fields_to_update: Dict[str, Any] = {}
                if enriched.email and not record.get("email"):
                    fields_to_update["email"] = enriched.email
                if enriched.phone and not record.get("phone"):
                    fields_to_update["phone"] = enriched.phone
                if enriched.raw_data and enriched.raw_data != record.get("raw_data"):
                    fields_to_update["raw_data"] = enriched.raw_data

                if fields_to_update:
                    if dry_run:
                        updated += 1
                    else:
                        if await db.update_lead(lead_id, **fields_to_update):
                            updated += 1

            except Exception as e:
                logger.debug(f"Website enrichment failed for lead {lead_id}: {e}")

            await asyncio.sleep(0.5)

        try:
            await db.log_activity(
                event_type="email_enrichment_complete",
                level="success",
                message=f"Website email enrichment completed: {updated}/{scanned} updated (dry_run={dry_run})",
                module="scraper",
                details={"scanned": scanned, "updated": updated, "dry_run": dry_run},
            )
        except Exception:
            pass

        return {"scanned": scanned, "updated": updated}

    async def scrape_google_maps(
        self,
        categories: List[str],
        location: str,
        limit: int = 20,
    ) -> List[Lead]:
        """
        Scrape business leads from Google Maps.
        Primary: SerpAPI Google Maps API. Fallback: DuckDuckGo HTML search
        (free, no key, returns indexable business pages with contact info).
        """
        serpapi_leads: List[Lead] = []

        if settings.serpapi_configured:
            try:
                serpapi_leads = await self._scrape_google_via_serpapi(categories, location, limit)
            except Exception as e:
                logger.warning(f"SerpAPI scrape failed, falling back to DuckDuckGo search: {e}")

            if serpapi_leads:
                logger.info(f"Using SerpAPI results for Google Maps scraping ({len(serpapi_leads)} leads)")
                return self._dedupe_leads(serpapi_leads, limit)

            logger.warning(
                "SerpAPI was configured but returned no usable Google Maps leads. "
                "Falling back to DuckDuckGo HTML search."
            )
        else:
            logger.info("SerpAPI is not configured; using DuckDuckGo fallback for Google Maps scraping")

        fallback_leads = await self._scrape_google_via_ddg(categories, location, limit)
        return self._dedupe_leads(fallback_leads, limit)

    async def _scrape_google_via_serpapi(
        self,
        categories: List[str],
        location: str,
        limit: int,
    ) -> List[Lead]:
        """
        Use SerpAPI Google Maps endpoint (100 free searches/month).
        Docs: https://serpapi.com/google-maps-api
        """
        leads = []
        per_category_limit = max(1, limit // max(len(categories[:3]), 1))

        for category in categories[:3]:  # Limit API calls
            try:
                query = f"{category} in {location}"
                params = {
                    "engine": "google_maps",
                    "q": query,
                    "type": "search",
                    "api_key": settings.SERPAPI_KEY,
                    "hl": "en",
                }

                response = await self.client.get(
                    "https://serpapi.com/search",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

                # Surface SerpAPI-level errors (bad key, quota exhausted, etc.)
                api_error = data.get("error")
                if api_error:
                    lowered = str(api_error).lower()
                    if "quota" in lowered or "run out" in lowered or "limit" in lowered:
                        logger.error(f"  SerpAPI quota exhausted: {api_error}")
                        return []  # No point hitting remaining categories
                    logger.warning(f"  SerpAPI error for '{query}': {api_error}")
                    continue

                local_results = data.get("local_results", [])
                for result in local_results[:per_category_limit]:
                    lead = self._parse_serpapi_result(result, category)
                    if lead:
                        leads.append(lead)

                logger.info(f"  SerpAPI: found {len(local_results)} raw results for '{query}'")
                await asyncio.sleep(1)  # Rate limit

            except Exception as e:
                logger.error(f"  SerpAPI error for {category}: {e}")

        return self._dedupe_leads(leads, limit)

    def _parse_serpapi_result(self, result: dict, category: str) -> Optional[Lead]:
        """Parse a SerpAPI Google Maps result into a Lead."""
        try:
            phone = self._clean_phone(result.get("phone"))
            website = result.get("website")
            address = result.get("address", "")
            name = result.get("title", "Unknown")

            # Keep businesses even when phone is missing so we can enrich/contact them later.
            if not phone and not website and not address:
                return None

            return Lead(
                name=name,
                category=category,
                phone=phone,
                location=address,
                source="google_maps",
                rating=result.get("rating"),
                review_count=result.get("reviews"),
                website=website,
                raw_data={
                    "scrape_method": "serpapi",
                    "place_id": result.get("place_id"),
                    "serpapi_link": result.get("link"),
                },
            )
        except Exception as e:
            logger.debug(f"  Failed to parse result: {e}")
            return None

    async def _scrape_google_via_ddg(
        self,
        categories: List[str],
        location: str,
        limit: int,
    ) -> List[Lead]:
        """
        DuckDuckGo HTML search fallback for business discovery.
        Queries business pages (which carry contact info in title/snippet)
        and extracts names, websites, phones and emails from results.
        """
        leads = []
        per_category_limit = max(1, limit // max(len(categories[:2]), 1))

        for category in categories[:2]:
            try:
                query = f"{category} in {location} contact phone number"
                results = await self._ddg_search(query, max_results=per_category_limit * 2)
                logger.info(f"  DDG fallback: found {len(results)} results for '{query}'")

                for result in results:
                    contact_text = f"{result.get('title', '')} {result.get('snippet', '')}"
                    phone = self._extract_first_phone(contact_text)
                    email = self._extract_first_email(contact_text)
                    website = result.get("url")

                    if not phone and not website:
                        continue

                    leads.append(Lead(
                        name=result.get("title", "Unknown")[:200],
                        category=category,
                        phone=phone,
                        email=email or None,
                        location=location,
                        source="google_maps",
                        website=website,
                        raw_data={"scrape_method": "ddg_fallback"},
                    ))

                    if len(leads) >= per_category_limit:
                        break

                await asyncio.sleep(2)  # Be polite to DDG

            except Exception as e:
                logger.error(f"  DDG fallback error for {category}: {e}")

        return leads

    async def _ddg_search(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """
        Query DuckDuckGo's HTML endpoint and parse organic results.
        Returns list of {title, url, snippet}.
        """
        if BeautifulSoup is None:
            logger.warning("BeautifulSoup is not installed; DuckDuckGo search unavailable")
            return []

        url = DDG_HTML_URL.format(query=urllib.parse.quote_plus(query))
        response = await self.client.get(url)

        if response.status_code in (403, 429):
            logger.warning(f"  DDG rate limited ({response.status_code}); backing off")
            await asyncio.sleep(10)
            return []

        if response.status_code >= 400:
            logger.warning(f"  DDG request failed with status {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        results: List[Dict[str, str]] = []

        for block in soup.select("div.result, div.web-result"):
            link = block.select_one("a.result__a")
            if not link:
                continue
            title = link.get_text(strip=True)
            href = (link.get("href") or "").strip()
            real_url = self._decode_ddg_href(href)
            snippet_el = block.select_one("a.result__snippet, .result__snippet")
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""

            if not title or not real_url:
                continue

            results.append({"title": title, "url": real_url, "snippet": snippet})
            if len(results) >= max_results:
                break

        return results

    @staticmethod
    def _decode_ddg_href(href: str) -> Optional[str]:
        """Resolve DuckDuckGo redirect links (//duckduckgo.com/l/?uddg=<urlencoded>) to the target URL."""
        if not href:
            return None
        if "duckduckgo.com/l/" in href:
            parsed = urlparse(href if href.startswith("http") else f"https:{href}")
            target = parse_qs(parsed.query).get("uddg", [None])[0]
            if target:
                return urllib.parse.unquote(target)
            return None
        if href.startswith("//"):
            return f"https:{href}"
        if href.startswith("http"):
            return href
        return None

    # ── Website Enrichment ────────────────────────────────────────────────────

    async def _enrich_leads_with_contact_details(self, leads: List[Lead]) -> List[Lead]:
        """Fetch website/contact pages to pick up missing emails and extra phone hints."""
        enriched: List[Lead] = []

        for lead in leads:
            if lead.website and not lead.email:
                try:
                    lead = await self._enrich_lead_from_website(lead)
                except Exception as e:
                    logger.debug(f"  Website enrichment failed for {lead.name}: {e}")

            enriched.append(lead)
            await asyncio.sleep(0.5)

        return enriched

    async def _enrich_lead_from_website(self, lead: Lead) -> Lead:
        """Visit the website and contact page, then fill email if found."""
        pages_to_check = [lead.website] if lead.website else []
        visited: set[str] = set()
        discovered_contact_pages: list[str] = []
        found_email: Optional[str] = lead.email
        found_phone: Optional[str] = lead.phone

        while pages_to_check and len(visited) < 3 and (not found_email or not found_phone):
            url = pages_to_check.pop(0)
            if not url or url in visited:
                continue

            visited.add(url)
            response = await self.client.get(url)
            if response.status_code >= 400:
                continue

            html = response.text
            found_email = found_email or self._extract_first_email(html)
            found_phone = found_phone or self._extract_first_phone(html)

            if BeautifulSoup is not None and len(visited) == 1:
                discovered_contact_pages = self._find_contact_pages(html, url)
                for contact_url in discovered_contact_pages:
                    if contact_url not in visited and contact_url not in pages_to_check:
                        pages_to_check.append(contact_url)

        if found_email or found_phone:
            raw_data = dict(lead.raw_data or {})
            raw_data["website_enriched"] = True
            if discovered_contact_pages:
                raw_data["contact_pages_checked"] = discovered_contact_pages[:2]
            lead = lead.model_copy(
                update={
                    "email": found_email or lead.email,
                    "phone": found_phone or lead.phone,
                    "raw_data": raw_data,
                }
            )

        return lead

    # ── Instagram Scraping ────────────────────────────────────────────────────

    async def scrape_instagram(
        self,
        categories: List[str],
        location: str,
        limit: int = 20,
    ) -> List[Lead]:
        """
        Discover Instagram business accounts via DuckDuckGo site search
        (`site:instagram.com {category} {location}`), then enrich each handle
        through Instagram's public web profile API (followers, bio, email,
        external website). Handles are stored even if enrichment is rate limited.
        """
        handles: List[str] = []

        for category in categories[:2]:
            try:
                query = f"site:instagram.com {category} {location}"
                results = await self._ddg_search(query, max_results=limit)
                found = self._extract_ig_handles(results)
                logger.info(f"  Instagram discovery: {len(found)} handles for '{query}'")

                for handle in found:
                    if handle not in handles:
                        handles.append(handle)

                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"  Instagram discovery error for {category}: {e}")

        if not handles:
            logger.info("  Instagram: no business handles discovered")
            return []

        # Enrich profiles (rate-limit aware; on 429 we keep what we have)
        enrich_budget = max(0, min(settings.SCRAPER_INSTAGRAM_MAX_PROFILES, len(handles)))
        leads: List[Lead] = []
        enriched_count = 0

        for handle in handles:
            profile: Optional[Dict[str, Any]] = None
            if enriched_count < enrich_budget:
                profile = await self._fetch_ig_profile(handle)
                if profile == "rate_limited":
                    logger.warning("  Instagram profile API rate limited; storing remaining handles unenriched")
                    profile = None
                    enrich_budget = 0  # stop further attempts this run
                elif profile:
                    enriched_count += 1
                await asyncio.sleep(1.5)

            lead = self._ig_profile_to_lead(profile, handle, categories, location)
            leads.append(lead)

            if len(leads) >= limit:
                break

        logger.info(
            f"  Instagram: {len(leads)} leads ({enriched_count} profiles enriched)"
        )
        return leads

    @staticmethod
    def _extract_ig_handles(results: List[Dict[str, str]]) -> List[str]:
        """Pull Instagram profile handles out of search result URLs/snippets."""
        handles: List[str] = []
        for result in results:
            haystack = f"{result.get('url', '')} {result.get('snippet', '')}"
            for match in IG_HANDLE_PATTERN.finditer(haystack):
                handle = match.group(1).strip(".-_").lower()
                if (
                    handle
                    and handle not in IG_RESERVED_PATHS
                    and not handle.isdigit()
                    and handle not in handles
                ):
                    handles.append(handle)
        return handles

    async def _fetch_ig_profile(self, handle: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a public Instagram profile via the web profile API.
        Returns the user dict, the string "rate_limited" on 429, or None on failure.
        """
        url = "https://www.instagram.com/api/v1/users/web_profile_info/"
        headers = {
            "x-ig-app-id": IG_APP_ID_HEADER,
            "x-requested-with": "XMLHttpRequest",
            "Accept": "application/json",
        }
        try:
            response = await self.client.get(
                url,
                params={"username": handle},
                headers=headers,
            )
            if response.status_code == 429:
                return "rate_limited"
            if response.status_code == 404:
                return None
            if response.status_code >= 400:
                logger.debug(f"  IG profile fetch for {handle}: HTTP {response.status_code}")
                return None

            data = response.json()
            return (data.get("data") or {}).get("user") or None

        except Exception as e:
            logger.debug(f"  IG profile fetch failed for {handle}: {e}")
            return None

    def _ig_profile_to_lead(
        self,
        profile: Optional[Dict[str, Any]],
        handle: str,
        categories: List[str],
        location: str,
    ) -> Lead:
        """Convert an Instagram profile (or bare handle) into a Lead."""
        raw_data: Dict[str, Any] = {
            "scrape_method": "ddg_discovery",
            "instagram_handle": handle,
        }

        name = handle
        email: Optional[str] = None
        website: Optional[str] = None
        follower_count: Optional[int] = None

        if isinstance(profile, dict):
            name = profile.get("full_name") or handle
            biography = profile.get("biography") or ""
            email = (profile.get("business_email") or "").strip() or None
            website = (profile.get("external_url") or "").strip() or None
            followed_by = profile.get("edge_followed_by") or {}
            try:
                follower_count = int(followed_by.get("count", 0)) or None
            except (TypeError, ValueError):
                follower_count = None

            raw_data["scrape_method"] = "ddg_discovery+ig_profile"
            raw_data["bio_snippet"] = biography[:200] if biography else None
            raw_data["followers"] = follower_count
            raw_data["is_business"] = bool(profile.get("is_business") or profile.get("business_category_name"))

            if not email:
                email = self._extract_first_email(biography)

        category = categories[0] if categories else "instagram"
        return Lead(
            name=name[:200],
            category=category,
            email=email,
            location=location,
            source="instagram",
            instagram_handle=handle,
            website=website,
            quality_score=None,
            raw_data=raw_data,
        )

    # ── Marketplace Scraping (Jiji) ───────────────────────────────────────────

    async def scrape_marketplace(
        self,
        categories: List[str],
        location: str,
        limit: int = 20,
    ) -> List[Lead]:
        """
        Scrape Jiji (West Africa) server-rendered category pages.
        The old `/{city}/{category}` URLs 404; verified working pages are
        `/{city}/{jiji_category}` (e.g. /lagos/services). Listings are filtered
        by category keywords so only relevant businesses become leads.
        """
        if BeautifulSoup is None:
            logger.warning("BeautifulSoup is not installed; skipping marketplace scraping")
            return []

        leads: List[Lead] = []
        city_slug = self._jiji_city_slug(location)

        seen_urls: set[str] = set()

        for category in categories[:2]:
            key = self._jiji_category_key(category)
            jiji_category = JIJI_CATEGORY_MAP.get(key, "services")
            page_url = f"https://jiji.ng/{city_slug}/{jiji_category}"
            if page_url in seen_urls:
                # Same page as a previous category; filter with this category's keywords too.
                continue
            seen_urls.add(page_url)

            try:
                response = await self.client.get(page_url)
                if response.status_code != 200:
                    # Subcategory missing: fall back to the generic services page.
                    page_url = f"https://jiji.ng/{city_slug}/services"
                    response = await self.client.get(page_url)
                if response.status_code != 200:
                    logger.warning(
                        f"  Marketplace: Jiji returned {response.status_code} for {page_url}"
                    )
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                titles = self._parse_jiji_titles(soup)
                keywords = JIJI_KEYWORDS.get(key, [])
                matched = 0

                for title, price in titles:
                    if not title:
                        continue
                    lowered = title.lower()
                    if keywords and not any(k in lowered for k in keywords):
                        continue

                    leads.append(Lead(
                        name=title[:200],
                        category=category,
                        phone=None,  # Jiji hides phone numbers behind "show contact"
                        location=location,
                        source="marketplace",
                        raw_data={
                            "scrape_method": "jiji_ssr",
                            "source_page": page_url,
                            "price": price,
                        },
                    ))
                    matched += 1
                    if matched >= limit // 2 or len(leads) >= limit:
                        break

                logger.info(
                    f"  Marketplace: {matched} relevant listings for '{category}' "
                    f"on {page_url} ({len(titles)} total)"
                )
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"  Marketplace scrape error: {e}")

        return leads

    @staticmethod
    def _jiji_city_slug(location: str) -> str:
        """Convert 'Lagos, Nigeria' -> 'lagos' for Jiji URLs."""
        city = location.split(",")[0].strip().lower()
        return re.sub(r"\s+", "-", city) or "lagos"

    @staticmethod
    def _jiji_category_key(category: str) -> str:
        """Normalize a bot category so plural variants map to the same Jiji slug."""
        key = category.lower().strip()
        if key in JIJI_CATEGORY_MAP:
            return key
        return key.rstrip("s") if key.rstrip("s") in JIJI_CATEGORY_MAP else key

    @staticmethod
    def _parse_jiji_titles(soup: Any) -> List[tuple]:
        """Extract (title, price) pairs from Jiji server-rendered listing markup."""
        items: List[tuple] = []
        seen_titles: set[str] = set()
        title_els = soup.select(
            ".qa-advert-title, .b-advert-title-inner, .b-list-advert-base__item-title"
        )
        for title_el in title_els:
            title = title_el.get_text(" ", strip=True)
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            # Price sits elsewhere in the same advert card; climb to the card root
            # (exact class match - the title div's own class contains a longer variant).
            card = title_el.find_parent(class_="b-list-advert-base")
            price = None
            if card:
                price_el = card.select_one(".qa-advert-price, .b-list-advert__price-base")
                price = price_el.get_text(" ", strip=True) if price_el else None
            items.append((title, price))
        return items

    # ── OpenStreetMap (experimental) ──────────────────────────────────────────

    async def scrape_osm(
        self,
        categories: List[str],
        location: str,
        limit: int = 20,
    ) -> List[Lead]:
        """
        Optional OpenStreetMap source via Overpass API. Disabled by default
        (SCRAPER_OVERPASS_ENABLED). Never fails the run: any error is logged
        and returns 0 leads. Only POIs carrying contact tags are returned.
        """
        if not settings.overpass_enabled:
            logger.info("  OSM source is disabled (SCRAPER_OVERPASS_ENABLED=false)")
            return []

        leads: List[Lead] = []
        city = location.split(",")[0].strip()
        category = categories[0].lower().strip() if categories else "restaurant"
        tag_filter = OSM_FILTERS.get(category)

        if not tag_filter:
            logger.info(f"  OSM: no mapping for category '{category}', skipping")
            return []

        # Union POIs with phone or email tags inside the named city area.
        query = (
            "[out:json][timeout:20];"
            f"area['name'='{city}']->.a;"
            f"(nwr(area.a){tag_filter}['phone'];"
            f"nwr(area.a){tag_filter}['email'];);"
            f"out center {max(limit * 2, 20)};"
        )

        try:
            response = await self.client.get(
                settings.SCRAPER_OVERPASS_URL,
                params={"data": query},
                timeout=25,
            )
            if response.status_code != 200:
                logger.warning(f"  OSM: Overpass returned {response.status_code}")
                return []

            elements = response.json().get("elements", [])
            for el in elements:
                tags = el.get("tags", {})
                name = tags.get("name")
                if not name:
                    continue

                phone = self._clean_phone(tags.get("phone") or tags.get("contact:phone"))
                email = (tags.get("email") or tags.get("contact:email") or "").strip() or None
                website = (tags.get("website") or tags.get("contact:website") or "").strip() or None

                if not phone and not email and not website:
                    continue

                street = tags.get("addr:street", "")
                house = tags.get("addr:housenumber", "")
                addr = f"{house} {street}".strip() or None

                leads.append(Lead(
                    name=name[:200],
                    category=category,
                    phone=phone,
                    email=email,
                    location=addr or city,
                    source="osm",
                    website=website,
                    raw_data={
                        "scrape_method": "overpass",
                        "osm_type": el.get("type"),
                        "osm_id": el.get("id"),
                    },
                ))
                if len(leads) >= limit:
                    break

            logger.info(f"  OSM: {len(leads)} leads for '{category}' in {city}")

        except Exception as e:
            logger.warning(f"  OSM scrape failed (non-fatal): {e}")

        return leads

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _clean_phone(self, phone: Optional[str]) -> Optional[str]:
        """Normalize phone number to E.164 format."""
        if not phone:
            return None
        # Remove all non-digit characters except +
        cleaned = re.sub(r"[^\d+]", "", phone.strip())
        if not cleaned or len(cleaned) < 7:
            return None
        # Ensure country code prefix
        if not cleaned.startswith("+"):
            if cleaned.startswith("0"):
                cleaned = "+234" + cleaned[1:]   # Nigeria default
            elif len(cleaned) == 10:
                cleaned = "+234" + cleaned        # Assume Nigeria
            else:
                cleaned = "+" + cleaned
        return cleaned

    def _dedupe_leads(self, leads: List[Lead], limit: int) -> List[Lead]:
        """Deduplicate scraped leads by phone first, then by business identity."""
        deduped: List[Lead] = []
        seen_keys: set[str] = set()

        for lead in leads:
            key = lead.phone or f"{lead.name.strip().lower()}::{(lead.location or '').strip().lower()}"
            if not key or key in seen_keys:
                continue

            seen_keys.add(key)
            deduped.append(lead)

            if len(deduped) >= limit:
                break

        return deduped

    def _extract_first_email(self, text: str) -> Optional[str]:
        """Extract the first usable email from page text/html."""
        if not text:
            return None

        # Prefer explicit mailto: links when available (often more reliable than regex on scripts/styles).
        if BeautifulSoup is not None and "mailto:" in text.lower():
            try:
                soup = BeautifulSoup(text, "html.parser")
                for link in soup.select("a[href^='mailto:']"):
                    href = (link.get("href") or "").strip()
                    candidate = href.split(":", 1)[-1].split("?", 1)[0].strip()
                    if candidate and EMAIL_PATTERN.fullmatch(candidate):
                        lowered = candidate.lower()
                        if any(blocked in lowered for blocked in BLOCKED_EMAIL_DOMAINS):
                            continue
                        return candidate
            except Exception:
                pass

        emails = EMAIL_PATTERN.findall(text or "")
        for email in emails:
            lowered = email.lower()
            if any(blocked in lowered for blocked in BLOCKED_EMAIL_DOMAINS):
                continue
            return email
        return None

    def _extract_first_phone(self, text: str) -> Optional[str]:
        """Extract the first usable phone number from page text/html."""
        candidates = PHONE_PATTERN.findall(text or "")
        for candidate in candidates:
            cleaned = self._clean_phone(candidate)
            if cleaned:
                return cleaned
        return None

    def _find_contact_pages(self, html: str, base_url: str) -> List[str]:
        """Find likely contact/about pages from a business website homepage."""
        if BeautifulSoup is None:
            return []

        soup = BeautifulSoup(html, "html.parser")
        candidates: List[str] = []

        for link in soup.select("a[href]"):
            href = (link.get("href") or "").strip()
            label = link.get_text(" ").lower()
            haystack = f"{href.lower()} {label}"
            if any(keyword in haystack for keyword in ("contact", "about", "support", "reach-us")):
                absolute = urljoin(base_url, href)
                if absolute.startswith("http") and absolute not in candidates:
                    candidates.append(absolute)

            if len(candidates) >= 2:
                break

        return candidates

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
