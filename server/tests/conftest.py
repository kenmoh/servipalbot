"""Shared pytest configuration."""
import os
import sys
from pathlib import Path

# Make `app` importable when running pytest from server/
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Settings requires Supabase credentials; provide safe dummies if .env is absent
# (on the dev machine server/.env exists, so this only matters for CI).
os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "dummy-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "dummy-service-key")
os.environ.setdefault("SERPAPI_KEY", "dummy-serpapi-key")
