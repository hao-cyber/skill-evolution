#!/usr/bin/env python3
"""Security + stability audit for skills.

Modes:
1) Security audit (default): scan registry skills via Supabase.
2) Stability audit (--stability-audit): scan local git history for skills/* A->D churn.
"""

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

# Add scripts/ to path so lib/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.supabase import supabase_get, supabase_rpc


def parse_args():
    p = argparse.ArgumentParser(description="Audit skills for security/stability issues")
    p.add_argument("--name", default=None, help="Audit a specific skill by name (default: all)")
    p.add_argument("--dry-run", action="store_true", help="Show results without updating database")
    p.add_argument("--verbose", "-v", action="store_true", help="Show detailed findings per skill")

    # Stability audit mode
    p.add_argument("--stability-audit", action="store_true", help="Run git-based stability audit for skills/*")
    p.add_argument("--repo", default=str(Path(__file__).resolve().parents[2]), help="Repo root for git scan")
    p.add_argument("--days", type=int, default=7, help="Lookback window in days for stability audit")
    p.add_argument("--top", type=int, default=1, help="Top N churn candidates to output")
    p.add_argument("--report-file", default=None, help="Optional path to write markdown audit section")
    p.add_argument(
        "--include-deleted",
        action="store_true",
        help="Include skills that are no longer present under skills/ (default: active skills only)",
    )
    return p.parse_args()


# --- Security rules ---

DANGEROUS_PATTERNS = [
    # Code injection
    (r'\beval\s*\(', "eval() call — arbitrary code execution"),
    (r'\bexec\s*\(', "exec() call — arbitrary code execution"),
    (r'(?<!re\.)\bcompile\s*\(', "compile() call — potential code execution"),
    # Command injection
    (r'os\.system\s*\(', "os.system() — shell command injection risk"),
    (r'subprocess\.\w+\(.*shell\s*=\s*True', "subprocess with shell=True — command injection risk"),
    (r'os\.popen\s*\(', "os.popen() — shell command injection risk"),
    # Path traversal
    (r'\.\./\.\.',  "path traversal pattern (../../)"),
]

# URL patterns that look suspicious but are OK for known API domains
KNOWN_API_DOMAINS = [
    "open.feishu.cn", "open.larksuite.com",  # Feishu/Lark
    "api.vercel.com",  # Vercel
    "dashscope.aliyuncs.com",  # DashScope
    "open.bigmodel.cn",  # GLM
    "api.siliconflow.cn",  # SiliconFlow
    "supabase.co",  # Supabase
]

SECRET_PATTERNS = [
    (r'(?:sk|api|token|key|secret|password)[-_]?\w*\s*=\s*["\'][A-Za-z0-9_\-]{20,}', "hardcoded secret/API key"),
    (r'Bearer\s+[A-Za-z0-9_\-]{20,}', "hardcoded Bearer token"),
]

HARDCODED_PATH_PATTERNS = [
    (r'/home/\w+/', "hardcoded home path"),
    (r'C:\\\\Users\\\\', "hardcoded Windows path"),
]


