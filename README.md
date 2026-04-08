# ServiPal Workspace

This repository is now split into two apps:

- `server/`: FastAPI backend for scraping, lead storage, WhatsApp, email drafts, and automation
- `client/`: Next.js dashboard for managing the bot

## Structure

```text
servipal-bot/
├── client/
├── server/
├── .uv-cache/
└── README.md
```

## Server

The backend lives in [`server/`](C:/Users/kenne/Desktop/servipal-bot/server).

### Run it

```powershell
cd server
$env:UV_CACHE_DIR='..\.uv-cache'
uv sync --python 3.12
uv run uvicorn app.main:app --reload
```

### Setup

1. Add backend secrets to `server/.env`
2. Run the base Supabase schema from `server/app/db/script.sql`
3. Run the email migration from `server/app/db/add_email_messages.sql`

### Helpful checks

```powershell
cd server
$env:UV_CACHE_DIR='..\.uv-cache'
uv run --no-sync python scripts/check_integrations.py
```

## Client

The dashboard lives in [`client/`](C:/Users/kenne/Desktop/servipal-bot/client).

### Run it

```powershell
cd client
copy .env.example .env.local
npm.cmd run dev
```

By default the dashboard expects the API at `http://localhost:8000`.

## Dashboard Features

- health and integration visibility
- lead review
- draft-first email workflow
- scrape controls
- recent logs and outbound email history

## Notes

- Email sending is draft-first: generate drafts first, then send selected draft IDs
- Scraped leads are still stored even when they do not have email addresses yet
- If `USE_SERPAPI=false`, the backend falls back to BeautifulSoup for direct Google scraping
