"""
ServiPal Bot - Supabase Database Client
========================================
Handles all database operations: CRUD for leads, messages,
social posts, and activity logs.
Uses supabase-py async client.
"""

import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any

import httpx
import re
from urllib.parse import urlparse
from supabase import create_client, Client

from app.config.config import settings
from app.schemas.schemas import Lead, Message, EmailRecord, SocialPostRecord, ActivityLog

logger = logging.getLogger("servipal_bot.database")


class SupabaseClient:
    """
    Async-compatible wrapper around Supabase client.
    Handles all database operations for the marketing bot.
    """

    def __init__(self):
        self.client: Optional[Client] = None
        self.enabled = settings.supabase_configured

        if not self.enabled:
            logger.warning("Supabase is not fully configured; database features are disabled")
            return

        try:
            self.client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_KEY,
            )
            logger.info("Supabase client initialized")
        except Exception as e:
            self.enabled = False
            logger.error(f"Failed to initialize Supabase client: {e}")

    def _is_ready(self) -> bool:
        return self.enabled and self.client is not None

    @staticmethod
    def _canonicalize_website(website: Optional[str]) -> Optional[str]:
        """Normalize websites so equality checks work (scheme, www, trailing slash)."""
        if not website:
            return None
        raw = website.strip()
        if not raw:
            return None

        # Ensure urlparse recognizes the host.
        candidate = raw if re.match(r"^https?://", raw, re.IGNORECASE) else f"https://{raw}"
        parsed = urlparse(candidate)
        if not parsed.netloc:
            return raw.rstrip("/")

        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]

        path = (parsed.path or "").rstrip("/")
        return f"https://{netloc}{path}"

    # ── Lead Operations ───────────────────────────────────────────────────────

    async def upsert_lead(self, lead: Lead) -> Optional[Dict]:
        """
        Insert or update a lead. Uses phone as unique key to avoid duplicates.
        Returns the saved lead record.
        """
        if not self._is_ready():
            logger.warning("Skipping lead upsert because Supabase is not configured")
            return None
        try:
            data = lead.model_dump(mode="json", exclude_none=True, exclude={"id"})
            if "website" in data:
                data["website"] = self._canonicalize_website(data.get("website"))
            # data["updated_at"] = datetime.now().isoformat()

            if lead.phone:
                result = (
                    self.client.table("leads")
                    .upsert(data, on_conflict="phone")
                    .execute()
                )
            else:
                result = self.client.table("leads").insert(data).execute()

            if result.data:
                logger.info(f"Lead saved: {lead.name} ({lead.phone})")
                return result.data[0]
            return None

        except Exception as e:
            logger.error(f"Failed to upsert lead {lead.name}: {e}")
            await self.log_activity(
                event_type="db_error",
                level="error",
                message=f"Failed to upsert lead: {str(e)}",
                module="database",
            )
            return None

    async def insert_lead_if_new(self, lead: Lead) -> Optional[Dict]:
        """
        Insert a lead only if it is new (do not update existing leads).

        Dedupe rules:
        - If phone is present and already exists, skip.
        - If phone is absent, use (name + optional location + optional website) identity check.
        """
        if not self._is_ready():
            logger.warning("Skipping lead insert because Supabase is not configured")
            return None

        # Canonicalize website for both dedupe and storage.
        lead = lead.model_copy(update={"website": self._canonicalize_website(lead.website)})

        try:
            if lead.phone and await self.lead_exists(lead.phone):
                return None
            if (
                not lead.phone
                and await self.lead_identity_exists(
                    name=lead.name,
                    location=lead.location,
                    website=lead.website,
                )
            ):
                return None

            data = lead.model_dump(mode="json", exclude_none=True, exclude={"id"})
            # data["updated_at"] = datetime.now().isoformat()
            result = self.client.table("leads").insert(data).execute()

            if result.data:
                logger.info(f"New lead inserted: {lead.name} ({lead.phone})")
                return result.data[0]
            return None

        except Exception as e:
            # Common case: a unique constraint (phone) was hit in a race. Treat as "skipped".
            msg = str(e).lower()
            if "duplicate key" in msg or "unique constraint" in msg or "23505" in msg:
                return None
            logger.error(f"Failed to insert lead {lead.name}: {e}")
            await self.log_activity(
                event_type="db_error",
                level="error",
                message=f"Failed to insert lead: {str(e)}",
                module="database",
            )
            return None

    async def get_leads(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        has_phone: bool = False,
    ) -> List[Dict]:
        """
        Retrieve leads with optional status filter.
        By default returns all leads. Set has_phone=True for WhatsApp-ready leads only.
        """
        if not self._is_ready():
            return []
        try:
            query = self.client.table("leads").select("*")

            if status:
                query = query.eq("status", status)
            if has_phone:
                query = query.not_.is_("phone", "null")

            query = query.order("created_at", desc=False).limit(limit)
            result = query.execute()
            return result.data or []

        except Exception as e:
            logger.error(f"Failed to get leads: {e}")
            return []

    async def update_lead_status(self, lead_id: str, status: str, **kwargs) -> bool:
        """Update lead status and optional extra fields."""
        if not self._is_ready():
            return False
        try:
            data = {"status": status,
            #  "updated_at": datetime.now().isoformat()
             }
            data.update(kwargs)

            self.client.table("leads").update(data).eq("id", lead_id).execute()
            return True

        except Exception as e:
            logger.error(f"Failed to update lead {lead_id}: {e}")
            return False

    async def lead_exists(self, phone: str) -> bool:
        """Check if a lead with this phone already exists."""
        if not self._is_ready():
            return False
        try:
            result = self.client.table("leads").select("id").eq("phone", phone).execute()
            return bool(result.data)
        except Exception:
            return False

    async def get_lead_by_phone(self, phone: str) -> Optional[Dict]:
        """Fetch a lead by phone (returns full record if found)."""
        if not self._is_ready():
            return None
        try:
            result = (
                self.client.table("leads")
                .select("*")
                .eq("phone", phone)
                .limit(1)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception:
            return None

    async def lead_identity_exists(
        self,
        name: str,
        location: Optional[str] = None,
        website: Optional[str] = None,
    ) -> bool:
        """Check for an existing lead using business identity when phone is unavailable."""
        if not self._is_ready():
            return False

        try:
            website = self._canonicalize_website(website)
            query = self.client.table("leads").select("id").eq("name", name)
            if location:
                query = query.eq("location", location)
            if website:
                query = query.eq("website", website)

            result = query.limit(1).execute()
            return bool(result.data)
        except Exception:
            return False

    async def get_lead_by_identity(
        self,
        name: str,
        location: Optional[str] = None,
        website: Optional[str] = None,
    ) -> Optional[Dict]:
        """Fetch a lead by identity when phone is not available."""
        if not self._is_ready():
            return None
        try:
            website = self._canonicalize_website(website)
            query = self.client.table("leads").select("*").eq("name", name)
            if location:
                query = query.eq("location", location)
            if website:
                query = query.eq("website", website)
            result = query.limit(1).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None

    async def update_lead(self, lead_id: str, **fields: Any) -> bool:
        """Update arbitrary lead fields (email, phone, website, etc.)."""
        if not self._is_ready():
            return False
        if not lead_id:
            return False

        try:
            data = dict(fields)
            if "website" in data:
                data["website"] = self._canonicalize_website(data.get("website"))
            # data["updated_at"] = datetime.now().isoformat()
            self.client.table("leads").update(data).eq("id", lead_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to update lead {lead_id}: {e}")
            return False

    async def get_leads_missing_email_with_website(self, limit: int = 50) -> List[Dict]:
        """Leads that have a website but no email (for enrichment jobs)."""
        if not self._is_ready():
            return []
        try:
            result = (
                self.client.table("leads")
                .select("*")
                .is_("email", "null")
                .not_.is_("website", "null")
                .order("created_at", desc=False)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to fetch leads missing email: {e}")
            return []

    # ── Message Operations ────────────────────────────────────────────────────

    async def save_message(self, message: Message) -> Optional[Dict]:
        """Save a WhatsApp message record to Supabase."""
        if not self._is_ready():
            return None
        try:
            data = message.model_dump(mode="json", exclude_none=True, exclude={"id"})
            result = self.client.table("messages").insert(data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f" Failed to save message: {e}")
            return None

    async def update_message_status(
        self,
        message_id: str,
        status: str,
        wa_message_id: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """Update message delivery status."""
        if not self._is_ready():
            return False
        try:
            data = {"status": status,
            #  "updated_at": datetime.now().isoformat()
             }
            if wa_message_id:
                data["wa_message_id"] = wa_message_id
            data.update(kwargs)

            self.client.table("messages").update(data).eq("id", message_id).execute()
            return True
        except Exception as e:
            logger.error(f" Failed to update message {message_id}: {e}")
            return False

    async def get_messages_sent_today(self) -> int:
        """Count messages sent today for rate limit tracking."""
        if not self._is_ready():
            return 0
        try:
            today = date.today().isoformat()
            result = (
                self.client.table("messages")
                .select("id", count="exact")
                .gte("created_at", f"{today}T00:00:00")
                .in_("status", ["sent", "delivered", "read"])
                .execute()
            )
            return result.count or 0
        except Exception:
            return 0

    async def get_failed_messages(self, max_retries: int = 3) -> List[Dict]:
        """Get failed messages eligible for retry."""
        if not self._is_ready():
            return []
        try:
            result = (
                self.client.table("messages")
                .select("*")
                .eq("status", "failed")
                .lt("retry_count", max_retries)
                .execute()
            )
            return result.data or []
        except Exception:
            return []

    async def save_email(self, email_record: EmailRecord) -> Optional[Dict]:
        """Save a cold email record to Supabase."""
        if not self._is_ready():
            return None
        try:
            # Use JSON mode so values like datetime get serialized for Supabase/httpx.
            data = email_record.model_dump(mode="json", exclude_none=True, exclude={"id"})
            result = self.client.table("email_messages").insert(data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Failed to save email record: {e}")
            return None

    async def update_email_message(
        self,
        email_id: str,
        updates: Dict[str, Any],
        *,
        require_draft: bool = True,
    ) -> Optional[Dict]:
        """Update an email message record (typically used to edit drafts)."""
        if not self._is_ready() or not email_id or not updates:
            return None

        allowed_fields = {"email", "subject", "body"}
        data: Dict[str, Any] = {
            key: value for key, value in updates.items() if key in allowed_fields and value is not None
        }
        if not data:
            return None

        try:
            query = self.client.table("email_messages").update(data).eq("id", email_id)
            if require_draft:
                query = query.eq("status", "draft")
            result = query.execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Failed to update email message {email_id}: {e}")
            return None

    async def update_email_status(
        self,
        email_id: str,
        status: str,
        provider_message_id: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """Update email delivery status."""
        if not self._is_ready():
            return False
        try:
            data = {"status": status,
            #  "updated_at": datetime.now().isoformat()
             }
            if provider_message_id:
                data["provider_message_id"] = provider_message_id
            data.update(kwargs)
            self.client.table("email_messages").update(data).eq("id", email_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to update email {email_id}: {e}")
            return False

    async def get_emails_sent_today(self) -> int:
        """Count emails sent today for rate limit tracking."""
        if not self._is_ready():
            return 0
        try:
            today = date.today().isoformat()
            result = (
                self.client.table("email_messages")
                .select("id", count="exact")
                .gte("created_at", f"{today}T00:00:00")
                .in_("status", ["sent", "delivered", "replied"])
                .execute()
            )
            return result.count or 0
        except Exception:
            return 0

    async def get_email_messages(self, limit: int = 50) -> List[Dict]:
        """Retrieve recent outbound email records."""
        if not self._is_ready():
            return []
        try:
            result = (
                self.client.table("email_messages")
                .select("*")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception:
            return []

    async def get_email_messages_by_ids(self, email_ids: List[str]) -> List[Dict]:
        """Retrieve specific email message records by id."""
        if not self._is_ready() or not email_ids:
            return []
        try:
            result = (
                self.client.table("email_messages")
                .select("*")
                .in_("id", email_ids)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get email messages by ids: {e}")
            return []

    # ── Social Post Operations ────────────────────────────────────────────────

    async def save_social_post(self, post: SocialPostRecord) -> Optional[Dict]:
        """Save a social post record."""
        if not self._is_ready():
            return None
        try:
            data = post.model_dump(mode="json", exclude_none=True, exclude={"id"})
            result = self.client.table("social_posts").insert(data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Failed to save social post: {e}")
            return None

    async def update_social_post(self, post_id: str, **kwargs) -> bool:
        """Update social post record (e.g., after publishing)."""
        if not self._is_ready():
            return False
        try:
            # data = {"updated_at": datetime.now().isoformat()}
            data.update(kwargs)
            self.client.table("social_posts").update(data).eq("id", post_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to update social post {post_id}: {e}")
            return False

    async def get_social_posts(self, limit: int = 20) -> List[Dict]:
        """Retrieve recent social post records."""
        if not self._is_ready():
            return []
        try:
            result = (
                self.client.table("social_posts")
                .select("*")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception:
            return []

    async def get_posts_published_today(self) -> int:
        """Count posts published today for rate limit tracking."""
        if not self._is_ready():
            return 0
        try:
            today = date.today().isoformat()
            result = (
                self.client.table("social_posts")
                .select("id", count="exact")
                .gte("published_at", f"{today}T00:00:00")
                .eq("status", "published")
                .execute()
            )
            return result.count or 0
        except Exception:
            return 0

    # ── Logging ───────────────────────────────────────────────────────────────

    async def log_activity(
        self,
        event_type: str,
        level: str,
        message: str,
        module: str,
        details: Optional[Dict] = None,
    ) -> None:
        """Log bot activity to Supabase logs table."""
        if not self._is_ready():
            return
        try:
            data = {
                "event_type": event_type,
                "level": level,
                "message": message,
                "module": module,
                "details": details or {},
                "created_at": datetime.now().isoformat(),
            }
            self.client.table("logs").insert(data).execute()
        except Exception as e:
            # Don't raise - logging failures should never crash the bot
            logger.warning(f"⚠️ Failed to write activity log: {e}")

    async def get_logs(
        self,
        level: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Retrieve activity logs."""
        if not self._is_ready():
            return []
        try:
            query = self.client.table("logs").select("*")
            if level:
                query = query.eq("level", level)
            result = query.order("created_at", desc=True).limit(limit).execute()
            return result.data or []
        except Exception:
            return []

    # ── Stats ─────────────────────────────────────────────────────────────────

    async def get_lead_counts(self) -> Dict[str, int]:
        """Get lead counts by status for dashboard."""
        counts = {"total": 0, "new": 0, "contacted": 0, "replied": 0, "converted": 0}
        if not self._is_ready():
            return counts
        try:
            for status in ["new", "contacted", "replied", "converted"]:
                result = (
                    self.client.table("leads")
                    .select("id", count="exact")
                    .eq("status", status)
                    .execute()
                )
                counts[status] = result.count or 0
                counts["total"] += counts[status]
        except Exception as e:
            logger.error(f"Failed to get lead counts: {e}")
        return counts

    async def healthcheck(self) -> Dict[str, Any]:
        """Return Supabase readiness information without exposing secrets."""
        if not self.enabled:
            return {"configured": False, "reachable": False}
        if not self.client:
            return {"configured": True, "reachable": False}

        try:
            result = self.client.table("logs").select("id", count="exact").limit(1).execute()
            return {"configured": True, "reachable": True, "log_count_checked": result.count or 0}
        except Exception as e:
            logger.warning(f"Supabase healthcheck failed: {e}")
            return {"configured": True, "reachable": False, "error": str(e)[:200]}
