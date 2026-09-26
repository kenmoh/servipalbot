"""Unit tests for WhatsApp webhook reply matching (stub DB, no network, no real writes)."""
from typing import Any, Dict, List, Optional

import pytest

from app.media.whatsapp import WhatsAppClient


class StubDB:
    """Minimal SupabaseClient stand-in that records calls."""

    def __init__(self, lead: Optional[Dict[str, Any]]):
        self.lead = lead
        self.queries: List[str] = []
        self.status_updates: List[tuple] = []
        self.activity_logs: List[Dict[str, Any]] = []

    async def get_lead_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        self.queries.append(phone)
        if self.lead and phone in (self.lead["phone"], self.lead["phone"].lstrip("+")):
            return self.lead
        return None

    async def update_lead_status(self, lead_id: str, status: str, **kwargs) -> bool:
        self.status_updates.append((lead_id, status))
        return True

    async def log_activity(self, **kwargs) -> None:
        self.activity_logs.append(kwargs)


@pytest.fixture
def wa_client():
    return WhatsAppClient()


def _webhook_payload(from_phone: str, text: str = "Yes, I am interested") -> Dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "contacts": [{"profile": {"name": "Vendor"}, "wa_id": from_phone}],
                            "messages": [
                                {"from": from_phone, "id": "wamid.X", "timestamp": "1", "text": {"body": text}}
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


@pytest.mark.asyncio
async def test_webhook_reply_matches_lead_with_plus_prefix(wa_client: WhatsAppClient):
    db = StubDB({"id": "lead-1", "phone": "+2347049397434"})
    await wa_client.handle_webhook(_webhook_payload("2347049397434"), db)

    # First lookup uses '+<from>', second uses raw 'from'
    assert db.queries[0] == "+2347049397434"
    assert ("lead-1", "replied") in db.status_updates
    assert db.activity_logs and db.activity_logs[0]["event_type"] == "whatsapp_reply"


@pytest.mark.asyncio
async def test_webhook_reply_with_plus_stored_lead(wa_client: WhatsAppClient):
    db = StubDB({"id": "lead-2", "phone": "+2348031234567"})
    await wa_client.handle_webhook(_webhook_payload("+2348031234567"), db)

    assert ("lead-2", "replied") in db.status_updates


@pytest.mark.asyncio
async def test_webhook_reply_unknown_number_no_crash(wa_client: WhatsAppClient):
    db = StubDB(None)
    await wa_client.handle_webhook(_webhook_payload("2349999999999"), db)
    assert db.status_updates == []
