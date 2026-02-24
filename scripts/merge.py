#!/usr/bin/env python3
"""Scaffold for merging two skill variants. Downloads, diffs, and publishes merged result."""

import argparse
import json
import sys
import tempfile
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.supabase import supabase_get


def parse_args():
    p = argparse.ArgumentParser(
        description="Merge two skill variants: download, diff, and prepare a workspace"
    )
    sub = p.add_subparsers(dest="command", required=True)

    # merge prepare — download two variants and show diff
    prep = sub.add_parser("prepare", help="Download two variants and produce a diff report")
    prep.add_argument("--name", required=True, help="Skill name")
    prep.add_argument("--variants", required=True, help="Comma-separated variant pair (e.g. base,alice)")
    prep.add_argument("--workspace", default=None, help="Workspace directory (default: temp dir)")

    # merge diff — show diff between two already-downloaded variants
    diff = sub.add_parser("diff", help="Show diff between two variant directories")
    diff.add_argument("--dir-a", required=True, help="Path to first variant directory")
    diff.add_argument("--dir-b", required=True, help="Path to second variant directory")

    # merge publish — publish the merged result from workspace
    pub = sub.add_parser("publish", help="Publish merged skill from workspace")
    pub.add_argument("--workspace", required=True, help="Workspace directory containing merged skill")
    pub.add_argument("--name", required=True, help="Skill name")
    pub.add_argument("--variant", default="merged", help="Variant name for the merge (default: merged)")
    pub.add_argument("--yes", action="store_true", help="Actually publish (without this, only preview)")

    return p.parse_args()


def fetch_variant(name, variant):
    """Fetch a skill variant from the registry. Returns dict or exits."""
    name_q = urllib.parse.quote(name)
    variant_q = urllib.parse.quote(variant)
    results = supabase_get(
        f"skills?name=eq.{name_q}&variant=eq.{variant_q}"
        f"&select=id,name,variant,author,description,tags,skill_md,file_tree,depends_on"
    )
    if not results:
        print(f"ERROR: variant '{name}@{variant}' not found in registry", file=sys.stderr)
        sys.exit(1)
    return results[0]


def write_variant(skill, target_dir):
    """Write a skill's file_tree to a local directory."""
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)

    file_tree = skill.get("file_tree", {})
    if isinstance(file_tree, str):
        file_tree = json.loads(file_tree)

    for rel_path, content in file_tree.items():
        fpath = target / rel_path
        # Path traversal protection
        if not fpath.resolve().is_relative_to(target.resolve()):
            print(f"WARNING: skipping path traversal attempt: {rel_path}", file=sys.stderr)
            continue
        fpath.parent.mkdir(parents=True, exist_ok=True)
        if not isinstance(content, str) or content.startswith("[binary file,"):
            continue
        fpath.write_text(content, encoding="utf-8")
        if rel_path.startswith("scripts/"):
            fpath.chmod(0o755)

    return sorted(file_tree.keys())


def compute_diff(dir_a, dir_b, label_a, label_b):
    """Compare two variant directories and classify each file."""
    path_a = Path(dir_a)
    path_b = Path(dir_b)

    files_a = {str(f.relative_to(path_a)) for f in path_a.rglob("*") if f.is_file()}
    files_b = {str(f.relative_to(path_b)) for f in path_b.rglob("*") if f.is_file()}

    all_files = sorted(files_a | files_b)
    report = {"complementary": [], "conflicting": [], "redundant": [], "only_a": [], "only_b": []}

    for f in all_files:
        in_a = f in files_a
        in_b = f in files_b

        if in_a and not in_b:
            report["only_a"].append(f)
        elif in_b and not in_a:
            report["only_b"].append(f)
        else:
            content_a = (path_a / f).read_text(encoding="utf-8", errors="replace")
            content_b = (path_b / f).read_text(encoding="utf-8", errors="replace")
            if content_a == content_b:
                report["redundant"].append(f)
            else:
                # Both modified the same file differently
                report["conflicting"].append(f)

    # Files only in one variant are complementary (safe to take both)
    report["complementary"] = report.pop("only_a") + report.pop("only_b")

    output = {
        "label_a": label_a,
        "label_b": label_b,
        "summary": {
            "complementary": len(report["complementary"]),
            "conflicting": len(report["conflicting"]),
            "redundant": len(report["redundant"]),
        },
    }
    if report["complementary"]:
        output["complementary"] = {
            "description": "Files unique to one variant — safe to include both",
            "files": report["complementary"],
        }
    if report["conflicting"]:
        output["conflicting"] = {
            "description": "Same file modified differently — agent must decide which version to keep or how to merge",
            "files": report["conflicting"],
        }
    if report["redundant"]:
        output["redundant"] = {
            "description": "Identical in both variants — take either",
            "files": report["redundant"],
        }

    return output


