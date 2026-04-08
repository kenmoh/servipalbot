"""
ServiPal Bot - Lead Scraper
============================
Scrapes vendor leads from:
1. Google Maps (via SerpAPI or direct scraping)
2. Instagram business accounts (via public search)
3. Marketplace listings (configurable)

All leads are deduped by phone number and stored in Supabase.
"""

import asyncio
import logging
import re
import urllib.parse
from urllib.parse import urljoin
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


class LeadScraper:
    """
    Multi-source lead scraper for vendor discovery.
    Supports Google Maps (SerpAPI/direct), Instagram, and marketplace sources.
    """

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=settings.REQUEST_TIMEOUT,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
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
        Returns dict with counts per source.
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
                    details={"source": source, "location": location, "saved": saved, "updated": updated},
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
        Uses SerpAPI as the primary source and BeautifulSoup scraping as a fallback.
        """
        serpapi_leads: List[Lead] = []

        if settings.serpapi_configured:
            try:
                serpapi_leads = await self._scrape_google_via_serpapi(categories, location, limit)
            except Exception as e:
                logger.warning(f"SerpAPI scrape failed, falling back to BeautifulSoup scraping: {e}")

            if serpapi_leads:
                logger.info(f"Using SerpAPI results for Google Maps scraping ({len(serpapi_leads)} leads)")
                return self._dedupe_leads(serpapi_leads, limit)

            logger.warning(
                "SerpAPI was configured but returned no usable Google Maps leads. "
                "Falling back to BeautifulSoup scraping."
            )
        else:
            logger.info("SerpAPI is not configured; using BeautifulSoup fallback for Google scraping")

        fallback_leads = await self._scrape_google_direct(categories, location, limit)
        return self._dedupe_leads(fallback_leads, limit)

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

                for result in data.get("local_results", [])[:per_category_limit]:
                    lead = self._parse_serpapi_result(result, category)
                    if lead:
                        leads.append(lead)

                logger.info(f"  SerpAPI: found {len(data.get('local_results', []))} raw results for '{query}'")
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

    async def _scrape_google_direct(
        self,
        categories: List[str],
        location: str,
        limit: int,
    ) -> List[Lead]:
        """
        Direct Google search scraping (no API key required).
        NOTE: This is rate-limited and may be blocked. For production,
        use SerpAPI or a proxy service.
        """
        if BeautifulSoup is None:
            logger.warning("BeautifulSoup is not installed; skipping direct Google scraping")
            return []

        leads = []
        per_category_limit = max(1, limit // max(len(categories[:2]), 1))

        for category in categories[:2]:
            try:
                query = f"{category} near {location} phone number"
                encoded = urllib.parse.quote_plus(query)
                url = f"https://www.google.com/search?q={encoded}&num=20"

                response = await self.client.get(url)
                if response.status_code == 429:
                    logger.warning("  ⚠️ Google rate limit hit, waiting 30s...")
                    await asyncio.sleep(30)
                    continue

                if response.status_code >= 400:
                    logger.warning(
                        f"  Direct scrape request failed for '{category}' with status {response.status_code}"
                    )
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                extracted = self._extract_from_google_html(soup, category, location)
                leads.extend(extracted[:per_category_limit])

                logger.info(f"  Direct scrape: found {len(extracted)} results for '{category}'")
                await asyncio.sleep(3)  # Be polite

            except Exception as e:
                logger.error(f"  Direct scrape error for {category}: {e}")

        return self._dedupe_leads(leads, limit)

    def _extract_from_google_html(
        self,
        soup: Any,
        category: str,
        location: str,
    ) -> List[Lead]:
        """Extract business info from Google search HTML."""
        leads = []

        # Look for structured business panels
        for panel in soup.select("[data-attrid*='kc:/local']"):
            try:
                name_el = panel.select_one("h2, h3, .title")
                phone_el = panel.select_one("[data-dtype='d3ph']")

                if name_el and phone_el:
                    leads.append(Lead(
                        name=name_el.get_text(strip=True),
                        category=category,
                        phone=self._clean_phone(phone_el.get_text(strip=True)),
                        location=location,
                        source="google_maps",
                        raw_data={"scrape_method": "bs4_google_fallback"},
                    ))
            except Exception:
                continue

        # Also search for phone numbers in plain text snippets
        phone_pattern = re.compile(r"\+?[\d\s\-()]{10,15}")
        for result in soup.select(".g, .tF2Cxc")[:10]:
            try:
                title_el = result.select_one("h3")
                snippet_el = result.select_one(".VwiC3b, .s")
                text = result.get_text()
                phones = phone_pattern.findall(text)

                if title_el and phones:
                    leads.append(Lead(
                        name=title_el.get_text(strip=True),
                        category=category,
                        phone=self._clean_phone(phones[0]),
                        location=location,
                        source="google_maps",
                        raw_data={"scrape_method": "bs4_google_fallback"},
                    ))
            except Exception:
                continue

        return leads

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
                        if any(blocked in lowered for blocked in ("example.com", "wix.com", "sentry.io")):
                            continue
                        return candidate
            except Exception:
                pass

        emails = EMAIL_PATTERN.findall(text or "")
        for email in emails:
            lowered = email.lower()
            if any(blocked in lowered for blocked in ("example.com", "wix.com", "sentry.io")):
                continue
            return email
        return None

    def _extract_first_phone(self, text: str) -> Optional[str]:
        """Extract the first usable phone number from page text/html."""
        candidates = re.findall(r"\+?\d[\d\s\-()]{8,}\d", text or "")
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

    # ── Instagram Scraping ────────────────────────────────────────────────────

    async def scrape_instagram(
        self,
        categories: List[str],
        location: str,
        limit: int = 20,
    ) -> List[Lead]:
        """
        Scrape Instagram business accounts using hashtag/location search.
        NOTE: Instagram heavily restricts scraping. This uses public pages only.
        For production, consider Instagram Basic Display API.
        """
        leads = []

        for category in categories[:2]:
            try:
                # Search relevant hashtags
                hashtag = f"{category.replace(' ', '')}{''.join(location.split()[:1])}"
                url = f"https://www.instagram.com/explore/tags/{hashtag}/?__a=1&__d=dis"

                response = await self.client.get(
                    url,
                    headers={"Accept": "application/json"},
                )

                if response.status_code == 200:
                    try:
                        data = response.json()
                        posts = data.get("graphql", {}).get("hashtag", {}).get(
                            "edge_hashtag_to_media", {}
                        ).get("edges", [])

                        for edge in posts[:limit // 2]:
                            node = edge.get("node", {})
                            owner = node.get("owner", {})

                            # Only get accounts that might be businesses
                            if owner.get("is_verified") or node.get("location"):
                                leads.append(Lead(
                                    name=owner.get("username", "unknown"),
                                    category=category,
                                    location=location,
                                    instagram_handle=owner.get("username"),
                                    source="instagram",

                                ))
                    except Exception:
                        pass

                await asyncio.sleep(2)

            except Exception as e:
                logger.debug(f"  Instagram scrape error for {category}: {e}")

        logger.info(f"  Instagram: found {len(leads)} potential leads")
        return leads

    # ── Marketplace Scraping ──────────────────────────────────────────────────

    async def scrape_marketplace(
        self,
        categories: List[str],
        location: str,
        limit: int = 20,
    ) -> List[Lead]:
        """
        Scrape marketplace listings. Configured for Jiji (West Africa).
        Extend this method for other marketplaces (OLX, Craigslist, etc.)
        """
        if BeautifulSoup is None:
            logger.warning("BeautifulSoup is not installed; skipping marketplace scraping")
            return []

        leads = []

        for category in categories[:2]:
            try:
                city = location.split(",")[0].strip().lower().replace(" ", "-")
                url = f"https://jiji.ng/{city}/{category}"

                response = await self.client.get(url)
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                listings = soup.select(".qa-advert-list-item, .b-list-advert__item")

                for listing in listings[:limit // 2]:
                    try:
                        name_el = listing.select_one("h3, .b-advert__title, .qa-advert-title")
                        phone_el = listing.select_one("[href^='tel:']")

                        if name_el:
                            phone = None
                            if phone_el:
                                phone = phone_el.get("href", "").replace("tel:", "")

                            leads.append(Lead(
                                name=name_el.get_text(strip=True),
                                category=category,
                                phone=self._clean_phone(phone) if phone else None,
                                location=location,
                                source="marketplace",
                            ))
                    except Exception:
                        continue

                logger.info(f"  Marketplace: found {len(leads)} listings for {category}")
                await asyncio.sleep(2)

            except Exception as e:
                logger.debug(f"  Marketplace scrape error: {e}")

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

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
