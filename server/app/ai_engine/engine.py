"""
ServiPal Bot - AI Engine
=========================
Handles all AI inference for:
1. Lead classification
2. WhatsApp message generation
3. Social media post generation

Provider: Groq (free tier)
- Sign up: https://console.groq.com
- Free: ~14,400 requests/day
- Models: llama3-8b-8192 (fast) | llama3-70b-8192 (smarter) | mixtral-8x7b-32768 (best JSON)

Uses Pydantic models to validate and structure AI outputs.
"""

import json
import logging
import re
import unicodedata
from typing import Optional

import httpx

from app.config.config import settings
from app.schemas.schemas import (
    WhatsAppMessage,
    ColdEmail,
    SocialPost,
    LeadClassification,
)

logger = logging.getLogger("servipal_bot.ai_engine")

# ── Prompt Templates ──────────────────────────────────────────────────────────

WHATSAPP_PROMPT = """You are writing a real WhatsApp message for a business partnership conversation.

Write a short, natural outreach message to a vendor. The message should:
- Sound like one person reaching out to another, not like ad copy
- Use simple conversational English
- Avoid hype, polished marketing language, and generic AI phrasing
- Avoid emojis, hashtags, bullet points, quotation marks around phrases, and long dashes
- Avoid words like "thrilled", "excited", "empower", "unlock", "seamless", "revolutionize", or "valued partner"
- Be between 70-140 words total
- Mention one practical benefit relevant to their business type
- End with a low-pressure question

Vendor Details:
- Name: {vendor_name}
- Business Type: {category}
- Location: {location}
- Platform benefit: {platform_benefit}

Respond ONLY with valid JSON matching this exact structure:
{{
  "greeting": "string (personal greeting using vendor name)",
  "body": "string (main value proposition, 50-150 words)",
  "call_to_action": "string (clear next step, 10-30 words)",
  "full_message": "string (complete assembled message)",
  "language": "en",
  "tone_score": 0.85
}}"""

SOCIAL_POST_PROMPT = """You are writing a social media post for ServiPal, a multi-service platform in Africa covering delivery, restaurants, laundry, and marketplace services.

Create an engaging {post_type} post for {platforms}. The post should:
- Be clear, grounded, and human
- Avoid emojis, long dashes, and over-polished AI-sounding phrasing
- Avoid buzzwords and generic motivational language
- Drive engagement without sounding salesy
- Topic/theme: {topic}

Respond ONLY with valid JSON matching this exact structure:
{{
  "caption": "string (main post text, 50-300 words)",
  "hashtags": ["list", "of", "hashtags", "without", "hash"],
  "call_to_action": "string (engagement prompt)",
  "suggested_image_prompt": "string (description for stock photo or AI image)",
  "post_type": "{post_type}",
  "best_posting_time": "12:00"
}}"""

COLD_EMAIL_PROMPT = """You are writing a real cold email to a business owner.

Write a short, natural business outreach email. The email should:
- Sound human and direct
- Avoid emojis, long dashes, buzzwords, and generic AI wording
- Avoid exaggerated claims and corporate-sounding filler
- Stay between 90-170 words
- Mention one practical reason the business might care
- End with a simple low-pressure question

Business Details:
- Name: {vendor_name}
- Business Type: {category}
- Location: {location}
- Platform benefit: {platform_benefit}

Respond ONLY with valid JSON matching this exact structure:
{{
  "subject": "string (5-12 words, simple and natural)",
  "body": "string (full email body)",
  "full_email": "string (complete final email)"
}}"""

CLASSIFICATION_PROMPT = """You are a lead quality analyst for ServiPal, a service platform for local businesses.

Analyze this business lead and classify its quality and priority for outreach.

Lead Data:
- Name: {name}
- Category: {category}
- Location: {location}
- Phone: {phone}
- Rating: {rating}
- Review Count: {review_count}
- Source: {source}

Scoring criteria:
- HIGH priority: Active business, clear phone, relevant category (restaurant/laundry/delivery/grocery)
- MEDIUM: Has phone but unclear category or low engagement
- LOW: Missing contact info, unrelated business
- SKIP: Clearly irrelevant, duplicate, or uncontactable

Respond ONLY with valid JSON:
{{
  "lead_id": "{lead_id}",
  "quality_score": 0.75,
  "priority": "high|medium|low|skip",
  "category": "normalized category name",
  "recommended_channel": "whatsapp|email|instagram_dm|skip",
  "reasoning": "brief explanation",
  "personalization_hints": ["key fact 1", "key fact 2"]
}}"""

