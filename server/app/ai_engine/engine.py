"""
ServiPal Bot - AI Engine
=========================
Handles all AI inference for:
1. Lead classification
2. WhatsApp message generation
3. Social media post generation

Provider: Google Gemini (AI Studio free tier)
- Sign up: https://aistudio.google.com/apikey
- Default model: gemini-3.5-flash-lite (override with GEMINI_MODEL)

Uses Pydantic models to validate and structure AI outputs.
"""

import json
import logging
import re
import unicodedata
from typing import Optional

from google import genai

from app.config.config import settings
from app.schemas.schemas import (
    WhatsAppMessage,
    ColdEmail,
    SocialPost,
    LeadClassification,
)

logger = logging.getLogger("servipal_bot.ai_engine")

client: Optional["genai.Client"] = (
    genai.Client(api_key=settings.GEMINI_API_KEY) if settings.gemini_configured else None
)

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

COLD_EMAIL_PROMPT = """
You are writing a genuine one-to-one cold email from Kenneth, who is reaching out personally on behalf of ServiPal.

The goal is to start a natural conversation with a local business owner, not to write a marketing or promotional email.

Write a short, personal, conversational email that feels like Kenneth actually found and considered this specific business before reaching out.

Rules:
- Sound like a real person, not a sales campaign or AI-generated message.
- Keep the tone warm, simple, and professional.
- Personalize the email using the business name, business type, and location naturally.
- Mention one specific practical reason ServiPal could be useful to this particular business.
- Do not make exaggerated claims or promise increased sales, revenue, or customer numbers.
- Do not use buzzwords such as "revolutionize", "seamless", "unlock", "empower", "grow your business", "leverage", "innovative", or "game-changer".
- Do not use emojis.
- Do not use long dashes.
- Do not use generic openings such as "I hope this email finds you well", "Dear Esteemed Business Owner", or "I am reaching out to introduce".
- Do not make the email sound like a newsletter, advertisement, or mass campaign.
- Avoid excessive descriptions of ServiPal.
- Do not include a website link in the first email unless specifically requested.
- Do not use bullet points.
- Keep the email between 80 and 140 words.
- Use short paragraphs with natural spacing.
- Mention that Kenneth is reaching out personally on behalf of ServiPal.
- If the business name sounds like a brand rather than a person's name, address the team naturally, for example "Hi Washyard team," or "Hi RSVP team,".
- Do not pretend to know anything about the business that was not provided.
- Do not invent details, reviews, customers, services, achievements, or history.
- End with a simple, low-pressure question that makes replying easy.
- The email should feel appropriate for a first contact where the recipient does not know Kenneth yet.

Location personalization:
- Never include the full business address in the email.
- Extract only the most recognizable street, neighborhood, district, or area name from the provided location.
- Prefer the street name when it is clear and natural.
- If the street name is not useful or recognizable, use the neighborhood or district instead.
- Never include postal codes, state names, country names, or long address strings unless they are genuinely necessary.
- Keep the location reference conversational.
- Examples:
  - "47 Allen Ave, Allen, Ikeja 101233, Lagos, Nigeria" → "Allen Ave"
  - "9 Eletu Ogabi St, Victoria Island, Lagos 101001, Lagos, Nigeria" → "Eletu Ogabi St" or "Victoria Island"
  - "5/7 St Finbarr's College Rd, Akoka, Lagos 100001, Lagos, Nigeria" → "St Finbarr's College Rd" or "Akoka"
- Do not force a location mention if it makes the email sound unnatural.

Business Details:
- Name: {vendor_name}
- Business Type: {category}
- Location: {location}
- Platform Benefit: {platform_benefit}

Before writing, silently identify:
1. What this particular business does.
2. Why ServiPal's stated platform benefit could reasonably matter to them.
3. The most natural short location reference to use, if a location reference is useful.

Then write the email.

Subject rules:
- 3 to 5 words.
- Natural and conversational.
- Do not use clickbait, urgency, promotional language, or excessive capitalization.
- Avoid words such as "offer", "deal", "opportunity", "promotion", "boost", "sales", or "partnership".
- The subject should sound like something a person would actually type when contacting one business.
  prefer a conversational subject in the format “Quick question for {vendor_name}”. Keep it natural and personal, and avoid formal wording such as “regarding”, “inquiry”, “business opportunity”, or “partnership” Avoid words such as "offer", "deal", "opportunity", "promotion", "boost", "sales", or "partnership".

Respond ONLY with valid JSON matching this exact structure:
{{
  "subject": "string",
  "body": "string",
  "full_email": "string"
}}

The "body" must contain only the email body, including the sign-off.

The "full_email" must contain the subject followed by the complete email body.

Do not wrap the JSON in markdown code fences."""

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
    "restaurant":  "reach more customers with online ordering and delivery through ServiPal",
    "laundry":     "get more laundry pickup/delivery requests directly through the ServiPal app",
    "delivery":    "join our growing delivery partner network and access daily order volume",
    "grocery":     "list your grocery store and offer same-day delivery to nearby customers",
    "marketplace": "expand your marketplace reach with our built-in customer base",
    "default":     "grow your business with ServiPal's multi-service platform",
}


