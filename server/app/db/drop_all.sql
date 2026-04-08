-- ============================================================
-- ServiPal Marketing Bot - Drop All Schema Objects
-- ============================================================
-- Run this in Supabase SQL Editor if you want a full reset
-- before recreating the schema with app/db/script.sql.

-- Drop views first
DROP VIEW IF EXISTS daily_message_stats;
DROP VIEW IF EXISTS daily_lead_summary;

-- Drop triggers before dropping tables/functions
DROP TRIGGER IF EXISTS update_social_posts_updated_at ON social_posts;
DROP TRIGGER IF EXISTS update_email_messages_updated_at ON email_messages;
DROP TRIGGER IF EXISTS update_messages_updated_at ON messages;
DROP TRIGGER IF EXISTS update_leads_updated_at ON leads;

-- Drop tables in dependency order
DROP TABLE IF EXISTS messages;
DROP TABLE IF EXISTS email_messages;
DROP TABLE IF EXISTS social_posts;
DROP TABLE IF EXISTS logs;
DROP TABLE IF EXISTS leads;

-- Drop helper function
DROP FUNCTION IF EXISTS update_updated_at_column();

-- Optional: keep the extension if you use UUIDs elsewhere
-- DROP EXTENSION IF EXISTS "uuid-ossp";
