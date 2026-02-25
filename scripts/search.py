#!/usr/bin/env python3
"""Search the Skill Evolution registry for community skills."""

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path

# Add scripts/ to path so lib/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.supabase import supabase_get, supabase_rpc
from lib.embedding import compute_embedding


def parse_args():
    p = argparse.ArgumentParser(description="Search community skills in the registry")
    p.add_argument("--query", "-q", default=None, help="Search keywords")
    p.add_argument("--tag", "-t", default=None, help="Filter by tag")
    p.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    p.add_argument("--offset", type=int, default=0, help="Skip first N results for pagination (default: 0)")
    p.add_argument("--sort", choices=["installs", "updated", "name"], default="installs", help="Sort order (default: installs)")
    p.add_argument("--detail", default=None, help="Show full detail for a specific skill name")
    p.add_argument("--list-all", action="store_true", help="List all skills (no search filter)")
    p.add_argument("--no-semantic", action="store_true", help="Disable vector similarity search (force full-text only)")
    p.add_argument("--include-unaudited", action="store_true", help="Include skills that haven't passed security audit")
    return p.parse_args()


SORT_MAP = {
    "installs": "installs.desc",
    "updated": "updated_at.desc",
    "name": "name.asc",
}


def search_skills(query=None, tag=None, limit=10, offset=0, sort="installs", audited_only=True):
    """Search skills using full-text search, or list all if no query."""
    order = SORT_MAP.get(sort, "installs.desc")

    params = {
        "select": "name,variant,description,author,installs,forks,tags,audited_at,created_at,updated_at",
        "order": order,
        "limit": str(limit),
        "offset": str(offset),
    }

    if audited_only:
        params["audited_at"] = "not.is.null"

    if query:
        # Allowlist: keep only alphanumeric, CJK, and whitespace to prevent tsquery injection
        sanitized = re.sub(r'[^\w\u4e00-\u9fff\s]', ' ', query)
        words = [w for w in sanitized.strip().split() if w]
        if words:
            fts_query = " & ".join(words)
            params["fts"] = f"fts.{fts_query}"

    if tag:
        params["tags"] = f"cs.{{{tag}}}"

    query_string = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    return supabase_get(f"skills?{query_string}")


def get_skill_detail(name):
    """Get all variants of a skill by name."""
    params = {
        "select": "name,variant,description,author,installs,forks,tags,requires_env,requires_runtime,depends_on,skill_md,audited_at,created_at,updated_at",
        "name": f"eq.{name}",
        "order": "installs.desc",
    }
    query_string = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    return supabase_get(f"skills?{query_string}")


def semantic_search(query, limit=10, audited_only=True, tag=None):
    """Search skills by vector similarity via Supabase RPC match_skills.

    Returns None (triggering FTS fallback) when:
    - No embedding provider is configured
    - The embedding API call fails
    - The Supabase RPC call fails
    - Top result similarity is below 0.5 (likely incomplete embeddings in DB)
    """
    embedding = compute_embedding(query)
    if not embedding:
        return None

    rpc_payload = {
        "query_embedding": embedding,
        "match_count": limit,
        "match_threshold": 0.5,
    }
    results = supabase_rpc("match_skills", rpc_payload, exit_on_error=False)
    if results is None:
        print("WARNING: semantic search failed, falling back to FTS", file=sys.stderr)
        return None

    # Post-filter: audited_only and tag (RPC doesn't support these natively)
    if audited_only:
        results = [r for r in results if r.get("audited_at") is not None]
    if tag:
        results = [r for r in results if tag in (r.get("tags") or [])]

    # Quality gate: if the best match has low similarity, the DB likely
    # has incomplete embeddings — fall back to FTS which covers all skills.
    if not results or results[0].get("similarity", 0) < 0.6:
        print("WARNING: low semantic similarity, falling back to FTS", file=sys.stderr)
        return None

    return results


def main():
    args = parse_args()

    args.limit = min(args.limit, 100)

    if args.detail:
        results = get_skill_detail(args.detail)
        if not results:
            print(json.dumps({"status": "not_found", "name": args.detail}))
            return

        # Show variants with truncated skill_md
        output = {
            "name": args.detail,
            "variant_count": len(results),
            "variants": [],
        }
        for r in results:
            variant = {
                "variant": r["variant"],
                "author": r["author"],
                "description": r["description"][:200],
                "installs": r["installs"],
                "forks": r["forks"],
                "tags": r["tags"],
                "requires_env": r["requires_env"],
                "requires_runtime": r["requires_runtime"],
                "depends_on": r["depends_on"],
                "skill_md_lines": len(r.get("skill_md", "").splitlines()),
                "audited": r.get("audited_at") is not None,
                "updated_at": r["updated_at"],
            }
            output["variants"].append(variant)

        print(json.dumps(output, indent=2, ensure_ascii=False))
        return

    if not args.query and not args.list_all:
        print("ERROR: must provide --query or --list-all", file=sys.stderr)
        sys.exit(1)

    # Semantic search: auto-use when a query is given and an embedding provider is available
    results = None
    audited_only = not args.include_unaudited
    if not args.no_semantic and args.query:
        results = semantic_search(args.query, args.limit, audited_only=audited_only, tag=args.tag)

    if results is None:
        audited_only = not args.include_unaudited
        results = search_skills(args.query, args.tag, args.limit, args.offset, args.sort, audited_only)

    if not results:
        print(json.dumps({"status": "no_results", "query": args.query or "*", "results": []}))
        return

    # Group by name to show variant counts
    by_name = {}
    for r in results:
        name = r["name"]
        if name not in by_name:
            by_name[name] = {
                "name": name,
                "description": r["description"][:150],
                "top_variant": r["variant"],
                "author": r["author"],
                "installs": r["installs"],
                "tags": r["tags"],
                "audited": r.get("audited_at") is not None,
                "variants": [],
            }
        by_name[name]["variants"].append(r["variant"])

    output = {
        "query": args.query,
        "total": len(by_name),
        "offset": args.offset,
        "has_more": len(results) == args.limit,
        "results": list(by_name.values()),
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