class AIEngine:
    """
    AI inference engine using the Google Gemini API.
    All outputs validated using Pydantic models.
    """

    def __init__(self):
        self.provider = "gemini"
        self.model    = settings.GEMINI_MODEL
        self.client   = client
        self.enabled  = self.client is not None

        if self.enabled:
            logger.info(f"AI Engine ready: provider=gemini model={self.model}")
        else:
            logger.warning("Gemini API key not configured; fallback content will be used")

    # ── LLM Call ──────────────────────────────────────────────────────────────

    async def _call_llm(self, prompt: str, max_tokens: int = 600) -> Optional[str]:
        """Call Gemini and return raw text."""
        if not self.enabled:
            return None
        try:
            return await self._call_gemini(prompt, max_tokens)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None

    async def _call_gemini(self, prompt: str, max_tokens: int) -> Optional[str]:
        """
        Call the Gemini API via the Interactions API.
        JSON output is enforced with response_format so _extract_json stays clean.
        Docs: https://aistudio.google.com/docs/get-started
        """
        interaction = await self.client.aio.interactions.create(
            model=self.model,
            input=prompt,
            response_format={"type": "text", "mime_type": "application/json"},
            generation_config={"max_output_tokens": max_tokens},
        )
        return interaction.output_text

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

        logger.warning(f"Could not parse JSON: {text[:150]}")
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
            logger.warning(f"No valid JSON for {vendor_name}, using fallback")
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
            logger.warning(f"Validation failed: {e} — using fallback")
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
            logger.warning(f"Social post validation failed: {e} — using fallback")
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
            logger.warning(f"Lead classification validation failed: {e}")
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
        if self.client is not None:
            await self.client.aio.aclose()

    async def healthcheck(self) -> dict:
        return {
            "configured": self.enabled,
            "provider": self.provider,
            "model": self.model,
        }

    async def chat_completion(self, message: str) -> str:
        """Raw conversational interaction bypassing standard JSON formatting restrictions."""
        if not self.enabled:
            return "AI Engine is not configured."
            
        system_prompt = (
            "You are ServiPal Bot, a helpful operational AI for a service directory company. "
            "Help the administrator answer questions about operations, write emails, or debug business strategy."
        )

        try:
            interaction = await self.client.aio.interactions.create(
                model=self.model,
                system_instruction=system_prompt,
                input=message,
                generation_config={"max_output_tokens": 1000},
            )
            return interaction.output_text or ""
        except Exception as e:
            logger.error(f"Chat completion failed: {e}")
            return f"Error communicating with AI model: {str(e)}"
