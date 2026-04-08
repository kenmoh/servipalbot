"""
ServiPal Marketing Bot - Main FastAPI Application
=================================================
Automated marketing bot for ServiPal multi-service platform.
Handles lead scraping, AI message generation, WhatsApp outreach,
and social media posting with full Supabase integration.
"""

import csv
import io
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from app.scraper.scraper import LeadScraper, BeautifulSoup
from app.ai_engine.engine import AIEngine
from app.media.whatsapp import WhatsAppClient
from app.media.email_client import EmailClient
from app.media.social_media import SocialMediaClient
from app.db.database import SupabaseClient
from app.media.scheduler import BotScheduler
from app.schemas.schemas import (
    ScrapeRequest, OutreachRequest, EmailOutreachRequest, EmailSendRequest, SocialPostRequest,
    BotRunRequest, BotStatus, Lead, LeadImportResult, SettingsUpdateRequest, ChatRequest
)
from app.config.config import settings

# ─── Logging Setup ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("servipal_bot")


# ─── App Lifespan ────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and clean up resources on app start/stop."""
    logger.info("🚀 ServiPal Marketing Bot starting up...")
    app.state.db = SupabaseClient()
    app.state.ai = AIEngine()
    app.state.whatsapp = WhatsAppClient()
    app.state.email = EmailClient()
    app.state.social = SocialMediaClient()
    app.state.scraper = LeadScraper()
    app.state.scheduler = BotScheduler(
        db=app.state.db,
        ai=app.state.ai,
        whatsapp=app.state.whatsapp,
        email=app.state.email,
        social=app.state.social,
        scraper=app.state.scraper,
    )
    logger.info("✅ All modules initialized successfully")
    yield
    await app.state.ai.close()
    await app.state.whatsapp.close()
    await app.state.email.close()
    await app.state.social.close()
    await app.state.scraper.close()
    logger.info("🛑 ServiPal Marketing Bot shutting down...")


# ─── FastAPI App ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="ServiPal Marketing Bot",
    description="Automated AI-powered marketing bot for ServiPal platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health Check ────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    """Check bot health and module status."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "modules": {
            "database": "connected" if app.state.db.enabled else "not_configured",
            "ai_engine": settings.AI_PROVIDER if app.state.ai.enabled else "fallback_only",
            "whatsapp": "ready" if app.state.whatsapp.enabled else "not_configured",
            "social_media": "ready" if app.state.social.enabled else "not_configured",
        },
    }


@app.get("/system/readiness", tags=["System"])
async def get_readiness():
    """Return configuration and integration readiness without exposing secrets."""
    return {
        "timestamp": datetime.now().isoformat(),
        "config": settings.integration_status(),
        "services": {
            "database": await app.state.db.healthcheck(),
            "ai_engine": await app.state.ai.healthcheck(),
            "whatsapp": await app.state.whatsapp.healthcheck(),
            "email": await app.state.email.healthcheck(),
            "social_media": await app.state.social.healthcheck(),
        },
    }


@app.post("/system/settings", tags=["System"])
async def update_settings(request: SettingsUpdateRequest):
    """Update runtime settings like USE_SERPAPI."""
    settings.USE_SERPAPI = request.use_serpapi
    return {
        "message": "Settings updated (runtime only)",
        "config": settings.integration_status()
    }


@app.post("/ai/chat", tags=["AI Interaction"])
async def ai_chat_interaction(request: ChatRequest):
    """Directly interact with the AI model from the dashboard."""
    response_text = await app.state.ai.chat_completion(request.message)
    return {"response": response_text}


# ─── Full Bot Run (Supabase Cron entry point) ─────────────────────────────────
@app.post("/bot/run", tags=["Automation"])
async def run_full_bot_cycle(
    request: BotRunRequest,
    background_tasks: BackgroundTasks,
):
    """
    Full automation cycle triggered by Supabase Cron or manually.
    Runs scraping → AI generation → WhatsApp outreach → Social posts.
    """
    background_tasks.add_task(
        app.state.scheduler.run_full_cycle,
        mode=request.mode,
        dry_run=request.dry_run,
    )
    return {
        "message": f"Bot cycle started in background (mode={request.mode})",
        "dry_run": request.dry_run,
        "triggered_at": datetime.now().isoformat(),
    }


@app.get("/bot/status", response_model=BotStatus, tags=["Automation"])
async def get_bot_status():
    """Get current bot statistics and last run info."""
    return await app.state.scheduler.get_status()