def audit_skill(skill):
    """Run security checks on a single skill. Returns (passed: bool, findings: list[str])."""
    findings = []
    file_tree = skill.get("file_tree", {})
    name = skill.get("name", "unknown")

    # 1. Check file_tree for dangerous patterns
    for rel_path, content in file_tree.items():
        if not isinstance(content, str):
            continue

        # Skip binary placeholders
        if content.startswith("[binary file,"):
            continue

        for pattern, desc in DANGEROUS_PATTERNS:
            matches = re.findall(pattern, content)
            if matches:
                findings.append(f"FAIL [{rel_path}]: {desc}")

        # Check f-string/dynamic URLs — WARN unless clearly suspicious
        # Most skills legitimately use f-string URLs for API calls; only flag as
        # info so reviewers are aware, not as automatic failures.
        url_patterns = [
            (r'urllib\.request\.urlopen\s*\(\s*[^)]*\+', "dynamic URL construction"),
            (r'requests\.(get|post)\s*\(\s*f["\']', "f-string URL in requests"),
            (r'urlopen\s*\(\s*f["\']', "f-string URL in urlopen"),
            (r'Request\s*\(\s*f["\']', "f-string URL in Request"),
        ]
        for pattern, desc in url_patterns:
            matches = re.finditer(pattern, content)
            for m in matches:
                # Check surrounding context for known API domains → skip entirely
                start = max(0, m.start() - 50)
                end = min(len(content), m.end() + 200)
                context = content[start:end]
                if any(domain in context for domain in KNOWN_API_DOMAINS):
                    continue
                findings.append(f"WARN [{rel_path}]: {desc}")

        for pattern, desc in SECRET_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for m in matches:
                # Skip false positives
                if any(fp in m for fp in ["SUPABASE", "TASKPOOL", "${HOME}", "os.environ", "os.getenv"]):
                    continue
                findings.append(f"FAIL [{rel_path}]: {desc} — {m[:50]}...")

        for pattern, desc in HARDCODED_PATH_PATTERNS:
            if re.search(pattern, content):
                findings.append(f"WARN [{rel_path}]: {desc}")

    # 2. Check SKILL.md size
    skill_md = skill.get("skill_md", "")
    if len(skill_md.splitlines()) > 500:
        findings.append(f"WARN: SKILL.md is {len(skill_md.splitlines())} lines (recommended ≤300)")

    # 3. Check file_tree total size
    total_size = sum(len(v) for v in file_tree.values() if isinstance(v, str))
    if total_size > 500_000:
        findings.append(f"FAIL: file_tree too large ({total_size} bytes, max 500KB)")

    # 4. Check file count
    if len(file_tree) > 50:
        findings.append(f"FAIL: too many files ({len(file_tree)}, max 50)")

    # 5. Check description length
    desc = skill.get("description", "")
    if len(desc) > 1000:
        findings.append(f"FAIL: description too long ({len(desc)} chars)")

    # Determine pass/fail: FAIL findings = reject, WARN-only = pass with warnings
    has_fail = any(f.startswith("FAIL") for f in findings)
    return not has_fail, findings


def _run_git(repo, args):
    cmd = ["git", "-C", repo, *args]
    return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)


def _list_active_skills(repo):
    skills_dir = Path(repo) / "skills"
    if not skills_dir.exists():
        return set()
    return {
        p.name
        for p in skills_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    }


