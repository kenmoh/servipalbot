"""
ServiPal Bot - Pydantic Models & Schemas
=========================================
Structured data models for:
- AI-generated outputs (messages, social posts, lead classification)
- API request/response schemas
- Database record models
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
import re


# ══════════════════════════════════════════════════════════════════════════════
# AI OUTPUT MODELS (Validated structured outputs from LLM)
# ══════════════════════════════════════════════════════════════════════════════

class WhatsAppMessage(BaseModel):
    """
    AI-generated WhatsApp outreach message.
    Validated for length, tone, and required placeholders.
    """
    greeting: str = Field(
        ...,
        description="Personalized greeting using vendor name",
        min_length=5,
        max_length=100,
    )
    body: str = Field(
        ...,
        description="Main message body - value proposition",
        min_length=50,
        max_length=500,
    )
    call_to_action: str = Field(
        ...,
        description="Clear CTA - what should they do next?",
        min_length=10,
        max_length=150,
    )
    full_message: str = Field(
        ...,
        description="Complete assembled message ready to send",
        min_length=80,
        max_length=700,
    )
    language: Literal["en", "fr", "es", "pt", "sw"] = "en"
    tone_score: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Friendliness/persuasion score (0-1)",
    )

    @field_validator("full_message")
    @classmethod
    def no_spam_words(cls, v: str) -> str:
        """Reject messages with spammy language."""
        spam_patterns = [r"\bfree money\b", r"\bguaranteed\b", r"\burgent!!!\b"]
        for pattern in spam_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError(f"Message contains spam-like pattern: {pattern}")
        return v

    @model_validator(mode="after")
    def assemble_full_message(self) -> "WhatsAppMessage":
        """Auto-assemble full_message if not provided."""
        if not self.full_message:
            self.full_message = f"{self.greeting}\n\n{self.body}\n\n{self.call_to_action}"
        return self


class SocialPost(BaseModel):
    """
    AI-generated social media post for Facebook/Instagram.
    """
    caption: str = Field(
        ...,
        description="Main post caption with emojis and hashtags",
        min_length=20,
        max_length=2200,
    )
    hashtags: List[str] = Field(
        default_factory=list,
        description="List of relevant hashtags (without #)",
        max_length=30,
    )
    call_to_action: str = Field(
        ...,
        description="Engagement CTA for the post",
        max_length=200,
    )
    suggested_image_prompt: str = Field(
        ...,
        description="Description for image generation or stock photo search",
        max_length=300,
    )
    post_type: Literal["promotion", "engagement", "educational", "testimonial"] = "engagement"
    best_posting_time: str = Field(
        default="12:00",
        description="Suggested posting time HH:MM",
    )

    @field_validator("hashtags")
    @classmethod
    def clean_hashtags(cls, v: List[str]) -> List[str]:
        """Remove # prefix if accidentally included."""
        return [tag.lstrip("#").strip().lower() for tag in v if tag.strip()]

    def formatted_caption(self) -> str:
        """Return caption with hashtags appended."""
        tags = " ".join(f"#{tag}" for tag in self.hashtags[:20])
        return f"{self.caption}\n\n{tags}" if tags else self.caption


class ColdEmail(BaseModel):
    """AI-generated cold email for business outreach."""
    subject: str = Field(..., min_length=5, max_length=120)
    body: str = Field(..., min_length=60, max_length=1200)
    full_email: str = Field(..., min_length=70, max_length=1400)


class LeadClassification(BaseModel):
    """
    AI classification result for a scraped lead.
    Determines quality, priority, and best outreach strategy.
    """
    lead_id: str
    quality_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Lead quality score (0 = poor, 1 = excellent)",
    )
    priority: Literal["high", "medium", "low", "skip"] = "medium"
    category: str = Field(..., description="Detected business category")
    recommended_channel: Literal["whatsapp", "email", "instagram_dm", "skip"] = "whatsapp"
    reasoning: str = Field(
        ...,
        description="Brief reasoning for classification",
        max_length=300,
    )
    personalization_hints: List[str] = Field(
        default_factory=list,
        description="Key facts to personalize the message",
    )


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE MODELS (Supabase table records)
# ══════════════════════════════════════════════════════════════════════════════

class Lead(BaseModel):
    """Represents a vendor lead in the Supabase leads table."""
    id: Optional[str] = None
    name: str = Field(..., min_length=2, max_length=200)
    category: str = Field(..., description="e.g., restaurant, laundry, marketplace")
    phone: Optional[str] = Field(None, description="Phone number with country code")
    email: Optional[str] = None
    location: Optional[str] = None
    source: Literal["google_maps", "instagram", "marketplace", "manual"] = "manual"
    status: Literal["new", "contacted", "delivered", "replied", "converted", "unsubscribed"] = "new"
    quality_score: Optional[float] = None
    priority: Optional[str] = None
    instagram_handle: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    raw_data: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # Strip spaces/dashes, keep + prefix
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        if not cleaned.startswith("+"):
            cleaned = "+" + cleaned
        return cleaned


