-- ============================================================
-- ServiPal Marketing Bot - Schema Verification Queries
-- ============================================================
-- Run this after app/db/script.sql to verify the tables/columns
-- the app expects are present.

-- Tables that should exist
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('leads', 'messages', 'email_messages', 'social_posts', 'logs')
ORDER BY table_name;

-- Leads columns the app expects, including `source`
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'leads'
ORDER BY ordinal_position;

-- Messages columns
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'messages'
ORDER BY ordinal_position;

-- Social posts columns
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'social_posts'
ORDER BY ordinal_position;

-- Email messages columns
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'email_messages'
ORDER BY ordinal_position;

-- Logs columns
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'logs'
ORDER BY ordinal_position;
