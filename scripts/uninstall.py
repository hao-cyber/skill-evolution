#!/usr/bin/env python3
"""Uninstall a skill from the local .claude/skills/ directory."""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Uninstall a local skill")
    p.add_argument("--name", required=True, help="Skill name to uninstall")
    p.add_argument("--skills-dir", default=None, help="Path to .claude/skills/ (auto-detected)")
    p.add_argument("--yes", action="store_true", help="Skip confirmation and delete immediately")
    return p.parse_args()


def find_skills_dir(override=None):
    if override:
        return Path(override)
    cwd = Path.cwd()
    for d in [cwd, *cwd.parents]:
        candidate = d / ".claude" / "skills"
        if candidate.is_dir():
            return candidate
    print("ERROR: cannot find .claude/skills/ directory", file=sys.stderr)
    sys.exit(1)


def main():
    args = parse_args()
    if not re.match(r'^[a-z0-9][a-z0-9\-]{0,62}$', args.name):
        print(f"ERROR: invalid skill name: {args.name}", file=sys.stderr)
        sys.exit(1)
    skills_dir = find_skills_dir(args.skills_dir)
    skill_dir = skills_dir / args.name

    if not skill_dir.is_dir():
        print(f"ERROR: skill not found: {skill_dir}", file=sys.stderr)
        sys.exit(1)

    # Collect files for preview
    files = sorted(str(f.relative_to(skill_dir)) for f in skill_dir.rglob("*") if f.is_file())

    if not args.yes:
        # Preview mode
        output = {
            "action": "preview",
            "skill": args.name,
            "path": str(skill_dir),
            "files": files,
            "file_count": len(files),
            "hint": "Re-run with --yes to delete",
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return

    # Delete
    shutil.rmtree(skill_dir)
    output = {
        "status": "ok",
        "skill": args.name,
        "deleted_from": str(skill_dir),
        "file_count": len(files),
    }
    print(json.dumps(output, ensure_ascii=False))
    print("HINT: check if any env vars in .env are no longer needed", file=sys.stderr)


if __name__ == "__main__":
    main()
