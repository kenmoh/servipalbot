#!/usr/bin/env python3
"""
ServiPal lead maintenance.

Usage (run from server/):
  uv run python scripts/maintain_leads.py --stats
  uv run python scripts/maintain_leads.py --classify-backfill 100
  uv run python scripts/maintain_leads.py --fix-invalid-status     # 'read' -> 'contacted'
  uv run python scripts/maintain_leads.py --dry-run --fix-invalid-status

--stats: counts by status/source and contactability.
--classify-backfill N: run AI classification over up to N unclassified leads
  (skips leads that already have quality_score).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai_engine.engine import AIEngine  # noqa: E402
from app.db.database import SupabaseClient  # noqa: E402


def _is_ready(db: SupabaseClient) -> bool:
    if not db.enabled:
        print("Supabase is not configured - cannot run maintenance.")
        return False
    return True


async def show_stats(db: SupabaseClient) -> None:
    try:
        result = (
            db.client.table("leads")
            .select("id,status,source,phone,email,website,quality_score")
            .limit(5000)
            .execute()
        )
    except Exception as e:
        print(f"Failed to fetch leads: {e}")
        return

    rows: List[Dict[str, Any]] = result.data or []
    if not rows:
        print("No leads found.")
        return

    by_status = Counter(r.get("status") or "null" for r in rows)
    by_source = Counter(r.get("source") or "null" for r in rows)
    has_phone = sum(1 for r in rows if r.get("phone"))
    has_email = sum(1 for r in rows if r.get("email"))
    has_site = sum(1 for r in rows if r.get("website"))
    classified = sum(1 for r in rows if r.get("quality_score") is not None)

    total = len(rows)
    print(f"Total leads (up to 5000): {total}")
    print("By status:", dict(by_status))
    print("By source:", dict(by_source))
    print(
        f"With phone: {has_phone} ({has_phone * 100 // total}%) | "
        f"email: {has_email} ({has_email * 100 // total}%) | "
        f"website: {has_site} ({has_site * 100 // total}%) | "
        f"AI-classified: {classified} ({classified * 100 // total}%)"
    )


async def fix_invalid_status(db: SupabaseClient, dry_run: bool) -> None:
    """Leads whose status is outside the allowed set ('read') get moved to 'contacted'."""
    try:
        result = (
            db.client.table("leads")
            .select("id,name,status")
            .eq("status", "read")
            .limit(1000)
            .execute()
        )
    except Exception as e:
        print(f"Failed to fetch leads with status 'read': {e}")
        return

    rows = result.data or []
    if not rows:
        print("No leads with status 'read' - nothing to fix.")
        return

    print(f"Found {len(rows)} leads with status 'read'")
    fixed = 0
    for row in rows:
        if dry_run:
            print(f"  [dry-run] would move '{row.get('name')}' -> 'contacted'")
            fixed += 1
            continue
        try:
            db.client.table("leads").update({"status": "contacted"}).eq("id", row["id"]).execute()
            fixed += 1
        except Exception as e:
            print(f"  Failed to update {row.get('id')}: {e}")

    print(f"{'Would fix' if dry_run else 'Fixed'} {fixed} lead(s).")


async def classify_backfill(db: SupabaseClient, ai: AIEngine, max_leads: int) -> int:
    """Classify unclassified leads (quality_score IS NULL) using the AI engine."""
    if not ai.enabled:
        print("AI engine is not configured - cannot classify leads.")
        return 0

    try:
        result = (
            db.client.table("leads")
            .select("id,name,category,location,phone,rating,review_count,source,quality_score")
            .is_("quality_score", "null")
            .limit(max_leads)
            .execute()
        )
    except Exception as e:
        print(f"Failed to fetch unclassified leads: {e}")
        return 0

    rows = result.data or []
    if not rows:
        print("No unclassified leads found - nothing to do.")
        return 0

    print(f"Classifying {len(rows)} unclassified leads...")
    classified = 0
    for row in rows:
        try:
            classification = await ai.classify_lead(
                lead_id=str(row["id"]),
                name=row.get("name", ""),
                category=row.get("category", ""),
                location=row.get("location", ""),
                phone=row.get("phone", ""),
                rating=row.get("rating"),
                review_count=row.get("review_count"),
                source=row.get("source", "unknown"),
            )
            if classification:
                db.client.table("leads").update({
                    "status": "new" if classification.priority != "skip" else "unsubscribed",
                    "quality_score": classification.quality_score,
                    "priority": classification.priority,
                    "category": classification.category,
                }).eq("id", row["id"]).execute()
                classified += 1
        except Exception as e:
            print(f"  Failed on {row.get('id')}: {e}")
        await asyncio.sleep(0.5)

    print(f"Classified {classified}/{len(rows)} leads.")
    return classified


async def main() -> None:
    parser = argparse.ArgumentParser(description="ServiPal lead maintenance")
    parser.add_argument("--stats", action="store_true", help="Show lead statistics")
    parser.add_argument("--classify-backfill", type=int, metavar="N", help="Classify up to N unclassified leads")
    parser.add_argument("--fix-invalid-status", action="store_true", help="Move 'read' status leads to 'contacted'")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without writing")
    args = parser.parse_args()

    if not any([args.stats, args.classify_backfill, args.fix_invalid_status]):
        parser.print_help()
        return

    db = SupabaseClient()
    if not _is_ready(db):
        return

    if args.stats:
        await show_stats(db)
    if args.fix_invalid_status:
        await fix_invalid_status(db, dry_run=args.dry_run)
    if args.classify_backfill:
        ai = AIEngine()
        try:
            await classify_backfill(db, ai, max_leads=args.classify_backfill)
        finally:
            await ai.close()


if __name__ == "__main__":
    asyncio.run(main())
