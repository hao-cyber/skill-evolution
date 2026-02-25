#!/usr/bin/env python3
"""Publish a local skill to the Skill Evolution registry (Supabase)."""

import argparse
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path

# Add scripts/ to path so lib/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import get_publisher_key, save_publisher_key
from lib.supabase import supabase_get, supabase_rpc


def parse_args():
    p = argparse.ArgumentParser(description="Publish a skill to the community registry")
    p.add_argument("--skill-name", required=True, help="Name of the skill directory under .claude/skills/")
    p.add_argument("--variant", default="base", help="Variant name (default: base, use author name for forks)")
    p.add_argument("--author", default=None, help="Author identifier (default: from git config)")
    p.add_argument("--skills-dir", default=None, help="Path to .claude/skills/ (auto-detected)")
    p.add_argument("--yes", action="store_true", help="Actually publish (without this flag, only preview is shown)")
    return p.parse_args()


def find_skills_dir(override=None):
    if override:
        return Path(override)
    # Walk up from cwd looking for .claude/skills/
    cwd = Path.cwd()
    for d in [cwd, *cwd.parents]:
        candidate = d / ".claude" / "skills"
        if candidate.is_dir():
            return candidate
    print("ERROR: cannot find .claude/skills/ directory", file=sys.stderr)
    sys.exit(1)


def get_author():
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "config", "user.name"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "anonymous"