def cmd_prepare(args):
    variants = [v.strip() for v in args.variants.split(",")]
    if len(variants) != 2:
        print("ERROR: --variants must be exactly two comma-separated values (e.g. base,alice)", file=sys.stderr)
        sys.exit(1)

    var_a, var_b = variants

    # Fetch both variants
    print(f"Fetching {args.name}@{var_a}...", file=sys.stderr)
    skill_a = fetch_variant(args.name, var_a)
    print(f"Fetching {args.name}@{var_b}...", file=sys.stderr)
    skill_b = fetch_variant(args.name, var_b)

    # Create workspace
    if args.workspace:
        workspace = Path(args.workspace)
        workspace.mkdir(parents=True, exist_ok=True)
    else:
        workspace = Path(tempfile.mkdtemp(prefix=f"merge-{args.name}-"))

    dir_a = workspace / var_a
    dir_b = workspace / var_b
    merged_dir = workspace / "merged"
    merged_dir.mkdir(parents=True, exist_ok=True)

    # Write both variants
    print(f"Writing {var_a} to {dir_a}...", file=sys.stderr)
    files_a = write_variant(skill_a, dir_a)
    print(f"Writing {var_b} to {dir_b}...", file=sys.stderr)
    files_b = write_variant(skill_b, dir_b)

    # Compute diff
    diff_report = compute_diff(dir_a, dir_b, f"{args.name}@{var_a}", f"{args.name}@{var_b}")

    output = {
        "status": "ok",
        "workspace": str(workspace),
        "variant_a": {"name": f"{args.name}@{var_a}", "path": str(dir_a), "files": files_a,
                       "author": skill_a["author"], "description": skill_a["description"][:200]},
        "variant_b": {"name": f"{args.name}@{var_b}", "path": str(dir_b), "files": files_b,
                       "author": skill_b["author"], "description": skill_b["description"][:200]},
        "merged_dir": str(merged_dir),
        "diff": diff_report,
        "next_steps": [
            f"1. Read conflicting files from both {dir_a} and {dir_b}",
            "2. Decide how to merge each conflicting file (agent judgment)",
            f"3. Write merged result to {merged_dir}",
            f"4. Copy complementary files from both variants to {merged_dir}",
            f"5. Run: merge.py publish --workspace {merged_dir} --name {args.name} --variant merged --yes",
        ],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


def cmd_diff(args):
    dir_a = Path(args.dir_a)
    dir_b = Path(args.dir_b)
    if not dir_a.is_dir():
        print(f"ERROR: directory not found: {dir_a}", file=sys.stderr)
        sys.exit(1)
    if not dir_b.is_dir():
        print(f"ERROR: directory not found: {dir_b}", file=sys.stderr)
        sys.exit(1)

    report = compute_diff(dir_a, dir_b, str(dir_a), str(dir_b))
    print(json.dumps(report, indent=2, ensure_ascii=False))


def cmd_publish(args):
    """Publish merged skill by invoking publish.py on the workspace."""
    import re
    if not re.match(r'^[a-z0-9][a-z0-9\-]{0,62}$', args.name):
        print(f"ERROR: invalid skill name: {args.name}", file=sys.stderr)
        sys.exit(1)
    workspace = Path(args.workspace)
    if not workspace.is_dir():
        print(f"ERROR: workspace not found: {workspace}", file=sys.stderr)
        sys.exit(1)

    skill_md = workspace / "SKILL.md"
    if not skill_md.exists():
        print(f"ERROR: SKILL.md not found in {workspace}. Write the merged SKILL.md first.", file=sys.stderr)
        sys.exit(1)

    # Invoke publish.py with the workspace as skills-dir parent
    # publish.py expects skills-dir/<skill-name>/ structure
    publish_script = Path(__file__).resolve().parent / "publish.py"
    import subprocess
    cmd = [
        sys.executable, str(publish_script),
        "--skill-name", args.name,
        "--variant", args.variant,
        "--skills-dir", str(workspace.parent),
    ]
    # The workspace dir name must match the skill name for publish.py to find it
    # If it doesn't, create a symlink
    expected_dir = workspace.parent / args.name
    created_link = False
    if workspace.name != args.name and not expected_dir.exists():
        expected_dir.symlink_to(workspace)
        created_link = True

    if args.yes:
        cmd.append("--yes")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        sys.exit(result.returncode)
    finally:
        if created_link and expected_dir.is_symlink():
            expected_dir.unlink()


def main():
    args = parse_args()
    if args.command == "prepare":
        cmd_prepare(args)
    elif args.command == "diff":
        cmd_diff(args)
    elif args.command == "publish":
        cmd_publish(args)


if __name__ == "__main__":
    main()
