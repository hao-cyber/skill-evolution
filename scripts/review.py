#!/usr/bin/env python3
"""Submit or query reviews for skills in the Skill Evolution registry."""

import argparse
import json
import os
import sys
import urllib.parse
from pathlib import Path

# Add scripts/ to path so lib/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import get_publisher_key
from lib.supabase import supabase_get, supabase_rpc


def parse_args():
    p = argparse.ArgumentParser(description="Review community skills in the registry")
    sub = p.add_subparsers(dest="command", required=True)

    # Submit a review
    submit = sub.add_parser("submit", help="Submit a review for a skill")
    submit.add_argument("--skill-name", required=True, help="Skill name")
    submit.add_argument("--variant", default="base", help="Skill variant")
    submit.add_argument("--score", type=int, required=True, choices=[1, 2, 3, 4, 5], help="Rating 1-5")
    submit.add_argument("--review", default="", help="Review text")
    submit.add_argument("--context", default="", help="Task context where skill was used")
    submit.add_argument("--reviewer", default="agent", help="Reviewer identifier")

    # List reviews for a skill
    ls = sub.add_parser("list", help="List reviews for a skill")
    ls.add_argument("--skill-name", required=True, help="Skill name")
    ls.add_argument("--variant", default=None, help="Filter by variant")
    ls.add_argument("--limit", type=int, default=10, help="Max results (max 100)")

    # Get average score
    stats = sub.add_parser("stats", help="Get review stats for a skill")
    stats.add_argument("--skill-name", required=True, help="Skill name")

    return p.parse_args()


def get_skill_id(name, variant="base"):
    """Look up skill ID by name and variant."""
    name_q = urllib.parse.quote(name)
    variant_q = urllib.parse.quote(variant)
    results = supabase_get(f"skills?name=eq.{name_q}&variant=eq.{variant_q}&select=id")
    if not results:
        print(f"ERROR: skill not found: {name}@{variant}", file=sys.stderr)
        sys.exit(1)
    return results[0]["id"]


def cmd_submit(args):
    skill_id = get_skill_id(args.skill_name, args.variant)
    publisher_key = get_publisher_key()
    if not publisher_key:
        print("ERROR: publisher key required — publish a skill first to register", file=sys.stderr)
        sys.exit(1)
    result = supabase_rpc("submit_review", {
        "p_skill_id": skill_id,
        "p_reviewer": args.reviewer,
        "p_score": args.score,
        "p_api_key": publisher_key,
        "p_review_text": args.review or None,
        "p_task_context": args.context or None,
    }) or {}
    output = {
        "status": "ok",
        "skill": f"{args.skill_name}@{args.variant}",
        "score": args.score,
        "review_id": result.get("id", "submitted"),
    }
    print(json.dumps(output, ensure_ascii=False))


def cmd_list(args):
    name_q = urllib.parse.quote(args.skill_name)

    # Get skill IDs for this name
    variant_filter = f"&variant=eq.{urllib.parse.quote(args.variant)}" if args.variant else ""
    skills = supabase_get(f"skills?name=eq.{name_q}{variant_filter}&select=id,variant")
    if not skills:
        print(json.dumps({"status": "not_found", "name": args.skill_name}))
        return

    limit = min(args.limit, 100)
    skill_ids = [s["id"] for s in skills]

    # Validate IDs are UUIDs to prevent PostgREST injection
    import re as _re
    for sid in skill_ids:
        if not _re.match(r'^[0-9a-f\-]{36}$', sid):
            print(f"ERROR: invalid skill ID format: {sid}", file=sys.stderr)
            sys.exit(1)

    reviews = supabase_get(
        f"skill_reviews?skill_id=in.({','.join(skill_ids)})&order=created_at.desc&limit={limit}&select=score,review_text,task_context,reviewer,created_at"
    )

    output = {
        "skill": args.skill_name,
        "review_count": len(reviews),
        "reviews": reviews,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


def cmd_stats(args):
    name_q = urllib.parse.quote(args.skill_name)
    skills = supabase_get(f"skills?name=eq.{name_q}&select=id,variant,installs")
    if not skills:
        print(json.dumps({"status": "not_found", "name": args.skill_name}))
        return

    all_reviews = []
    for skill in skills:
        reviews = supabase_get(
            f"skill_reviews?skill_id=eq.{skill['id']}&select=score"
        )
        scores = [r["score"] for r in reviews]
        skill["review_count"] = len(scores)
        skill["avg_score"] = round(sum(scores) / len(scores), 1) if scores else None
        all_reviews.extend(scores)

    total_scores = all_reviews
    output = {
        "skill": args.skill_name,
        "total_reviews": len(total_scores),
        "avg_score": round(sum(total_scores) / len(total_scores), 1) if total_scores else None,
        "variants": [
            {
                "variant": s["variant"],
                "installs": s["installs"],
                "review_count": s["review_count"],
                "avg_score": s["avg_score"],
            }
            for s in skills
        ],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


def main():
    args = parse_args()
    if args.command == "submit":
        cmd_submit(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "stats":
        cmd_stats(args)


if __name__ == "__main__":
    main()
