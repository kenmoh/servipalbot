"""
ServiPal Bot - Social Media Client
====================================
Handles automated posting to Facebook Pages and Instagram Business accounts
via Meta Graph API (free tier).

Features:
- Generate AI content and post to Facebook
- Cross-post to Instagram (linked business account)
- Rate limit management (25 posts/day limit)
- Post performance tracking in Supabase

API Docs: https://developers.facebook.com/docs/graph-api
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Tuple

import httpx

from app.config.config import settings
from app.schemas.schemas import SocialPost, SocialPostRecord
from app.db.database import SupabaseClient

logger = logging.getLogger("servipal_bot.social_media")

META_API_BASE = "https://graph.facebook.com/{version}"


class SocialMediaClient:
    """
    Meta Graph API client for Facebook and Instagram posting.
    """

    def __init__(self):
        self.access_token = settings.META_ACCESS_TOKEN
        self.fb_page_id = settings.FACEBOOK_PAGE_ID
        self.ig_account_id = settings.INSTAGRAM_ACCOUNT_ID
        self.version = settings.META_API_VERSION
        self.daily_limit = settings.META_DAILY_POST_LIMIT
        self.enabled = settings.meta_configured

        self.base_url = META_API_BASE.format(version=self.version)
        self.client = httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT)
        if self.enabled:
            logger.info("Social media client initialized")
        else:
            logger.warning("Social media client is not fully configured; publish operations will be skipped")

    # ── Facebook Posting ──────────────────────────────────────────────────────

    async def post_to_facebook(
        self,
        caption: str,
        db: SupabaseClient,
        image_url: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Post content to Facebook Page.

        Args:
            caption: Post text with hashtags
            db: Supabase client for logging
            image_url: Optional public image URL to attach

        Returns:
            (success: bool, post_id: str)
        """
        if not self.enabled:
            logger.warning("Facebook post skipped because Meta integration is not configured")
            return False, None

        try:
            endpoint = f"{self.base_url}/{self.fb_page_id}/feed"

            if image_url:
                # Photo post
                endpoint = f"{self.base_url}/{self.fb_page_id}/photos"
                payload = {
                    "url": image_url,
                    "caption": caption,
                    "access_token": self.access_token,
                }
            else:
                # Text post
                payload = {
                    "message": caption,
                    "access_token": self.access_token,
                }

            response = await self.client.post(endpoint, data=payload)
            response.raise_for_status()
            data = response.json()

            post_id = data.get("id") or data.get("post_id")
            logger.info(f"✅ Facebook post published: {post_id}")

            await db.log_activity(
                event_type="facebook_post",
                level="success",
                message=f"Post published to Facebook: {post_id}",
                module="social_media",
                details={"post_id": post_id, "has_image": bool(image_url)},
            )
            return True, post_id

        except httpx.HTTPStatusError as e:
            error = e.response.text[:300]
            logger.error(f"❌ Facebook post failed ({e.response.status_code}): {error}")
            await db.log_activity(
                event_type="facebook_post_failed",
                level="error",
                message=f"Facebook post failed: {error}",
                module="social_media",
            )
            return False, None
        except Exception as e:
            logger.error(f"❌ Facebook post error: {e}")
            return False, None

    # ── Instagram Posting ─────────────────────────────────────────────────────

    async def post_to_instagram(
        self,
        caption: str,
        image_url: str,
        db: SupabaseClient,
    ) -> Tuple[bool, Optional[str]]:
        """
        Post image + caption to Instagram Business account.
        NOTE: Instagram requires an image URL - text-only posts not supported.
        Uses 2-step container → publish flow.

        Args:
            caption: Post caption with hashtags
            image_url: Public HTTPS URL of image to post
            db: Supabase client for logging

        Returns:
            (success: bool, post_id: str)
        """
        if not self.enabled:
            logger.warning("Instagram post skipped because Meta integration is not configured")
            return False, None

        try:
            # Step 1: Create media container
            container_url = f"{self.base_url}/{self.ig_account_id}/media"
            container_payload = {
                "image_url": image_url,
                "caption": caption,
                "access_token": self.access_token,
            }

            response = await self.client.post(container_url, data=container_payload)
            response.raise_for_status()
            container_id = response.json().get("id")

            if not container_id:
                logger.error("❌ Instagram: No container ID returned")
                return False, None

            # Brief wait for container processing
            await asyncio.sleep(3)

            # Step 2: Publish the container
            publish_url = f"{self.base_url}/{self.ig_account_id}/media_publish"
            publish_payload = {
                "creation_id": container_id,
                "access_token": self.access_token,
            }

            response = await self.client.post(publish_url, data=publish_payload)
            response.raise_for_status()
            post_id = response.json().get("id")

            logger.info(f"✅ Instagram post published: {post_id}")
            await db.log_activity(
                event_type="instagram_post",
                level="success",
                message=f"Post published to Instagram: {post_id}",
                module="social_media",
            )
            return True, post_id

        except httpx.HTTPStatusError as e:
            error = e.response.text[:300]
            logger.error(f"❌ Instagram post failed ({e.response.status_code}): {error}")
            await db.log_activity(
                event_type="instagram_post_failed",
                level="error",
                message=f"Instagram post failed: {error}",
                module="social_media",
            )
            return False, None
        except Exception as e:
            logger.error(f"❌ Instagram post error: {e}")
            return False, None

    # ── Combined Post ─────────────────────────────────────────────────────────

    async def publish_post(
        self,
        post: SocialPost,
        platforms: List[str],
        db: SupabaseClient,
        image_url: Optional[str] = None,
    ) -> SocialPostRecord:
        """
        Publish an AI-generated post to one or more platforms.
        Saves record in Supabase and returns the record.
        """
        # Check daily limit
        published_today = await db.get_posts_published_today()
        if published_today >= self.daily_limit:
            logger.warning(
                f"⚠️ Daily post limit reached ({self.daily_limit}). Skipping post."
            )
            record = SocialPostRecord(
                platform="both" if len(platforms) > 1 else platforms[0],
                caption=post.formatted_caption(),
                hashtags=post.hashtags,
                post_type=post.post_type,
                status="draft",
                error_message="Daily limit reached",
            )
            await db.save_social_post(record)
            return record

        caption = post.formatted_caption()
        fb_id = None
        ig_id = None
        status = "failed"
        error_msg = None

        # Post to Facebook
        if "facebook" in platforms:
            fb_success, fb_id = await self.post_to_facebook(caption, db, image_url)
            if fb_success:
                status = "published"

        # Post to Instagram (requires image)
        if "instagram" in platforms:
            if image_url:
                ig_success, ig_id = await self.post_to_instagram(caption, image_url, db)
                if ig_success:
                    status = "published"
            else:
                logger.warning("⚠️ Instagram requires an image URL - skipping Instagram post")

        # Save post record
        record = SocialPostRecord(
            platform="both" if len(platforms) > 1 else platforms[0],
            caption=caption,
            hashtags=post.hashtags,
            post_type=post.post_type,
            fb_post_id=fb_id,
            ig_post_id=ig_id,
            status=status,
            error_message=error_msg,
            published_at=datetime.utcnow() if status == "published" else None,
        )

        saved = await db.save_social_post(record)
        if saved:
            record.id = saved.get("id")

        logger.info(
            f"📊 Post published to {platforms}: "
            f"FB={fb_id or 'failed'}, IG={ig_id or 'skipped/failed'}"
        )
        return record

    # ── Fetch Post Stats ──────────────────────────────────────────────────────

    async def fetch_post_insights(self, post_id: str) -> Dict:
        """
        Fetch engagement metrics for a published Facebook post.
        Updates Supabase with latest stats.
        """
        try:
            url = f"{self.base_url}/{post_id}/insights"
            params = {
                "metric": "post_impressions,post_engagements,post_reactions_by_type_total",
                "access_token": self.access_token,
            }
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.debug(f"Failed to fetch insights for {post_id}: {e}")
            return {}

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def healthcheck(self) -> dict:
        return {
            "configured": self.enabled,
            "facebook_page_present": bool(self.fb_page_id and self.fb_page_id != "your_facebook_page_id_here"),
            "instagram_account_present": bool(self.ig_account_id and self.ig_account_id != "your_instagram_business_account_id_here"),
        }
