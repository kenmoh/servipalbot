"""
ServiPal Bot - Resend Email Client
==================================
Handles outbound cold email via Resend with basic throttling and delivery logging.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Tuple

import httpx

from app.config.config import settings
from app.schemas.schemas import Lead, EmailRecord
from app.db.database import SupabaseClient

logger = logging.getLogger("servipal_bot.email")


class EmailClient:
    """Resend email client for cold outreach."""

    def __init__(self):
        self.enabled = settings.resend_configured
        self.base_url = f"{settings.RESEND_BASE_URL}/emails"
        self.daily_limit = settings.EMAIL_DAILY_LIMIT
        self.delay_seconds = settings.EMAIL_DELAY_SECONDS
        self.client = httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT)
        self.headers = {
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
        }

        if self.enabled:
            logger.info("Email client initialized")
        else:
            logger.warning("Email client is not fully configured; send operations will be skipped")

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        lead_id: str,
        db: SupabaseClient,
        email_id: str | None = None,
    ) -> Tuple[bool, str]:
        """Send one outbound email and persist its status."""
        if not self.enabled:
            logger.warning("Email send skipped because Resend is not configured")
            return False, ""

        if not email_id:
            email_record = EmailRecord(
                lead_id=lead_id,
                email=to_email,
                subject=subject,
                body=body,
                status="pending",
                created_at=datetime.utcnow(),
            )
            saved = await db.save_email(email_record)
            email_id = saved["id"] if saved else None
        else:
            await db.update_email_status(email_id, status="pending")

        payload = {
            "from": f"{settings.RESEND_FROM_NAME} <{settings.RESEND_FROM_ADDRESS}>",
            "to": [to_email],
            "subject": subject,
            "text": body,
        }
        if settings.RESEND_REPLY_TO:
            payload["reply_to"] = settings.RESEND_REPLY_TO

        try:
            response = await self.client.post(self.base_url, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            resend_id = data.get("id", "")

            if email_id:
                await db.update_email_status(
                    email_id,
                    status="sent",
                    provider_message_id=resend_id,
                    sent_at=datetime.utcnow().isoformat(),
                )

            await db.log_activity(
                event_type="email_sent",
                level="success",
                message=f"Email sent to {to_email}",
                module="email",
                details={"lead_id": lead_id, "resend_id": resend_id},
            )
            return True, resend_id

        except Exception as e:
            if email_id:
                await db.update_email_status(
                    email_id,
                    status="failed",
                    error_message=str(e)[:300],
                    retry_count=settings.MAX_RETRIES,
                )

            await db.log_activity(
                event_type="email_failed",
                level="error",
                message=f"Email failed for {to_email}",
                module="email",
                details={"lead_id": lead_id, "error": str(e)[:300]},
            )
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False, ""

    async def send_bulk_outreach(
        self,
        leads: list,
        ai_engine,
        db: SupabaseClient,
        max_emails: int = 10,
        dry_run: bool = False,
    ) -> Dict[str, int]:
        """Generate and save draft cold emails for leads with valid email addresses."""
        stats = {"attempted": 0, "drafted": 0, "failed": 0, "skipped": 0}

        for lead_data in leads[:max_emails]:
            lead = Lead(**lead_data) if isinstance(lead_data, dict) else lead_data
            if isinstance(lead_data, dict):
                lead.id = lead_data.get("id")

            if not lead.email:
                stats["skipped"] += 1
                continue

            email_model = await ai_engine.generate_cold_email(
                vendor_name=lead.name,
                category=lead.category,
                location=lead.location or "your area",
            )
            if not email_model:
                stats["failed"] += 1
                continue

            stats["attempted"] += 1
            if dry_run:
                stats["skipped"] += 1
            else:
                saved = await db.save_email(
                    EmailRecord(
                        lead_id=str(lead.id),
                        email=lead.email,
                        subject=email_model.subject,
                        body=email_model.full_email,
                        status="draft",
                        created_at=datetime.utcnow(),
                    )
                )
                if saved:
                    stats["drafted"] += 1
                else:
                    stats["failed"] += 1

            await asyncio.sleep(1)

        return stats

    async def send_saved_drafts(
        self,
        email_records: list[dict],
        db: SupabaseClient,
    ) -> Dict[str, int]:
        """Send previously drafted email records with throttling."""
        stats = {"attempted": 0, "sent": 0, "failed": 0, "skipped": 0}

        sent_today = await db.get_emails_sent_today()
        remaining = max(self.daily_limit - sent_today, 0)
        if remaining <= 0:
            logger.warning(f"Daily email limit reached ({self.daily_limit}). Skipping.")
            return stats

        for record in email_records[:remaining]:
            if record.get("status") not in ("draft", "failed"):
                stats["skipped"] += 1
                continue

            stats["attempted"] += 1
            success, _ = await self.send_email(
                to_email=record["email"],
                subject=record["subject"],
                body=record["body"],
                lead_id=record["lead_id"],
                db=db,
                email_id=record["id"],
            )
            if success:
                stats["sent"] += 1
            else:
                stats["failed"] += 1

            await asyncio.sleep(self.delay_seconds)

        return stats

    async def healthcheck(self) -> dict:
        return {
            "configured": self.enabled,
            "from_address_present": bool(settings.RESEND_FROM_ADDRESS.strip()),
        }

    async def close(self):
        await self.client.aclose()