# ─── Lead Scraping ────────────────────────────────────────────────────────────
@app.post("/scrape/leads", tags=["Lead Generation"])
async def scrape_leads(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
):
    """
    Scrape vendor leads from Google Maps, Instagram, or marketplaces.
    Stores new leads in Supabase with status='new'.
    """
    readiness = await app.state.db.healthcheck()
    if not readiness.get("configured"):
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    if not readiness.get("reachable"):
        raise HTTPException(
            status_code=503,
            detail=f"Supabase is not reachable: {readiness.get('error', 'healthcheck failed')}",
        )

    # Fail fast when scraping sources require BeautifulSoup but it's not installed in the runtime.
    if "marketplace" in request.sources and BeautifulSoup is None:
        raise HTTPException(
            status_code=400,
            detail="marketplace scraping requires beautifulsoup4, but it is not installed in this runtime",
        )
    if "google_maps" in request.sources and not settings.serpapi_configured and BeautifulSoup is None:
        raise HTTPException(
            status_code=400,
            detail="google_maps scraping requires SerpAPI or beautifulsoup4 (direct scraping fallback), but neither is available",
        )

    background_tasks.add_task(
        app.state.scraper.scrape_and_store,
        sources=request.sources,
        categories=request.categories,
        location=request.location,
        db=app.state.db,
        max_leads=request.max_leads,
    )
    return {
        "message": "Scraping started in background",
        "sources": request.sources,
        "location": request.location,
    }


@app.get("/leads", tags=["Lead Generation"])
async def get_leads(
    status: str = Query(default=None, description="Filter by status: new/contacted/responded"),
    limit: int = Query(default=50, le=200),
    has_phone: bool = Query(default=False, description="If true, only return leads with phone numbers"),
):
    """Retrieve leads from Supabase with optional status filter."""
    readiness = await app.state.db.healthcheck()
    if not readiness.get("configured"):
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    if not readiness.get("reachable"):
        raise HTTPException(
            status_code=503,
            detail=f"Supabase is not reachable: {readiness.get('error', 'healthcheck failed')}",
        )

    leads = await app.state.db.get_leads(status=status, limit=limit, has_phone=has_phone)
    return {"count": len(leads), "leads": leads}


@app.post("/leads/enrich/emails", tags=["Lead Generation"])
async def enrich_lead_emails_from_websites(
    background_tasks: BackgroundTasks,
    limit: int = Query(default=50, le=200, description="Max leads to scan"),
    dry_run: bool = Query(default=False, description="If true, do not write updates to DB"),
):
    """
    For leads that have a website but no email, scrape the website and update the lead with any email found.
    """
    readiness = await app.state.db.healthcheck()
    if not readiness.get("configured"):
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    if not readiness.get("reachable"):
        raise HTTPException(
            status_code=503,
            detail=f"Supabase is not reachable: {readiness.get('error', 'healthcheck failed')}",
        )

    background_tasks.add_task(
        app.state.scraper.enrich_missing_emails_from_websites,
        db=app.state.db,
        limit=limit,
        dry_run=dry_run,
    )
    return {"message": "Email enrichment started in background", "limit": limit, "dry_run": dry_run}


@app.post("/leads/import/csv", response_model=LeadImportResult, tags=["Lead Generation"])
async def import_leads_csv(file: UploadFile = File(...)):
    """Import curated vendor leads from a CSV file."""
    if not app.state.db.enabled:
        raise HTTPException(status_code=503, detail="Supabase is not configured")

    contents = await file.read()
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Unable to decode CSV: {e}") from e

    reader = csv.DictReader(io.StringIO(text))
    imported = 0
    skipped = 0
    errors: list[str] = []

    for index, row in enumerate(reader, start=2):
        try:
            name = (row.get("business_name") or row.get("name") or "").strip()
            category = (row.get("vendor_type") or row.get("category") or "manual").strip().lower()
            phone = (row.get("phone") or "").strip() or None

            if not name:
                skipped += 1
                errors.append(f"Row {index}: missing business name")
                continue

            lead = Lead(
                name=name,
                category=category,
                phone=phone,
                email=(row.get("email") or "").strip() or None,
                location=(row.get("city") or row.get("location") or "").strip() or None,
                source="manual",
                website=(row.get("website") or "").strip() or None,
                raw_data={"imported_from": file.filename, "row": index},
            )

            existing = None
            if lead.phone:
                existing = await app.state.db.get_lead_by_phone(lead.phone)
            else:
                existing = await app.state.db.get_lead_by_identity(
                    name=lead.name,
                    location=lead.location,
                    website=lead.website,
                )

            if existing:
                fields_to_update = {}
                if lead.email and not existing.get("email"):
                    fields_to_update["email"] = lead.email
                if lead.phone and not existing.get("phone"):
                    fields_to_update["phone"] = lead.phone
                if lead.website and not existing.get("website"):
                    fields_to_update["website"] = lead.website
                if fields_to_update and existing.get("id"):
                    await app.state.db.update_lead(existing["id"], **fields_to_update)
                skipped += 1
                continue

            result = await app.state.db.insert_lead_if_new(lead)
            if result:
                imported += 1
            else:
                skipped += 1
        except Exception as e:
            skipped += 1
            errors.append(f"Row {index}: {str(e)[:200]}")

    return LeadImportResult(imported=imported, skipped=skipped, errors=errors[:25])


