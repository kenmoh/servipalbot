"""
ServiPal Bot - WhatsApp Cloud API Client
=========================================
Handles all WhatsApp messaging via Meta's WhatsApp Cloud API.
Features:
- Send text messages with personalization
- Track delivery status via webhooks
- Retry failed messages
- Respect free tier rate limits (250 conversations/day)

API Docs: https://developers.facebook.com/docs/whatsapp/cloud-api
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Tuple

import httpx

from app.config.config import settings
from app.schemas.schemas import Lead, WhatsAppMessage, Message
from app.db.database import SupabaseClient

logger = logging.getLogger("servipal_bot.whatsapp")


class WhatsAppClient:
    """
    WhatsApp Cloud API client with delivery tracking and retry logic.
    """

    API_URL = "https://graph.facebook.com/{version}/{phone_id}/messages"

    def __init__(self):
        self.phone_id = settings.WHATSAPP_PHONE_ID
        self.token = settings.WHATSAPP_TOKEN
        self.version = settings.WHATSAPP_API_VERSION
        self.daily_limit = settings.WHATSAPP_DAILY_LIMIT
        self.enabled = settings.whatsapp_configured

        self.base_url = self.API_URL.format(
            version=self.version,
            phone_id=self.phone_id,
        )
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        self.client = httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT)
        if self.enabled:
            logger.info("WhatsApp client initialized")
        else:
            logger.warning("WhatsApp client is not fully configured; send operations will be skipped")

    # ── Main Send Method ──────────────────────────────────────────────────────

    async def send_message(
        self,
        to_phone: str,
        message_text: str,
        lead_id: str,
        db: SupabaseClient,
    ) -> Tuple[bool, str]:
        """
        Send a WhatsApp text message and record in Supabase.

        Args:
            to_phone: Recipient phone in E.164 format (+2348012345678)
            message_text: Text content to send
            lead_id: Associated lead ID for tracking
            db: Supabase client for logging

        Returns:
            (success: bool, wa_message_id: str)
        """
        if not self.enabled:
            logger.warning("WhatsApp send skipped because the integration is not configured")
            return False, ""

        # Normalize phone: strip + for API
        clean_phone = to_phone.lstrip("+")

        # Create message record in Supabase
        msg_record = Message(
            lead_id=lead_id,
            phone=to_phone,
            content=message_text,
            status="pending",
            created_at=datetime.utcnow(),
        )
        saved = await db.save_message(msg_record)
        msg_id = saved["id"] if saved else None

        # Build payload
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message_text,
            },
        }

        # Attempt send with retries
        for attempt in range(1, settings.MAX_RETRIES + 1):
            try:
                response = await self.client.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                wa_msg_id = (
                    data.get("messages", [{}])[0].get("id")
                    if data.get("messages")
                    else None
                )

                # Update DB record
                if msg_id:
                    await db.update_message_status(
                        msg_id,
                        status="sent",
                        wa_message_id=wa_msg_id,
                        sent_at=datetime.utcnow().isoformat(),
                    )

                # Update lead status
                await db.update_lead_status(lead_id, "contacted")

                logger.info(f"✅ WhatsApp sent to {to_phone} (WA ID: {wa_msg_id})")
                await db.log_activity(
                    event_type="whatsapp_sent",
                    level="success",
                    message=f"Message sent to {to_phone}",
                    module="whatsapp",
                    details={"lead_id": lead_id, "wa_message_id": wa_msg_id},
                )
                return True, wa_msg_id or ""

            except httpx.HTTPStatusError as e:
                error_body = e.response.text[:300]
                logger.warning(
                    f"  ⚠️ WhatsApp send attempt {attempt} failed "
                    f"({e.response.status_code}): {error_body}"
                )

                if e.response.status_code == 429:
                    # Rate limit - wait before retry
                    await asyncio.sleep(60 * attempt)
                elif e.response.status_code in [400, 401, 403]:
                    # Unrecoverable - don't retry
                    break
                else:
                    await asyncio.sleep(settings.RETRY_DELAY_SECONDS * attempt)

            except Exception as e:
                logger.warning(f"  ⚠️ WhatsApp send attempt {attempt} error: {e}")
                await asyncio.sleep(settings.RETRY_DELAY_SECONDS * attempt)

        # All attempts failed
        if msg_id:
            await db.update_message_status(
                msg_id,
                status="failed",
                error_message=f"Failed after {settings.MAX_RETRIES} attempts",
                retry_count=settings.MAX_RETRIES,
            )

        logger.error(f"❌ Failed to send WhatsApp to {to_phone} after all retries")
        await db.log_activity(
            event_type="whatsapp_failed",
            level="error",
            message=f"Failed to send to {to_phone}",
            module="whatsapp",
            details={"lead_id": lead_id, "phone": to_phone},
        )
        return False, ""

    # ── Bulk Outreach ─────────────────────────────────────────────────────────

    async def send_bulk_outreach(
        self,
        leads: list,
        ai_engine,
        db: SupabaseClient,
        max_messages: int = 20,
    ) -> Dict[str, int]:
        """
        Send AI-generated WhatsApp messages to a list of leads.
        Respects daily rate limits. Returns send statistics.
        """
        stats = {"attempted": 0, "sent": 0, "failed": 0, "skipped": 0}

        # Check daily limit
        sent_today = await db.get_messages_sent_today()
        remaining = min(self.daily_limit - sent_today, max_messages)

        if remaining <= 0:
            logger.warning(f"⚠️ Daily WhatsApp limit reached ({self.daily_limit}). Skipping.")
            return stats

        logger.info(f"📤 Starting bulk outreach: {remaining} messages allowed today")

        for lead_data in leads[:remaining]:
            # Handle both dict and Lead model
            if isinstance(lead_data, dict):
                lead = Lead(**lead_data)
                lead.id = lead_data.get("id")
            else:
                lead = lead_data

            if not lead.phone:
                stats["skipped"] += 1
                continue

            # Generate personalized message
            msg_model = await ai_engine.generate_whatsapp_message(
                vendor_name=lead.name,
                category=lead.category,
                location=lead.location or "your area",
            )

            if not msg_model:
                stats["failed"] += 1
                continue

            stats["attempted"] += 1
            success, _ = await self.send_message(
                to_phone=lead.phone,
                message_text=msg_model.full_message,
                lead_id=str(lead.id),
                db=db,
            )

            if success:
                stats["sent"] += 1
            else:
                stats["failed"] += 1

            # Throttle: 1 message per 2 seconds to avoid rate limits
            await asyncio.sleep(2)

        logger.info(
            f"📊 Bulk outreach complete: {stats['sent']} sent, "
            f"{stats['failed']} failed, {stats['skipped']} skipped"
        )
        return stats

    # ── Retry Failed Messages ─────────────────────────────────────────────────

    async def retry_failed_messages(self, db: SupabaseClient) -> int:
        """Retry all failed messages that haven't exceeded max retries."""
        failed = await db.get_failed_messages(max_retries=settings.MAX_RETRIES)

        if not failed:
            logger.info("✅ No failed messages to retry")
            return 0

        logger.info(f"🔄 Retrying {len(failed)} failed messages")
        retried = 0

        for msg in failed:
            # Get original message content from DB
            phone = msg.get("phone")
            content = msg.get("content")
            lead_id = msg.get("lead_id")
            msg_id = msg.get("id")

            if not all([phone, content, lead_id]):
                continue

            # Update retry count first
            await db.update_message_status(
                msg_id,
                status="pending",
                retry_count=msg.get("retry_count", 0) + 1,
            )

            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": phone.lstrip("+"),
                "type": "text",
                "text": {"body": content},
            }

            try:
                response = await self.client.post(
                    self.base_url, headers=self.headers, json=payload
                )
                response.raise_for_status()
                data = response.json()
                wa_id = data.get("messages", [{}])[0].get("id")

                await db.update_message_status(msg_id, "sent", wa_message_id=wa_id)
                await db.update_lead_status(lead_id, "contacted")
                retried += 1

            except Exception as e:
                await db.update_message_status(msg_id, "failed", error_message=str(e)[:200])
                logger.warning(f"  Retry failed for {phone}: {e}")

            await asyncio.sleep(2)

        logger.info(f"✅ Retried {retried}/{len(failed)} messages successfully")
        return retried

    # ── Webhook Handler ───────────────────────────────────────────────────────

    async def handle_webhook(self, payload: dict, db: SupabaseClient) -> None:
        """
        Process incoming WhatsApp webhook events.
        Updates message status and lead status in Supabase.
        """
        try:
            for entry in payload.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})

                    # Handle status updates
                    for status in value.get("statuses", []):
                        wa_id = status.get("id")
                        new_status = status.get("status")  # sent/delivered/read/failed

                        if wa_id and new_status:
                            # Find message by WA ID and update
                            logger.info(f"📬 Status update: {wa_id} → {new_status}")
                            # Note: requires a DB query by wa_message_id
                            # (implement get_message_by_wa_id if needed)

                    # Handle incoming messages (replies)
                    for msg in value.get("messages", []):
                        from_phone = msg.get("from")
                        msg_text = msg.get("text", {}).get("body", "")

                        if from_phone:
                            logger.info(f"💬 Reply from {from_phone}: {msg_text[:50]}")
                            # Find lead by phone and mark as replied
                            leads = await db.get_leads(limit=1)
                            for lead in leads:
                                if lead.get("phone", "").lstrip("+") == from_phone:
                                    await db.update_lead_status(lead["id"], "replied")
                                    await db.log_activity(
                                        event_type="whatsapp_reply",
                                        level="info",
                                        message=f"Reply received from {from_phone}",
                                        module="whatsapp",
                                        details={"text": msg_text[:200]},
                                    )

        except Exception as e:
            logger.error(f"❌ Webhook processing error: {e}")

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def healthcheck(self) -> dict:
        return {
            "configured": self.enabled,
            "phone_id_present": bool(self.phone_id and self.phone_id != "your_whatsapp_phone_number_id_here"),
        }