def run_stability_audit(repo, days, top, report_file=None, include_deleted=False):
    """Scan git history and find skills with A->D churn within lookback window."""
    try:
        output = _run_git(
            repo,
            [
                "log",
                f"--since={days} days ago",
                "--name-status",
                "--pretty=format:__COMMIT__%H|%ct|%s",
                "--",
                "skills/",
            ],
        )
    except Exception as e:
        raise RuntimeError(f"ERROR: git log scan failed: {e}")

    skills = {}
    current = None

    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("__COMMIT__"):
            meta = line.replace("__COMMIT__", "", 1)
            parts = meta.split("|", 2)
            if len(parts) < 3:
                current = None
                continue
            current = {"hash": parts[0], "ts": int(parts[1]), "subject": parts[2]}
            continue

        if current is None:
            continue

        fields = line.split("\t")
        if len(fields) < 2:
            continue
        status = fields[0][0]  # A/M/D/R...
        path = fields[-1]

        if not path.startswith("skills/"):
            continue

        parts = path.split("/")
        if len(parts) < 2:
            continue
        skill = parts[1]

        rec = skills.setdefault(
            skill,
            {
                "skill": skill,
                "adds": 0,
                "deletes": 0,
                "last_add": None,
                "last_delete": None,
                "latest_ts": 0,
            },
        )

        if status == "A":
            rec["adds"] += 1
            if rec["last_add"] is None or current["ts"] > rec["last_add"]["ts"]:
                rec["last_add"] = current
        elif status == "D":
            rec["deletes"] += 1
            if rec["last_delete"] is None or current["ts"] > rec["last_delete"]["ts"]:
                rec["last_delete"] = current

        if current["ts"] > rec["latest_ts"]:
            rec["latest_ts"] = current["ts"]

    churn_candidates = [v for v in skills.values() if v["adds"] > 0 and v["deletes"] > 0]

    active_skills = _list_active_skills(repo)
    if include_deleted:
        candidates = churn_candidates
    else:
        candidates = [c for c in churn_candidates if c["skill"] in active_skills]

    candidates.sort(key=lambda x: (x["adds"] + x["deletes"], x["latest_ts"]), reverse=True)
    top_candidates = candidates[: max(1, top)]

    result = {
        "status": "ok",
        "mode": "stability",
        "lookback_days": days,
        "generated_at": int(time.time()),
        "skills_scanned": len(skills),
        "active_skills": len(active_skills),
        "churn_candidates_total": len(churn_candidates),
        "churn_candidates": len(candidates),
        "filtered_out_removed": max(0, len(churn_candidates) - len(candidates)),
        "include_deleted": include_deleted,
        "top": top_candidates,
    }

    if report_file:
        p = Path(report_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            f.write("## Stability Audit Candidates\n\n")
            f.write(f"- Lookback: {days} days\n")
            scope = "skills/* (active only)" if not include_deleted else "skills/* (including deleted)"
            f.write(f"- Scope: {scope}\n")
            f.write(f"- A→D churn candidates: {len(candidates)}")
            if not include_deleted:
                f.write(f" (filtered removed: {max(0, len(churn_candidates) - len(candidates))})")
            f.write("\n\n")
            if top_candidates:
                t = top_candidates[0]
                f.write(f"### Top1: `{t['skill']}`\n")
                f.write(f"- Change counts: A={t['adds']} / D={t['deletes']}\n")
                if t.get("last_add"):
                    f.write(f"- Recent add: {t['last_add']['hash'][:8]} · {t['last_add']['subject']}\n")
                if t.get("last_delete"):
                    f.write(f"- Recent delete: {t['last_delete']['hash'][:8]} · {t['last_delete']['subject']}\n")
                f.write("- Suggestion: prioritize this skill in today's improvement recommendation.\n")
            else:
                f.write("- No A→D churn candidates detected today.\n")

    return result


def run_security_audit(args):
    # Fetch skills (service key to read file_tree which may not be exposed via anon)
    select = "id,name,variant,description,author,skill_md,file_tree,audited_at"
    if args.name:
        name_q = urllib.parse.quote(args.name)
        skills = supabase_get(f"skills?name=eq.{name_q}&select={select}", service_key=True)
    else:
        skills = supabase_get(f"skills?select={select}&order=name.asc", service_key=True)

    if not skills:
        print("No skills found.")
        return

    results = {"total": len(skills), "passed": 0, "failed": 0, "skills": []}

    for skill in skills:
        passed, findings = audit_skill(skill)
        label = f"{skill['name']}@{skill['variant']}"

        result = {
            "name": skill["name"],
            "variant": skill["variant"],
            "passed": passed,
            "finding_count": len(findings),
            "previously_audited": skill.get("audited_at") is not None,
        }

        if args.verbose or not passed:
            result["findings"] = findings

        results["skills"].append(result)

        if passed:
            results["passed"] += 1
        else:
            results["failed"] += 1

        # Update database
        if not args.dry_run:
            supabase_rpc(
                "audit_skill",
                {
                    "p_skill_id": skill["id"],
                    "p_passed": passed,
                },
                service_key=True,
                exit_on_error=False,
            )
            status = "PASS" if passed else "FAIL"
            print(f"  {status}: {label} ({len(findings)} findings)", file=sys.stderr)

    if args.dry_run:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "total": results["total"],
                    "passed": results["passed"],
                    "failed": results["failed"],
                },
                ensure_ascii=False,
            )
        )


def main():
    args = parse_args()

    if args.stability_audit:
        result = run_stability_audit(
            repo=args.repo,
            days=max(1, args.days),
            top=max(1, args.top),
            report_file=args.report_file,
            include_deleted=args.include_deleted,
        )
        print(json.dumps(result, ensure_ascii=False))
        return

    run_security_audit(args)


if __name__ == "__main__":
    main()
