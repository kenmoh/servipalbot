"""
ServiPal Bot - Scheduler & Orchestrator
========================================
Orchestrates the full bot automation cycle:
1. Scrape new leads
2. Classify and filter leads
3. Generate + send WhatsApp outreach
4. Generate + publish social posts
5. Log all activities

Designed to be triggered by Supabase Cron or manual API call.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict

from app.config.config import settings
from app.schemas.schemas import BotStatus, Lead
from app.db.database import SupabaseClient
from app.ai_engine.engine import AIEngine
from app.media.whatsapp import WhatsAppClient
from app.media.email_client import EmailClient
from app.media.social_media import SocialMediaClient
from app.scraper.scraper import LeadScraper
from app.media.notifier import Notifier

logger = logging.getLogger("servipal_bot.scheduler")


# Default scrape config — adjust to your target market
DEFAULT_SCRAPE_CONFIG = {
    "sources": ["google_maps", "marketplace"],
    "categories": ["restaurant", "laundry", "delivery service", "grocery store"],
    "location": "Lagos, Nigeria",
    "max_leads": 30,
}

# Social post topics rotated daily
DAILY_POST_TOPICS = [
    "How ServiPal helps restaurants get more delivery orders",
    "Why laundry businesses are growing faster with ServiPal",
    "Success story: Local business doubled orders on ServiPal",
    "Tips for vendors: How to maximize your ServiPal profile",
    "ServiPal marketplace — where buyers meet the best local sellers",
    "Fast, reliable delivery powered by ServiPal partners",
    "Join thousands of vendors already earning more with ServiPal",
]


class BotScheduler:
    """
    Central orchestrator for all bot automation tasks.
    Maintains state and coordinates between modules.
    """

    def __init__(
        self,
        db: SupabaseClient,
        ai: AIEngine,
        whatsapp: WhatsAppClient,
        email: EmailClient,
        social: SocialMediaClient,
        scraper: LeadScraper,
    ):
        self.db = db
        self.ai = ai
        self.whatsapp = whatsapp
        self.email = email
        self.social = social
        self.scraper = scraper
        self.notifier = Notifier()

        self._last_run_at: Optional[datetime] = None
        self._last_run_status: Optional[str] = None

        logger.info("⚙️ Bot scheduler initialized")

    # ── Full Automation Cycle ─────────────────────────────────────────────────

    async def run_full_cycle(
        self,
        mode: str = "full",
        dry_run: bool = False,
    ) -> Dict:
        """
        Execute the complete bot automation cycle.

        Mode options:
        - "full": scrape → classify → outreach → social post
        - "scrape_only": only scrape and classify leads
        - "outreach_only": only send WhatsApp messages
        - "social_only": only publish social media posts

        dry_run=True: generate content without sending/posting.
        """
        started_at = datetime.now()
        summary = {
            "mode": mode,
            "dry_run": dry_run,
            "started_at": started_at.isoformat(),
            "new_leads": 0,
            "messages_sent": 0,
            "posts_published": 0,
            "errors": [],
        }

        logger.info(f"🚀 Bot cycle starting | mode={mode} | dry_run={dry_run}")
        await self.db.log_activity(
            event_type="bot_cycle_start",
            level="info",
            message=f"Bot cycle started (mode={mode})",
            module="scheduler",
            details={"dry_run": dry_run, "mode": mode},
        )

        try:
            # ── Step 1: Scrape Leads ──────────────────────────────────────────
            if mode in ("full", "scrape_only"):
                logger.info("Step 1/4: 🔍 Scraping new leads...")
                try:
                    scrape_results = await self.scraper.scrape_and_store(
                        sources=DEFAULT_SCRAPE_CONFIG["sources"],
                        categories=DEFAULT_SCRAPE_CONFIG["categories"],
                        location=DEFAULT_SCRAPE_CONFIG["location"],
                        db=self.db,
                        max_leads=DEFAULT_SCRAPE_CONFIG["max_leads"],
                    )
                    summary["new_leads"] = sum(scrape_results.values())
                    logger.info(f"  ✅ Scraped {summary['new_leads']} new leads")
                except Exception as e:
                    logger.error(f"  ❌ Scraping failed: {e}")
                    summary["errors"].append(f"Scraping: {str(e)}")

            # ── Step 2: Classify Leads ────────────────────────────────────────
            if mode in ("full", "scrape_only"):
                logger.info("Step 2/4: 🏷️ Classifying new leads...")
                await self._classify_new_leads()

            # ── Step 3: WhatsApp Outreach ─────────────────────────────────────
            if mode in ("full", "outreach_only"):
                logger.info("Step 3/4: 📱 Running WhatsApp outreach...")
                try:
                    msg_stats = await self.run_whatsapp_outreach(
                        max_messages=settings.WHATSAPP_DAILY_LIMIT // 4,  # Use 25% of daily limit
                        dry_run=dry_run,
                    )
                    summary["messages_sent"] = msg_stats.get("sent", 0)
                    logger.info(
                        f"  ✅ WhatsApp: {msg_stats.get('sent', 0)} sent, "
                        f"{msg_stats.get('failed', 0)} failed"
                    )
                except Exception as e:
                    logger.error(f"  ❌ WhatsApp outreach failed: {e}")
                    summary["errors"].append(f"WhatsApp: {str(e)}")

            # ── Step 4: Social Media Posts ────────────────────────────────────
            if mode in ("full", "social_only"):
                logger.info("Step 4/4: 📣 Publishing social media post...")
                try:
                    post_count = await self.run_social_posting(
                        platforms=["facebook", "instagram"],
                        dry_run=dry_run,
                    )
                    summary["posts_published"] = post_count
                    logger.info(f"  ✅ Published {post_count} social posts")
                except Exception as e:
                    logger.error(f"  ❌ Social posting failed: {e}")
                    summary["errors"].append(f"Social: {str(e)}")

            # ── Step 5: Retry Failed Messages ─────────────────────────────────
            if not dry_run and mode != "scrape_only":
                await self.whatsapp.retry_failed_messages(self.db)

            # ── Done ──────────────────────────────────────────────────────────
            self._last_run_at = datetime.now()
            self._last_run_status = "success" if not summary["errors"] else "partial"
            summary["completed_at"] = self._last_run_at.isoformat()
            summary["duration_seconds"] = (
                self._last_run_at - started_at
            ).total_seconds()

            logger.info(
                f"🎉 Bot cycle complete! "
                f"leads={summary['new_leads']} "
                f"messages={summary['messages_sent']} "
                f"posts={summary['posts_published']}"
            )

            await self.db.log_activity(
                event_type="bot_cycle_complete",
                level="success",
                message="Bot cycle completed successfully",
                module="scheduler",
                details=summary,
            )

            # Send summary notification
            await self.notifier.send_summary(summary)

        except Exception as e:
            self._last_run_status = "error"
            logger.error(f"❌ Bot cycle failed: {e}")
            summary["error"] = str(e)
            await self.db.log_activity(
                event_type="bot_cycle_error",
                level="error",
                message=f"Bot cycle failed: {str(e)}",
                module="scheduler",
                details=summary,
            )
            await self.notifier.send_alert(f"Bot cycle failed: {str(e)}")

        return summary

    # ── Individual Task Runners ───────────────────────────────────────────────

    async def _classify_new_leads(self) -> int:
        """Classify all unclassified new leads using AI."""
        try:
            leads = await self.db.get_leads(status="new", limit=100)
            classified = 0

            for lead_data in leads:
                if lead_data.get("quality_score") is not None:
                    continue  # Already classified

                classification = await self.ai.classify_lead(
                    lead_id=str(lead_data["id"]),
                    name=lead_data.get("name", ""),
                    category=lead_data.get("category", ""),
                    location=lead_data.get("location", ""),
                    phone=lead_data.get("phone", ""),
                    rating=lead_data.get("rating"),
                    review_count=lead_data.get("review_count"),
                    source=lead_data.get("source", "unknown"),
                )

                if classification:
                    await self.db.update_lead_status(
                        lead_data["id"],
                        status="new" if classification.priority != "skip" else "unsubscribed",
                        quality_score=classification.quality_score,
                        priority=classification.priority,
                        category=classification.category,
                    )
                    classified += 1

                # Small delay to avoid AI rate limits
                await asyncio.sleep(0.5)

            logger.info(f"🏷️ Classified {classified} leads")
            return classified

        except Exception as e:
            logger.error(f"❌ Lead classification error: {e}")
            return 0

    async def run_whatsapp_outreach(
        self,
        lead_ids: Optional[List[str]] = None,
        max_messages: int = 20,
        dry_run: bool = False,
    ) -> Dict:
        """
        Run WhatsApp outreach campaign.
        Targets high-priority new leads first.
        """
        # Get leads to contact
        if lead_ids:
            # Specific leads requested
            all_leads = await self.db.get_leads(limit=200, has_phone=True)
            leads = [l for l in all_leads if str(l.get("id")) in lead_ids]
        else:
            # Auto-select: high priority first, then medium
            high = await self.db.get_leads(status="new", limit=max_messages, has_phone=True)
            leads = sorted(
                [l for l in high if l.get("phone")],
                key=lambda x: (
                    {"high": 0, "medium": 1, "low": 2, None: 3}.get(x.get("priority"), 3)
                ),
            )

        leads = leads[:max_messages]

        if not leads:
            logger.info("📭 No leads to contact right now")
            return {"sent": 0, "failed": 0, "skipped": 0}

        if dry_run:
            logger.info(f"🧪 DRY RUN: Would send {len(leads)} messages")
            return {"sent": 0, "failed": 0, "skipped": len(leads), "dry_run": True}

        return await self.whatsapp.send_bulk_outreach(
            leads=leads,
            ai_engine=self.ai,
            db=self.db,
            max_messages=max_messages,
        )

    async def run_social_posting(
        self,
        platforms: Optional[List[str]] = None,
        topic: Optional[str] = None,
        post_type: str = "engagement",
        dry_run: bool = False,
    ) -> int:
        """
        Generate and publish one social media post.
        Rotates topics to keep content fresh.
        """
        if platforms is None:
            platforms = ["facebook", "instagram"]

        # Rotate topic based on day of week
        if not topic:
            day_index = datetime.now().weekday()
            topic = DAILY_POST_TOPICS[day_index % len(DAILY_POST_TOPICS)]

        platform_str = " and ".join(p.capitalize() for p in platforms)

        # Generate post content
        post = await self.ai.generate_social_post(
            post_type=post_type,
            platforms=platform_str,
            topic=topic,
        )

        if not post:
            logger.error("❌ Failed to generate social post content")
            return 0

        if dry_run:
            logger.info(f"🧪 DRY RUN: Generated post - {post.caption[:80]}...")
            return 0

        # Publish to platforms
        record = await self.social.publish_post(
            post=post,
            platforms=platforms,
            db=self.db,
            image_url=None,  # Extend: add image generation here
        )

        return 1 if record.status == "published" else 0

    async def run_email_outreach(
        self,
        lead_ids: Optional[List[str]] = None,
        max_emails: int = 10,
        dry_run: bool = False,
    ) -> Dict:
        """Run cold email outreach for leads that have email addresses."""
        if lead_ids:
            all_leads = await self.db.get_leads(limit=200)
            leads = [l for l in all_leads if str(l.get("id")) in lead_ids and l.get("email")]
        else:
            new_leads = await self.db.get_leads(status="new", limit=max_emails)
            leads = sorted(
                [l for l in new_leads if l.get("email")],
                key=lambda x: (
                    {"high": 0, "medium": 1, "low": 2, None: 3}.get(x.get("priority"), 3)
                ),
            )

        leads = leads[:max_emails]

        if not leads:
            logger.info("No leads with email to contact right now")
            return {"sent": 0, "failed": 0, "skipped": 0}

        return await self.email.send_bulk_outreach(
            leads=leads,
            ai_engine=self.ai,
            db=self.db,
            max_emails=max_emails,
            dry_run=dry_run,
        )

    async def send_email_drafts(
        self,
        email_ids: List[str],
        delay_seconds: Optional[int] = None,
    ) -> Dict:
        """Send previously generated email drafts by id."""
        drafts = await self.db.get_email_messages_by_ids(email_ids)
        if not drafts:
            logger.info("No matching email drafts found")
            return {"sent": 0, "failed": 0, "skipped": 0}

        return await self.email.send_saved_drafts(drafts, self.db, delay_seconds=delay_seconds)

    # ── Status ────────────────────────────────────────────────────────────────

    async def get_status(self) -> BotStatus:
        """Return current bot statistics."""
        lead_counts = await self.db.get_lead_counts()
        sent_today = await self.db.get_messages_sent_today()
        emails_today = await self.db.get_emails_sent_today()
        posts_today = await self.db.get_posts_published_today()

        return BotStatus(
            last_run_at=self._last_run_at,
            last_run_status=self._last_run_status,
            total_leads=lead_counts.get("total", 0),
            new_leads=lead_counts.get("new", 0),
            contacted_leads=lead_counts.get("contacted", 0),
            replied_leads=lead_counts.get("replied", 0),
            messages_sent_today=sent_today,
            emails_sent_today=emails_today,
            posts_published_today=posts_today,
            daily_message_limit=settings.WHATSAPP_DAILY_LIMIT,
            daily_email_limit=settings.EMAIL_DAILY_LIMIT,
            daily_post_limit=settings.META_DAILY_POST_LIMIT,
        )