class Message(BaseModel):
    """Represents a WhatsApp message record in Supabase."""
    id: Optional[str] = None
    lead_id: str
    phone: str
    content: str = Field(..., min_length=10)
    wa_message_id: Optional[str] = None        # WhatsApp message ID for tracking
    status: Literal["pending", "sent", "delivered", "read", "failed", "replied"] = "pending"
    error_message: Optional[str] = None
    retry_count: int = 0
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    replied_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class EmailRecord(BaseModel):
    """Represents an outbound cold email record in Supabase."""
    id: Optional[str] = None
    lead_id: str
    email: str
    subject: str
    body: str
    status: Literal["draft", "pending", "sent", "delivered", "failed", "replied"] = "draft"
    provider_message_id: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    replied_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class SocialPostRecord(BaseModel):
    """Represents a social media post record in Supabase."""
    id: Optional[str] = None
    platform: Literal["facebook", "instagram", "both"]
    caption: str
    hashtags: Optional[List[str]] = None
    post_type: str = "engagement"
    fb_post_id: Optional[str] = None
    ig_post_id: Optional[str] = None
    status: Literal["draft", "published", "failed"] = "draft"
    likes: int = 0
    comments: int = 0
    reach: int = 0
    error_message: Optional[str] = None
    published_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class ActivityLog(BaseModel):
    """Activity log entry for monitoring bot operations."""
    id: Optional[str] = None
    event_type: str = Field(..., description="e.g., scrape_complete, message_sent")
    level: Literal["info", "warning", "error", "success"] = "info"
    message: str
    details: Optional[dict] = None
    module: str = Field(..., description="Module that generated this log")
    created_at: Optional[datetime] = None


# ══════════════════════════════════════════════════════════════════════════════
# API REQUEST / RESPONSE SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class ScrapeRequest(BaseModel):
    """Request body for /scrape/leads endpoint."""
    sources: List[Literal["google_maps", "instagram", "marketplace"]] = ["google_maps"]
    categories: List[str] = Field(
        default=["restaurant", "laundry", "delivery", "grocery"],
        description="Business categories to scrape",
    )
    location: str = Field(
        default="Lagos, Nigeria",
        description="Target city/location for scraping",
    )
    max_leads: int = Field(default=50, ge=1, le=200)


class OutreachRequest(BaseModel):
    """Request body for /outreach/whatsapp endpoint."""
    lead_ids: Optional[List[str]] = Field(
        default=None,
        description="Specific lead IDs. If None, uses all 'new' leads.",
    )
    max_messages: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Max messages to send in this run",
    )


class EmailOutreachRequest(BaseModel):
    """Request body for /outreach/email endpoint."""
    lead_ids: Optional[List[str]] = Field(
        default=None,
        description="Specific lead IDs. If None, uses all 'new' leads with email addresses.",
    )
    max_emails: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Max draft emails to generate in this run",
    )
    dry_run: bool = Field(
        default=False,
        description="If True, previews content without saving drafts",
    )


class EmailSendRequest(BaseModel):
    """Request body for /outreach/email/send endpoint."""
    email_ids: List[str] = Field(
        default_factory=list,
        description="Specific draft email record IDs to send",
        min_length=1,
    )


class EmailUpdateRequest(BaseModel):
    """Request body for PATCH /emails/{email_id} (edit draft fields)."""
    email: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None


class SocialPostRequest(BaseModel):
    """Request body for /social/post endpoint."""
    platforms: List[Literal["facebook", "instagram"]] = ["facebook", "instagram"]
    topic: Optional[str] = Field(
        default=None,
        description="Optional topic/theme for the post",
    )
    post_type: Literal["promotion", "engagement", "educational", "testimonial"] = "engagement"


class BotRunRequest(BaseModel):
    """Request body for /bot/run full cycle endpoint."""
    mode: Literal["full", "scrape_only", "outreach_only", "social_only"] = "full"
    dry_run: bool = Field(
        default=False,
        description="If True, generates content but doesn't send/post",
    )


class BotStatus(BaseModel):
    """Response model for /bot/status endpoint."""
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[str] = None
    total_leads: int = 0
    new_leads: int = 0
    contacted_leads: int = 0
    replied_leads: int = 0
    messages_sent_today: int = 0
    emails_sent_today: int = 0
    posts_published_today: int = 0
    daily_message_limit: int = 0
    daily_email_limit: int = 0
    daily_post_limit: int = 0


class LeadImportResult(BaseModel):
    imported: int = 0
    skipped: int = 0
    errors: List[str] = Field(default_factory=list)


class SettingsUpdateRequest(BaseModel):
    """Request body for /system/settings endpoint."""
    use_serpapi: bool

class ChatRequest(BaseModel):
    """Request body for /ai/chat endpoint."""
    message: str
