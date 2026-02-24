#!/usr/bin/env python3
"""Install a skill from the Skill Evolution registry to local .claude/skills/."""

import argparse
import json
import os
import sys
import urllib.parse
from pathlib import Path

# Add scripts/ to path so lib/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.supabase import supabase_get, supabase_rpc


def parse_args():
    p = argparse.ArgumentParser(description="Install a community skill from the registry")
    p.add_argument("--name", required=True, help="Skill name to install")
    p.add_argument("--variant", default="base", help="Variant to install (default: base)")
    p.add_argument("--skills-dir", default=None, help="Path to .claude/skills/ (auto-detected)")
    p.add_argument("--force", action="store_true", help="Overwrite existing skill directory")
    p.add_argument("--no-deps", action="store_true", help="Skip automatic dependency installation")
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


def install_skill(name, variant, skills_dir, force=False, _visited=None):
    """Install a single skill. Returns result dict. Raises SystemExit on fatal error.

    _visited tracks already-processed skills to prevent circular deps.
    """
    if _visited is None:
        _visited = set()

    dep_key = f"{name}@{variant}"
    if dep_key in _visited:
        return {"status": "skipped", "name": name, "variant": variant, "reason": "circular dependency"}
    _visited.add(dep_key)

    target_dir = skills_dir / name

    # Check if already exists
    if target_dir.exists() and not force:
        return {"status": "skipped", "name": name, "variant": variant, "reason": "already installed"}

    # Fetch skill from registry
    name_q = urllib.parse.quote(name)
    variant_q = urllib.parse.quote(variant)
    results = supabase_get(
        f"skills?name=eq.{name_q}&variant=eq.{variant_q}&select=id,name,variant,skill_md,file_tree,requires_env,requires_runtime,depends_on"
    )

    if not results:
        return {"status": "error", "name": name, "variant": variant, "reason": "not found in registry"}

    skill = results[0]
    file_tree = skill.get("file_tree", {})

    if not file_tree:
        return {"status": "error", "name": name, "variant": variant, "reason": "no file_tree in registry"}

    # Write files
    files_written = []
    resolved_target = target_dir.resolve()
    for rel_path, content in file_tree.items():
        if content.startswith("[binary file,"):
            print(f"WARNING: skipping binary file: {rel_path}", file=sys.stderr)
            continue

        fpath = (target_dir / rel_path).resolve()
        # Prevent path traversal — all files must stay inside target_dir
        if not fpath.is_relative_to(resolved_target):
            print(f"ERROR: path traversal blocked: {rel_path}", file=sys.stderr)
            sys.exit(1)

        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content, encoding="utf-8")
        files_written.append(rel_path)

    # Make scripts executable
    script_dir = target_dir / "scripts"
    if script_dir.is_dir():
        for script in script_dir.iterdir():
            if script.is_file():
                script.chmod(0o755)

    # Increment install count (best-effort)
    supabase_rpc("increment_installs", {"skill_id": skill["id"]}, exit_on_error=False)

    # Check env dependencies
    missing_env = []
    for env_var in skill.get("requires_env", []):
        if not os.environ.get(env_var):
            missing_env.append(env_var)

    output = {
        "status": "ok",
        "name": name,
        "variant": variant,
        "installed_to": str(target_dir),
        "files_written": files_written,
        "file_count": len(files_written),
    }

    if missing_env:
        output["missing_env"] = missing_env
        output["warning"] = f"Missing environment variables: {', '.join(missing_env)}"

    if skill.get("requires_runtime"):
        output["requires_runtime"] = skill["requires_runtime"]

    # Auto-install dependencies
    deps = skill.get("depends_on") or []
    if deps:
        output["depends_on"] = deps
        dep_results = []
        for dep_name in deps:
            # Already installed locally? skip
            if (skills_dir / dep_name).exists():
                dep_results.append({"status": "skipped", "name": dep_name, "reason": "already installed"})
                continue
            print(f"Installing dependency: {dep_name}@base ...", file=sys.stderr)
            dep_result = install_skill(dep_name, "base", skills_dir, force=False, _visited=_visited)
            dep_results.append(dep_result)
        output["deps_installed"] = dep_results

    return output


def main():
    args = parse_args()
    skills_dir = find_skills_dir(args.skills_dir)

    if args.no_deps:
        # Old behavior: install single skill, fail hard on errors
        result = install_skill(args.name, args.variant, skills_dir, args.force)
        if result["status"] == "error":
            print(f"ERROR: {result['name']}@{result['variant']}: {result['reason']}", file=sys.stderr)
            sys.exit(1)
        # Strip dep auto-install from output (--no-deps)
        result.pop("deps_installed", None)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        result = install_skill(args.name, args.variant, skills_dir, args.force)
        if result["status"] == "error":
            print(f"ERROR: {result['name']}@{result['variant']}: {result['reason']}", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
