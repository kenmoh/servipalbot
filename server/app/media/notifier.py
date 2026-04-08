"""
ServiPal Bot - Notifications
============================
Minimal notifier used by the scheduler for summaries and alerts.
This keeps the bot bootable even when Slack/Telegram integrations
have not been configured yet.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger("servipal_bot.notifier")


class Notifier:
    """No-op notifier that logs summaries and alerts."""

    async def send_summary(self, summary: Dict[str, Any]) -> None:
        logger.info("Bot summary: %s", summary)

    async def send_alert(self, message: str) -> None:
        logger.warning("Bot alert: %s", message)
