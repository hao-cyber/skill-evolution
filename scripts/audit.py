#!/usr/bin/env python3
"""Security audit for skills in the Skill Evolution registry.

Scans all skills (or specific ones) against security rules.
Skills that pass get marked with audited_at timestamp.
Skills that fail get audited_at cleared.

Designed to run periodically (e.g. via cron or scheduler).
Requires SUPABASE_SERVICE_KEY (admin-only operation).
"""

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path

# Add scripts/ to path so lib/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.supabase import supabase_get, supabase_rpc


def parse_args():
    p = argparse.ArgumentParser(description="Audit skills for security issues")
    p.add_argument("--name", default=None, help="Audit a specific skill by name (default: all)")
    p.add_argument("--dry-run", action="store_true", help="Show results without updating database")
    p.add_argument("--verbose", "-v", action="store_true", help="Show detailed findings per skill")
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
                if any(fp in m for fp in ["SUPABASE", "TASKPOOL", "$HOME", "${HOME}", "os.environ", "os.getenv"]):
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


def main():
    args = parse_args()

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
            supabase_rpc("audit_skill", {
                "p_skill_id": skill["id"],
                "p_passed": passed,
            }, service_key=True, exit_on_error=False)
            status = "PASS" if passed else "FAIL"
            print(f"  {status}: {label} ({len(findings)} findings)", file=sys.stderr)

    if args.dry_run:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        summary = f"Audit complete: {results['passed']}/{results['total']} passed, {results['failed']} failed"
        print(summary, file=sys.stderr)
        print(json.dumps({
            "status": "ok",
            "total": results["total"],
            "passed": results["passed"],
            "failed": results["failed"],
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
