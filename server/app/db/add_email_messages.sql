-- ============================================================
-- ServiPal Marketing Bot - Email Messages Migration
-- ============================================================
-- Run this in Supabase SQL Editor after the base schema is in place.

CREATE TABLE IF NOT EXISTS email_messages (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id             UUID REFERENCES leads(id) ON DELETE CASCADE,
    email               TEXT NOT NULL,
    subject             TEXT NOT NULL,
    body                TEXT NOT NULL,
    provider_message_id TEXT,
    status              TEXT DEFAULT 'pending',
    error_message       TEXT,
    retry_count         INTEGER DEFAULT 0,
    sent_at             TIMESTAMPTZ,
    delivered_at        TIMESTAMPTZ,
    replied_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS email_messages_lead_id_idx ON email_messages(lead_id);
CREATE INDEX IF NOT EXISTS email_messages_status_idx ON email_messages(status);
CREATE INDEX IF NOT EXISTS email_messages_created_at_idx ON email_messages(created_at DESC);

CREATE TRIGGER update_email_messages_updated_at
    BEFORE UPDATE ON email_messages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