# ── Category -> Benefit Mapping ───────────────────────────────────────────────
CATEGORY_BENEFITS = {
    "restaurant":  "reach more hungry customers with online ordering and delivery through ServiPal",
    "laundry":     "get more laundry pickup/delivery requests directly through the ServiPal app",
    "delivery":    "join our growing delivery partner network and access daily order volume",
    "grocery":     "list your grocery store and offer same-day delivery to nearby customers",
    "marketplace": "expand your marketplace reach with our built-in customer base",
    "default":     "grow your business with ServiPal's multi-service platform",
}


class AIEngine:
    """
    AI inference engine using Groq free tier.
    Falls back to Ollama if AI_PROVIDER=ollama is set.
    All outputs validated using Pydantic models.
    """

    def __init__(self):
        self.provider = settings.AI_PROVIDER
        self.client = httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT)
        self.enabled = True

        if self.provider == "groq":
            self.model    = settings.GROQ_MODEL
            self.base_url = settings.GROQ_BASE_URL
            self.headers  = {
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type":  "application/json",
            }
            self.enabled = settings.groq_configured
        else:  # ollama
            self.model    = settings.OLLAMA_MODEL
            self.base_url = settings.OLLAMA_BASE_URL
            self.headers  = {"Content-Type": "application/json"}

        if self.enabled:
            logger.info(f"AI Engine ready: provider={self.provider} model={self.model}")
        else:
            logger.warning("AI provider is not fully configured; fallback content will be used")

    # ── LLM Call ──────────────────────────────────────────────────────────────

    async def _call_llm(self, prompt: str, max_tokens: int = 600) -> Optional[str]:
        """Route call to configured LLM and return raw text."""
        if not self.enabled:
            return None
        try:
            if self.provider == "groq":
                return await self._call_groq(prompt, max_tokens)
            else:
                return await self._call_ollama(prompt, max_tokens)
        except Exception as e:
            logger.error(f"❌ LLM call failed: {e}")
            return None

    async def _call_groq(self, prompt: str, max_tokens: int) -> Optional[str]:
        """
        Call Groq Chat Completions API.
        Free tier: ~14,400 req/day on llama3-8b-8192.
        Docs: https://console.groq.com/docs/openai
        """
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "response_format": {"type": "json_object"},  # Forces clean JSON output
        }
        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            headers=self.headers,
            json=payload,
        )

        if response.status_code == 429:
            logger.warning("⚠️ Groq rate limit hit — backing off 60s")
            import asyncio
            await asyncio.sleep(60)
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
            )

        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def _call_ollama(self, prompt: str, max_tokens: int) -> Optional[str]:
        """Call local Ollama instance (offline fallback)."""
        payload = {
            "model":   self.model,
            "prompt":  prompt,
            "stream":  False,
            "format":  "json",
            "options": {"temperature": 0.7, "num_predict": max_tokens},
        }
        response = await self.client.post(
            f"{self.base_url}/api/generate",
            headers=self.headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json().get("response", "")

    # ── JSON Extraction ───────────────────────────────────────────────────────

    def _extract_json(self, text: str) -> Optional[dict]:
        """
        Safely parse JSON from LLM response.
        Handles markdown fences and extra surrounding text.
        """
        if not text:
            return None

        # Strip markdown code fences
        text = re.sub(r"```(?:json)?\s*", "", text).strip().replace("```", "")

        # Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Find JSON object inside surrounding text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        logger.warning(f"⚠️ Could not parse JSON: {text[:150]}")
        return None

    def _sanitize_generated_text(self, text: str) -> str:
        """Normalize generated copy so it reads more naturally in outreach."""
        if not text:
            return ""

        text = text.replace("—", "-").replace("–", "-")
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        text = text.replace('"', "").replace("*", "")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" *- *", ", ", text)
        text = re.sub(r"\s+\?", "?", text)
        text = re.sub(r"!{2,}", "!", text)
        text = re.sub(r"\?{2,}", "?", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        replacements = {
            "I'm reaching out": "I wanted to reach out",
            "We'd love to": "We'd like to",
            "we'd love to": "we'd like to",
            "thrilled": "glad",
            "excited": "happy",
            "seamless": "simple",
            "unlock": "get",
            "valued partner": "partner",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)

        return text.strip()

    def _sanitize_whatsapp_payload(self, data: dict) -> dict:
        """Clean LLM message fields before validation."""
        cleaned = dict(data)
        for key in ("greeting", "body", "call_to_action", "full_message"):
            if key in cleaned and cleaned[key]:
                cleaned[key] = self._sanitize_generated_text(cleaned[key])
        return cleaned

    def _sanitize_social_payload(self, data: dict) -> dict:
        """Clean social copy so it matches the requested tone."""
        cleaned = dict(data)
        for key in ("caption", "call_to_action", "suggested_image_prompt"):
            if key in cleaned and cleaned[key]:
                cleaned[key] = self._sanitize_generated_text(cleaned[key])
        return cleaned

    def _sanitize_cold_email_payload(self, data: dict) -> dict:
        """Clean cold email fields before validation."""
        cleaned = dict(data)
        for key in ("subject", "body", "full_email"):
            if key in cleaned and cleaned[key]:
                cleaned[key] = self._sanitize_generated_text(cleaned[key])

        for key in ("body", "full_email"):
            value = cleaned.get(key, "")
            value = re.sub(r"^subject:\s*.*?\n+", "", value, flags=re.IGNORECASE | re.DOTALL)
            cleaned[key] = value.strip()

        return cleaned

    # ── Public Methods ────────────────────────────────────────────────────────

    async def generate_whatsapp_message(
        self,
        vendor_name: str,
        category:    str,
        location:    str,
    ) -> Optional[WhatsAppMessage]:
        """Generate a personalized WhatsApp outreach message."""
        benefit = CATEGORY_BENEFITS.get(category.lower(), CATEGORY_BENEFITS["default"])
        prompt  = WHATSAPP_PROMPT.format(
            vendor_name=vendor_name,
            category=category,
            location=location,
            platform_benefit=benefit,
        )

        logger.info(f"🤖 Generating WhatsApp message for: {vendor_name}")
        raw  = await self._call_llm(prompt, max_tokens=400)
        data = self._extract_json(raw)

        if not data:
            logger.warning(f"⚠️ No valid JSON for {vendor_name}, using fallback")
            return self._fallback_whatsapp_message(vendor_name, category, location, benefit)

        try:
            data = self._sanitize_whatsapp_payload(data)
            if not data.get("full_message"):
                data["full_message"] = (
                    f"{data.get('greeting', '')}\n\n"
                    f"{data.get('body', '')}\n\n"
                    f"{data.get('call_to_action', '')}"
                )
            return WhatsAppMessage(**data)
        except Exception as e:
            logger.warning(f"⚠️ Validation failed: {e} — using fallback")
            return self._fallback_whatsapp_message(vendor_name, category, location, benefit)

    async def generate_social_post(
        self,
        post_type: str           = "engagement",
        platforms: str           = "Facebook and Instagram",
        topic:     Optional[str] = None,
    ) -> Optional[SocialPost]:
        """Generate an AI social media post for ServiPal."""
        if not topic:
            topic = "ServiPal connecting local businesses with customers"

        prompt = SOCIAL_POST_PROMPT.format(
            post_type=post_type,
            platforms=platforms,
            topic=topic,
        )

        logger.info(f"🤖 Generating {post_type} social post")
        raw  = await self._call_llm(prompt, max_tokens=500)
        data = self._extract_json(raw)

        if not data:
            return self._fallback_social_post(post_type)

        try:
            data = self._sanitize_social_payload(data)
            data["post_type"] = post_type
            return SocialPost(**data)
        except Exception as e:
            logger.warning(f"⚠️ Social post validation failed: {e} — using fallback")
            return self._fallback_social_post(post_type)

    async def generate_cold_email(
        self,
        vendor_name: str,
        category: str,
        location: str,
    ) -> Optional[ColdEmail]:
        """Generate a natural cold email for a lead."""
        benefit = CATEGORY_BENEFITS.get(category.lower(), CATEGORY_BENEFITS["default"])
        prompt = COLD_EMAIL_PROMPT.format(
            vendor_name=vendor_name,
            category=category,
            location=location,
            platform_benefit=benefit,
        )

        logger.info(f"Generating cold email for: {vendor_name}")
        raw = await self._call_llm(prompt, max_tokens=450)
        data = self._extract_json(raw)

        if not data:
            return self._fallback_cold_email(vendor_name, category, location, benefit)

        try:
            data = self._sanitize_cold_email_payload(data)
            if not data.get("full_email"):
                data["full_email"] = data.get("body", "")
            return ColdEmail(**data)
        except Exception as e:
            logger.warning(f"Cold email validation failed: {e} - using fallback")
            return self._fallback_cold_email(vendor_name, category, location, benefit)

    async def classify_lead(
        self,
        lead_id:      str,
        name:         str,
        category:     str,
        location:     str            = "",
        phone:        str            = "",
        rating:       Optional[float]= None,
        review_count: Optional[int]  = None,
        source:       str            = "unknown",
    ) -> Optional[LeadClassification]:
        """Classify a lead's quality and priority using AI."""
        prompt = CLASSIFICATION_PROMPT.format(
            lead_id=lead_id, name=name, category=category,
            location=location, phone=phone or "not provided",
            rating=rating or "unknown",
            review_count=review_count or "unknown",
            source=source,
        )

        raw  = await self._call_llm(prompt, max_tokens=300)
        data = self._extract_json(raw)

        if not data:
            return LeadClassification(
                lead_id=lead_id, quality_score=0.5, priority="medium",
                category=category,
                recommended_channel="whatsapp" if phone else "skip",
                reasoning="Classification failed, using defaults",
            )
        try:
            data["lead_id"] = lead_id
            return LeadClassification(**data)
        except Exception as e:
            logger.warning(f"⚠️ Lead classification validation failed: {e}")
            return None

    # ── Fallbacks ─────────────────────────────────────────────────────────────

    def _fallback_whatsapp_message(
        self, vendor_name: str, category: str, location: str, benefit: str
    ) -> WhatsAppMessage:
        """Hardcoded fallback when AI generation fails."""
        greeting = f"Hi {vendor_name},"
        body = (
            f"I wanted to reach out from ServiPal. We're working with {category} businesses "
            f"in {location} and helping them {benefit}. I thought your business could be a good fit."
        )
        cta = "Would you be open to a quick overview?"
        return WhatsAppMessage(
            greeting=greeting, body=body, call_to_action=cta,
            full_message=f"{greeting}\n\n{body}\n\n{cta}",
            tone_score=0.75,
        )

    def _fallback_social_post(self, post_type: str) -> SocialPost:
        """Hardcoded fallback social post when AI generation fails."""
        return SocialPost(
            caption=(
                "ServiPal helps local businesses get discovered and handle orders more easily.\n\n"
                "If you run a restaurant, laundry service, delivery business, or marketplace shop, "
                "the platform gives you a practical way to reach more customers."
            ),
            hashtags=["ServiPal", "LocalBusiness", "Delivery", "Restaurant", "Lagos"],
            call_to_action="Send us a message if you want to learn more.",
            suggested_image_prompt="Diverse smiling local business owners with delivery packages and food",
            post_type=post_type,
            best_posting_time="12:00",
        )

    def _fallback_cold_email(
        self,
        vendor_name: str,
        category: str,
        location: str,
        benefit: str,
    ) -> ColdEmail:
        """Fallback cold email when AI generation fails."""
        subject = f"A quick partnership idea for {vendor_name}"
        body = (
            f"Hi {vendor_name} team,\n\n"
            f"I wanted to reach out because we're building ServiPal for businesses in {location}. "
            f"For {category} businesses, the goal is simple: {benefit}.\n\n"
            f"I thought your business could be a good fit, and I wanted to ask if you'd be open "
            f"to a short overview of how it works.\n\n"
            f"Best,\n"
            f"{settings.BOT_NAME}"
        )
        return ColdEmail(subject=subject, body=body, full_email=body)

    async def close(self):
        await self.client.aclose()

    async def healthcheck(self) -> dict:
        return {
            "configured": self.enabled,
            "provider": self.provider,
            "model": self.model,
        }
