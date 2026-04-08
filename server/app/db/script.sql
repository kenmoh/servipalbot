-- ============================================================
-- ServiPal Marketing Bot - Supabase Database Schema
-- ============================================================
-- Run this in your Supabase SQL Editor to set up all tables.
-- Navigate to: https://app.supabase.com → SQL Editor → New Query

-- ── Enable UUID Extension ────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- ── LEADS TABLE ──────────────────────────────────────────────
-- Stores all scraped vendor leads with contact info and status
CREATE TABLE IF NOT EXISTS leads (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL,
    category        TEXT NOT NULL,
    phone           TEXT UNIQUE,               -- Unique constraint for deduplication
    email           TEXT,
    location        TEXT,
    source          TEXT DEFAULT 'manual',     -- google_maps | instagram | marketplace | manual
    status          TEXT DEFAULT 'new',        -- new | contacted | delivered | replied | converted | unsubscribed
    quality_score   FLOAT,                     -- AI classification score 0-1
    priority        TEXT,                      -- high | medium | low | skip
    instagram_handle TEXT,
    website         TEXT,
    rating          FLOAT,
    review_count    INTEGER,
    raw_data        JSONB,                     -- Raw scraper output for reference
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS leads_status_idx ON leads(status);
CREATE INDEX IF NOT EXISTS leads_priority_idx ON leads(priority);
CREATE INDEX IF NOT EXISTS leads_source_idx ON leads(source);
CREATE INDEX IF NOT EXISTS leads_created_at_idx ON leads(created_at DESC);
CREATE INDEX IF NOT EXISTS leads_category_idx ON leads(category);


-- ── MESSAGES TABLE ────────────────────────────────────────────
-- Tracks every WhatsApp message sent
CREATE TABLE IF NOT EXISTS messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id         UUID REFERENCES leads(id) ON DELETE CASCADE,
    phone           TEXT NOT NULL,
    content         TEXT NOT NULL,
    wa_message_id   TEXT,                      -- WhatsApp's message ID for webhook tracking
    status          TEXT DEFAULT 'pending',    -- pending | sent | delivered | read | failed | replied
    error_message   TEXT,
    retry_count     INTEGER DEFAULT 0,
    sent_at         TIMESTAMPTZ,
    delivered_at    TIMESTAMPTZ,
    read_at         TIMESTAMPTZ,
    replied_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS messages_lead_id_idx ON messages(lead_id);
CREATE INDEX IF NOT EXISTS messages_status_idx ON messages(status);
CREATE INDEX IF NOT EXISTS messages_wa_id_idx ON messages(wa_message_id);
CREATE INDEX IF NOT EXISTS messages_created_at_idx ON messages(created_at DESC);
-- For daily count queries
CREATE INDEX IF NOT EXISTS messages_sent_today_idx ON messages(created_at, status);


-- ── SOCIAL POSTS TABLE ────────────────────────────────────────
-- Tracks all social media posts
CREATE TABLE IF NOT EXISTS social_posts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    platform        TEXT NOT NULL,             -- facebook | instagram | both
    caption         TEXT NOT NULL,
    hashtags        TEXT[],                    -- Array of hashtag strings
    post_type       TEXT DEFAULT 'engagement', -- promotion | engagement | educational | testimonial
    fb_post_id      TEXT,                      -- Facebook post ID
    ig_post_id      TEXT,                      -- Instagram post ID
    status          TEXT DEFAULT 'draft',      -- draft | published | failed
    likes           INTEGER DEFAULT 0,
    comments        INTEGER DEFAULT 0,
    reach           INTEGER DEFAULT 0,
    error_message   TEXT,
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS posts_status_idx ON social_posts(status);
CREATE INDEX IF NOT EXISTS posts_platform_idx ON social_posts(platform);
CREATE INDEX IF NOT EXISTS posts_published_at_idx ON social_posts(published_at DESC);
CREATE INDEX IF NOT EXISTS posts_created_at_idx ON social_posts(created_at DESC);


-- ── LOGS TABLE ────────────────────────────────────────────────
-- Activity log for all bot operations
CREATE TABLE IF NOT EXISTS logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type      TEXT NOT NULL,             -- e.g., scrape_complete, message_sent, bot_cycle_start
    level           TEXT DEFAULT 'info',       -- info | warning | error | success
    message         TEXT NOT NULL,
    module          TEXT NOT NULL,             -- scraper | ai_engine | whatsapp | social_media | scheduler
    details         JSONB,                     -- Additional structured data
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS logs_level_idx ON logs(level);
CREATE INDEX IF NOT EXISTS logs_event_type_idx ON logs(event_type);
CREATE INDEX IF NOT EXISTS logs_module_idx ON logs(module);
CREATE INDEX IF NOT EXISTS logs_created_at_idx ON logs(created_at DESC);


-- ── UPDATED_AT TRIGGERS ───────────────────────────────────────
-- Auto-update updated_at timestamps

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_messages_updated_at
    BEFORE UPDATE ON messages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_social_posts_updated_at
    BEFORE UPDATE ON social_posts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ── ROW LEVEL SECURITY (Optional - enable for multi-tenant) ──
-- ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE social_posts ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE logs ENABLE ROW LEVEL SECURITY;


-- ── SUPABASE CRON JOBS ────────────────────────────────────────
-- Enable pg_cron extension first: https://supabase.com/docs/guides/database/extensions/pg_cron
-- Go to: Database → Extensions → Search "pg_cron" → Enable

-- Morning WhatsApp outreach (9 AM UTC daily, adjust timezone offset)
SELECT cron.schedule(
    'morning-whatsapp-outreach',
    '0 8 * * *',   -- 8 AM UTC = 9 AM WAT (West Africa Time)
    $$
    SELECT net.http_post(
        url := 'https://YOUR-BOT-URL/bot/run',
        headers := '{"Content-Type": "application/json"}'::jsonb,
        body := '{"mode": "outreach_only", "dry_run": false}'::jsonb
    ) AS request_id;
    $$
);

-- Midday social media posts (11 AM UTC daily)
SELECT cron.schedule(
    'midday-social-posts',
    '0 11 * * *',   -- 11 AM UTC = 12 PM WAT
    $$
    SELECT net.http_post(
        url := 'https://YOUR-BOT-URL/bot/run',
        headers := '{"Content-Type": "application/json"}'::jsonb,
        body := '{"mode": "social_only", "dry_run": false}'::jsonb
    ) AS request_id;
    $$
);

-- Evening lead scraping (5 PM UTC daily)
SELECT cron.schedule(
    'evening-lead-scraping',
    '0 17 * * *',   -- 5 PM UTC = 6 PM WAT
    $$
    SELECT net.http_post(
        url := 'https://YOUR-BOT-URL/bot/run',
        headers := '{"Content-Type": "application/json"}'::jsonb,
        body := '{"mode": "scrape_only", "dry_run": false}'::jsonb
    ) AS request_id;
    $$
);

-- ── USEFUL VIEWS ──────────────────────────────────────────────

-- Daily lead summary
CREATE OR REPLACE VIEW daily_lead_summary AS
SELECT
    DATE(created_at) AS date,
    source,
    COUNT(*) AS total_leads,
    COUNT(CASE WHEN status = 'contacted' THEN 1 END) AS contacted,
    COUNT(CASE WHEN status = 'replied' THEN 1 END) AS replied,
    COUNT(CASE WHEN status = 'converted' THEN 1 END) AS converted,
    ROUND(AVG(quality_score)::numeric, 2) AS avg_quality_score
FROM leads
GROUP BY DATE(created_at), source
ORDER BY date DESC;

-- Daily message stats
CREATE OR REPLACE VIEW daily_message_stats AS
SELECT
    DATE(created_at) AS date,
    COUNT(*) AS total_sent,
    COUNT(CASE WHEN status = 'delivered' THEN 1 END) AS delivered,
    COUNT(CASE WHEN status = 'read' THEN 1 END) AS read_count,
    COUNT(CASE WHEN status = 'replied' THEN 1 END) AS replied,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) AS failed
FROM messages
GROUP BY DATE(created_at)
ORDER BY date DESC;