# Maturity Check — When to Suggest Publishing

After a skill stabilizes through creation and reflection cycles, proactively suggest publishing to the community registry.

## Maturity Signals

Check these after each successful execution or reflect cycle. A skill is **ready to publish** when ALL of the following are true:

1. **Production-tested** — skill has been used successfully ≥3 times in real tasks (not just `--help` smoke tests)
2. **Stable** — no reflect fixes in the last 3 days (or last 5 successful executions, whichever comes first)
3. **Well-structured** — SKILL.md has valid `name` and `description` in frontmatter, ≤300 lines
4. **Clean** — no sanitize warnings (run `publish.py` preview to check: no hardcoded paths, no leaked secrets)
5. **Self-contained** — if it has scripts, they all exit 0 on `--help`; if it depends on other skills, `depends_on` is declared in frontmatter

## Optional (strengthen the case)

- Has `evals.yaml` with passing tests
- Has been used by multiple users (not just the author)
- Review score ≥4.0 from peers

## How to Suggest

When all required signals are met, present to the user:

```
这个 skill 已经稳定运行了，要发布到社区市场吗？

[OPTIONS]
A: 发布到市场
B: 再观察一段时间
[/OPTIONS]
```

Include a brief summary: execution count, days since last fix, file count, any warnings.

## When NOT to Suggest

- Skill is purely internal (contains org-specific logic, internal API keys, proprietary workflows)
- Skill is a thin wrapper around one API call — probably not worth publishing as standalone
- User has previously declined publishing for this skill — don't ask again in the same session

## After User Confirms

Route to the publish workflow: read `references/publish.md` and follow the preview → confirm → publish flow.