def parse_frontmatter(skill_md_text):
    """Extract YAML frontmatter from SKILL.md (supports multi-line values)."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", skill_md_text, re.DOTALL)
    if not m:
        return {}
    import yaml
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}


def collect_file_tree(skill_dir):
    """Collect all files in the skill directory into a flat dict {relative_path: content}."""
    tree = {}
    for fpath in sorted(skill_dir.rglob("*")):
        if fpath.is_file():
            rel = str(fpath.relative_to(skill_dir))
            # Skip __pycache__, .pyc, etc
            if "__pycache__" in rel or rel.endswith(".pyc"):
                continue
            try:
                tree[rel] = fpath.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Binary file — store placeholder
                tree[rel] = f"[binary file, {fpath.stat().st_size} bytes]"
    return tree


def sanitize_check(file_tree):
    """Check for secrets/hardcoded paths. Returns list of warnings."""
    warnings = []
    secret_patterns = [
        (r"(?:sk|api|token|key|secret|password)[-_]?\w*\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{20,}", "possible API key/secret"),
        (r"/home/\w+/", "hardcoded home path"),
    ]
    for path, content in file_tree.items():
        for pattern, desc in secret_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                for m in matches:
                    # Skip common false positives
                    if "SUPABASE" in m or "TASKPOOL" in m or "$HOME" in m or "${HOME}" in m:
                        continue
                    warnings.append(f"{path}: {desc} — {m[:60]}")
    return warnings


def extract_tags(description, name):
    """Auto-extract tags from description and name."""
    tags = set()
    # Add name parts
    for part in re.split(r"[-_]", name):
        if len(part) > 2:
            tags.add(part.lower())
    return sorted(tags)


def extract_requires(file_tree):
    """Scan scripts for env var requirements and runtime dependencies."""
    env_vars = set()
    runtimes = set()
    for path, content in file_tree.items():
        if not path.startswith("scripts/"):
            continue
        # Env vars: os.environ["X"], os.getenv("X"), $X
        for m in re.findall(r'os\.(?:environ|getenv)\s*[\[(]\s*["\'](\w+)', content):
            if not m.startswith("TASKPOOL_"):
                env_vars.add(m)
        # Runtime: shebang
        if content.startswith("#!/"):
            first_line = content.split("\n")[0]
            if "python" in first_line:
                runtimes.add("uv")
            elif "node" in first_line:
                runtimes.add("node")
    return sorted(env_vars), sorted(runtimes)


def ensure_publisher_key(author):
    """Get or auto-register a publisher key. Returns the UUID key string."""
    key = get_publisher_key()
    if key:
        return key

    # Auto-register on first publish
    print(f"First publish — registering author '{author}'...", file=sys.stderr)
    result = supabase_rpc("register_publisher", {"p_author": author})
    if not result or "api_key" not in result:
        print("ERROR: publisher registration failed", file=sys.stderr)
        sys.exit(1)

    new_key = result["api_key"]
    save_publisher_key(new_key)
    print(f"Publisher key saved.", file=sys.stderr)
    return new_key


def main():
    args = parse_args()
    skills_dir = find_skills_dir(args.skills_dir)
    skill_dir = skills_dir / args.skill_name

    if not skill_dir.is_dir():
        print(f"ERROR: skill directory not found: {skill_dir}", file=sys.stderr)
        sys.exit(1)

    skill_md_path = skill_dir / "SKILL.md"
    if not skill_md_path.exists():
        print(f"ERROR: SKILL.md not found in {skill_dir}", file=sys.stderr)
        sys.exit(1)

    # Read and parse
    skill_md = skill_md_path.read_text(encoding="utf-8")
    fm = parse_frontmatter(skill_md)
    name = fm.get("name", args.skill_name)
    description = fm.get("description", "")

    if not description:
        print("ERROR: SKILL.md must have a 'description' in frontmatter", file=sys.stderr)
        sys.exit(1)

    # Input validation — prevent oversized or malformed payloads
    if not re.match(r'^[a-z0-9][a-z0-9\-]{0,62}$', name):
        print(f"ERROR: invalid skill name '{name}' — must be lowercase alphanumeric + hyphens, 1-63 chars", file=sys.stderr)
        sys.exit(1)
    if not re.match(r'^[a-z0-9][a-z0-9\-]{0,62}$', args.variant):
        print(f"ERROR: invalid variant '{args.variant}' — must be lowercase alphanumeric + hyphens, 1-63 chars", file=sys.stderr)
        sys.exit(1)
    if len(description) > 1000:
        print(f"ERROR: description too long ({len(description)} chars, max 1000)", file=sys.stderr)
        sys.exit(1)

    # Collect files
    file_tree = collect_file_tree(skill_dir)

    # Quality checks
    line_count = len(skill_md.splitlines())
    if line_count > 300:
        print(f"WARNING: SKILL.md is {line_count} lines (recommended ≤300)", file=sys.stderr)

    # Sanitize check
    warnings = sanitize_check(file_tree)
    if warnings:
        print("SANITIZE WARNINGS:", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)

    # Validate file_tree size
    total_size = sum(len(v) for v in file_tree.values())
    if len(file_tree) > 50:
        print(f"ERROR: too many files ({len(file_tree)}, max 50)", file=sys.stderr)
        sys.exit(1)
    if total_size > 500_000:
        print(f"ERROR: total content too large ({total_size} bytes, max 500KB)", file=sys.stderr)
        sys.exit(1)

    # Extract metadata
    author = args.author or get_author()
    tags = extract_tags(description, name)
    if len(tags) > 15:
        tags = tags[:15]
    requires_env, requires_runtime = extract_requires(file_tree)

    # Build payload
    payload = {
        "name": name,
        "variant": args.variant,
        "description": description,
        "author": author,
        "tags": tags,
        "skill_md": skill_md,
        "file_tree": file_tree,
        "requires_env": requires_env,
        "requires_tools": [],
        "requires_runtime": requires_runtime,
        "depends_on": fm.get("depends_on", []) or [],
    }

    # Default: show preview. Require --yes to actually publish.
    preview = {
        "name": name,
        "variant": args.variant,
        "author": author,
        "description": description[:100],
        "tags": tags,
        "files": list(file_tree.keys()),
        "file_count": len(file_tree),
        "skill_md_lines": line_count,
        "requires_env": requires_env,
        "requires_runtime": requires_runtime,
        "depends_on": fm.get("depends_on", []) or [],
        "sanitize_warnings": warnings,
    }

    if not args.yes:
        preview["action"] = "preview"
        preview["hint"] = "Re-run with --yes to publish"
        print(json.dumps(preview, indent=2, ensure_ascii=False))
        return

    # Authenticate publisher (auto-registers on first publish)
    publisher_key = ensure_publisher_key(author)

    # Determine variant — fork logic: if another author's base exists, use author as variant
    actual_variant = args.variant
    parent_id = None
    name_q = urllib.parse.quote(name)
    variant_q = urllib.parse.quote(args.variant)
    existing = supabase_get(
        f"skills?name=eq.{name_q}&variant=eq.{variant_q}&select=id,author"
    )

    if existing and existing[0]["author"] != author:
        # Fork: use author name as variant
        actual_variant = author
        parent_id = existing[0]["id"]
        # Increment fork counter on the parent skill (best-effort)
        supabase_rpc("increment_forks", {"skill_id": parent_id}, exit_on_error=False)

    # Build RPC params (match publish_skill function signature)
    rpc_params = {
        "p_name": name,
        "p_variant": actual_variant,
        "p_description": description,
        "p_author": author,
        "p_api_key": publisher_key,
        "p_tags": tags,
        "p_skill_md": skill_md,
        "p_file_tree": file_tree,
        "p_requires_env": requires_env,
        "p_requires_tools": [],
        "p_requires_runtime": requires_runtime,
        "p_depends_on": fm.get("depends_on", []) or [],
    }
    if parent_id:
        rpc_params["p_parent_id"] = parent_id

    # Publish via server-side RPC (uses anon key, no service key needed)
    result = supabase_rpc("publish_skill", rpc_params) or {}

    output = {
        "status": "ok",
        "action": result.get("action", "published"),
        "id": result.get("id", "unknown"),
        "name": name,
        "variant": actual_variant,
        "file_count": len(file_tree),
    }
    if actual_variant != args.variant:
        output["note"] = f"forked as variant '{actual_variant}' (original by different author)"
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
