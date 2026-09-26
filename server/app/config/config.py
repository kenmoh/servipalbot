"""
ServiPal Bot - Configuration
============================
All environment variables loaded via Pydantic BaseSettings.
Copy env.example.txt to .env and fill in your credentials.
"""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings
from typing import Literal

from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):

    # ── App ───────────────────────────────────────────────────────────────────
    APP_ENV:   Literal["development", "production"] = "development"
    LOG_LEVEL: str = "INFO"

    # ── AI (Gemini only) ──────────────────────────────────────────────────────
    # Sign up: https://aistudio.google.com/apikey
    # Accepts either GEMINI_API_KEY or GOOGLE_API_KEY from the environment.
    GEMINI_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"


    # ── Supabase ──────────────────────────────────────────────────────────────
    SUPABASE_URL:         str 
    SUPABASE_ANON_KEY:    str 
    SUPABASE_SERVICE_KEY: str 

    # ── WhatsApp Cloud API ────────────────────────────────────────────────────
    WHATSAPP_TOKEN:              str = "your_whatsapp_cloud_api_token_here"
    WHATSAPP_PHONE_ID:           str = "your_whatsapp_phone_number_id_here"
    WHATSAPP_API_VERSION:        str = "v19.0"
    WHATSAPP_DAILY_LIMIT:        int = 250
    WHATSAPP_WEBHOOK_VERIFY_TOKEN: str = "servipal_webhook_secret"

    # ── Meta Graph API (Facebook & Instagram) ────────────────────────────────
    META_ACCESS_TOKEN:    str = "your_meta_page_access_token_here"
    FACEBOOK_PAGE_ID:     str = "your_facebook_page_id_here"
    INSTAGRAM_ACCOUNT_ID: str = "your_instagram_business_account_id_here"
    META_API_VERSION:     str = "v19.0"
    META_DAILY_POST_LIMIT:int = 25

    RESEND_API_KEY:       str = ""
    RESEND_BASE_URL:      str = "https://api.resend.com"
    RESEND_FROM_ADDRESS:  str = ""
    RESEND_FROM_NAME:     str = "ServiPal"
    RESEND_REPLY_TO:      str = ""
    EMAIL_DAILY_LIMIT:    int = 50
    EMAIL_DELAY_SECONDS:  int = 30

    # ── Lead Scraping ─────────────────────────────────────────────────────────
    USE_SERPAPI: bool = False
    SERPAPI_KEY: str

    # Experimental OpenStreetMap (Overpass) source. Off by default; when enabled
    # it never fails the run - errors are logged and the source returns 0 leads.
    SCRAPER_OVERPASS_ENABLED: bool = False
    SCRAPER_OVERPASS_URL:    str  = "https://overpass-api.de/api/interpreter"

    # Cap on Instagram profile-enrichment calls per scrape run (public web API).
    SCRAPER_INSTAGRAM_MAX_PROFILES: int = 12

    # ── Bot Behaviour ─────────────────────────────────────────────────────────
    BOT_NAME:              str = "ServiPal"
    BOT_TIMEZONE:          str = "Africa/Lagos"
    MAX_RETRIES:           int = 3
    RETRY_DELAY_SECONDS:   int = 5
    REQUEST_TIMEOUT:       int = 30
    MORNING_OUTREACH_HOUR: int = 9
    MIDDAY_SOCIAL_HOUR:    int = 12

    class Config:
        env_file          = ".env"
        env_file_encoding = "utf-8"
        case_sensitive    = True
        extra             = "ignore"  # tolerate unrelated env vars users keep in .env

    @staticmethod
    def _is_placeholder(value: str) -> bool:
        if not value:
            return True
        return (
            value.startswith("your_")
            or value.endswith("_here")
            or "your-project" in value
            or value == "servipal_webhook_secret"
        )

    @property
    def gemini_configured(self) -> bool:
        return not self._is_placeholder(self.GEMINI_API_KEY)

    @property
    def supabase_configured(self) -> bool:
        return (
            not self._is_placeholder(self.SUPABASE_URL)
            and not self._is_placeholder(self.SUPABASE_SERVICE_KEY)
        )

    @property
    def whatsapp_configured(self) -> bool:
        return (
            not self._is_placeholder(self.WHATSAPP_TOKEN)
            and not self._is_placeholder(self.WHATSAPP_PHONE_ID)
        )

    @property
    def meta_configured(self) -> bool:
        return (
            not self._is_placeholder(self.META_ACCESS_TOKEN)
            and not self._is_placeholder(self.FACEBOOK_PAGE_ID)
            and not self._is_placeholder(self.INSTAGRAM_ACCOUNT_ID)
        )

    @property
    def resend_configured(self) -> bool:
        return (
            not self._is_placeholder(self.RESEND_API_KEY)
            and bool(self.RESEND_FROM_ADDRESS.strip())
        )

    @property
    def serpapi_configured(self) -> bool:
        return self.USE_SERPAPI and not self._is_placeholder(self.SERPAPI_KEY)

    @property
    def overpass_enabled(self) -> bool:
        return self.SCRAPER_OVERPASS_ENABLED and bool(self.SCRAPER_OVERPASS_URL.strip())

    def integration_status(self) -> dict[str, bool]:
        return {
            "gemini": self.gemini_configured,
            "supabase": self.supabase_configured,
            "whatsapp": self.whatsapp_configured,
            "meta": self.meta_configured,
            "resend": self.resend_configured,
            "serpapi": self.serpapi_configured,
        }


settings = Settings()
