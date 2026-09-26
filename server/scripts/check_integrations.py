#!/usr/bin/env python3
"""
ServiPal integration checks.

Usage:
  uv run python scripts/check_integrations.py
  uv run python scripts/check_integrations.py --live
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai_engine.engine import AIEngine
from app.config.config import settings
from app.db.database import SupabaseClient
from app.media.social_media import SocialMediaClient
from app.media.whatsapp import WhatsAppClient


async def check_gemini_live(ai: AIEngine) -> dict[str, Any]:
    if not ai.enabled:
        return {"configured": False, "reachable": False}

    try:
        text = await ai._call_gemini('Reply with valid JSON: {"ok":true}', max_tokens=64)
        return {"configured": True, "reachable": bool(text), "response": (text or "")[:120]}
    except Exception as e:
        return {"configured": True, "reachable": False, "error": str(e)[:200]}


async def check_meta_live(social: SocialMediaClient) -> dict[str, Any]:
    if not social.enabled:
        return {"configured": False, "reachable": False}

    try:
        response = await social.client.get(
            f"{social.base_url}/{social.fb_page_id}",
            params={"fields": "id,name", "access_token": social.access_token},
        )
        response.raise_for_status()
        return {"configured": True, "reachable": True, "status_code": response.status_code}
    except Exception as e:
        return {"configured": True, "reachable": False, "error": str(e)[:200]}


async def check_whatsapp_live(whatsapp: WhatsAppClient) -> dict[str, Any]:
    if not whatsapp.enabled:
        return {"configured": False, "reachable": False}

    try:
        response = await whatsapp.client.get(
            f"https://graph.facebook.com/{whatsapp.version}/{whatsapp.phone_id}",
            headers=whatsapp.headers,
        )
        response.raise_for_status()
        return {"configured": True, "reachable": True, "status_code": response.status_code}
    except Exception as e:
        return {"configured": True, "reachable": False, "error": str(e)[:200]}


async def main(live: bool) -> None:
    db = SupabaseClient()
    ai = AIEngine()
    whatsapp = WhatsAppClient()
    social = SocialMediaClient()

    try:
        report = {
            "config": settings.integration_status(),
            "database": await db.healthcheck(),
            "ai_engine": await ai.healthcheck(),
            "whatsapp": await whatsapp.healthcheck(),
            "social_media": await social.healthcheck(),
        }

        if live:
            report["gemini_live"] = await check_gemini_live(ai)
            report["whatsapp_live"] = await check_whatsapp_live(whatsapp)
            report["meta_live"] = await check_meta_live(social)

        for section, value in report.items():
            print(f"{section}: {value}")
    finally:
        await ai.close()
        await whatsapp.close()
        await social.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Run lightweight external API checks")
    args = parser.parse_args()
    asyncio.run(main(args.live))