# ─── WhatsApp Outreach ────────────────────────────────────────────────────────
@app.post("/outreach/whatsapp", tags=["WhatsApp"])
async def send_whatsapp_outreach(
    request: OutreachRequest,
    background_tasks: BackgroundTasks,
):
    """
    Generate AI messages and send WhatsApp outreach to leads.
    Respects daily rate limits. Updates lead status in Supabase.
    """
    background_tasks.add_task(
        app.state.scheduler.run_whatsapp_outreach,
        lead_ids=request.lead_ids,
        max_messages=request.max_messages,
    )
    return {
        "message": "WhatsApp outreach queued",
        "max_messages": request.max_messages,
    }


@app.post("/outreach/email", tags=["Email"])
async def send_email_outreach(
    request: EmailOutreachRequest,
    background_tasks: BackgroundTasks,
):
    """
    Generate AI cold email drafts for leads with email addresses.
    """
    background_tasks.add_task(
        app.state.scheduler.run_email_outreach,
        lead_ids=request.lead_ids,
        max_emails=request.max_emails,
        dry_run=request.dry_run,
    )
    return {
        "message": "Email draft generation queued",
        "max_emails": request.max_emails,
        "dry_run": request.dry_run,
    }


@app.post("/outreach/email/send", tags=["Email"])
async def send_email_drafts(
    request: EmailSendRequest,
    background_tasks: BackgroundTasks,
):
    """Send previously generated email drafts by id."""
    background_tasks.add_task(
        app.state.scheduler.send_email_drafts,
        email_ids=request.email_ids,
    )
    return {
        "message": "Email send queued",
        "email_ids": request.email_ids,
    }


@app.get("/webhooks/whatsapp", tags=["WhatsApp"])
async def verify_whatsapp_webhook(request: Request):
    """Meta webhook verification handshake."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge", "")

    if mode != "subscribe" or token != settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid webhook verification request")
    return int(challenge) if challenge.isdigit() else challenge


@app.post("/webhooks/whatsapp", tags=["WhatsApp"])
async def receive_whatsapp_webhook(request: Request):
    """Receive WhatsApp delivery and reply webhook payloads."""
    payload = await request.json()
    await app.state.whatsapp.handle_webhook(payload, app.state.db)
    return {"status": "ok"}


# ─── Social Media Posting ─────────────────────────────────────────────────────
@app.post("/social/post", tags=["Social Media"])
async def create_social_post(
    request: SocialPostRequest,
    background_tasks: BackgroundTasks,
):
    """
    Generate AI social media content and post to Facebook/Instagram.
    """
    background_tasks.add_task(
        app.state.scheduler.run_social_posting,
        platforms=request.platforms,
        topic=request.topic,
        post_type=request.post_type,
    )
    return {
        "message": "Social post generation started",
        "platforms": request.platforms,
        "topic": request.topic,
    }


@app.get("/social/posts", tags=["Social Media"])
async def get_social_posts(limit: int = Query(default=20, le=100)):
    """Retrieve recent social media post logs from Supabase."""
    posts = await app.state.db.get_social_posts(limit=limit)
    return {"count": len(posts), "posts": posts}


@app.get("/emails", tags=["Email"])
async def get_email_messages(limit: int = Query(default=50, le=200)):
    """Retrieve recent outbound email records from Supabase."""
    emails = await app.state.db.get_email_messages(limit=limit)
    return {"count": len(emails), "emails": emails}


# ─── Logs ─────────────────────────────────────────────────────────────────────
@app.get("/logs", tags=["Monitoring"])
async def get_logs(
    level: str = Query(default=None, description="Filter: info/warning/error"),
    limit: int = Query(default=100, le=500),
):
    """Retrieve activity logs from Supabase."""
    logs = await app.state.db.get_logs(level=level, limit=limit)
    return {"count": len(logs), "logs": logs}
