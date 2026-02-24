# Merge — Agent-Driven Variant Fusion

## When to Merge

- Multiple variants of the same skill have complementary optimizations
- User says "merge these variants", "合并版本", "融合"
- Agent identifies two variants that together would be better than either alone

## Flow

### 1. Discover Variants

```bash
uv run python .claude/skills/skill-dev/scripts/search.py \
  --detail <skill-name>
```

Review all variants: what each optimized, which changes are complementary vs conflicting.

### 2. Prepare Workspace

Use `merge.py prepare` to download both variants and get a structured diff:

```bash
uv run python .claude/skills/skill-dev/scripts/merge.py prepare \
  --name <skill-name> --variants <variant-a>,<variant-b>
```

This creates a workspace with:
- `<variant-a>/` — full content of variant A
- `<variant-b>/` — full content of variant B
- `merged/` — empty directory for the merge result
- Structured diff report classifying files as complementary/conflicting/redundant

### 3. Analyze Differences

The diff report tells you:

- **Complementary** — files unique to one variant. Safe to copy both into `merged/`.
- **Conflicting** — same file modified differently. Read both, apply agent judgment.
- **Redundant** — identical in both. Copy either into `merged/`.

### 4. Merge Strategy

**SKILL.md merging** (agent's strength):
- Combine non-conflicting instruction improvements
- For conflicts: evaluate which instruction is better for the merged use case
- Rewrite description to reflect combined capabilities
- Update tags to cover both specializations

**Script merging** (use deterministic approach):
- If scripts don't overlap: include both
- If scripts conflict: prefer the more robust implementation, or create a wrapper
- Always test merged scripts with `--help`

### 5. Validate

- Run script `--help` tests
- Check SKILL.md line count (≤300)
- Verify no broken references between files

### 6. Publish as New Variant

```bash
uv run python .claude/skills/skill-dev/scripts/merge.py publish \
  --workspace <workspace>/merged --name <skill-name> --variant merged --yes
```

### 7. Report

Show: which variants were merged, what was taken from each, any conflicts resolved.

## Quick Diff (without full prepare)

To compare two already-downloaded variant directories:

```bash
uv run python .claude/skills/skill-dev/scripts/merge.py diff \
  --dir-a /path/to/variant-a --dir-b /path/to/variant-b
```

## Principles

- **Semantic merge, not text merge** — LLM understands intent behind instructions, not just diff lines
- **Complementary > conflicting** — if two optimizations don't touch the same area, just combine them
- **Provenance tracking** — the merged variant description should credit source variants
- **User confirms** — always show the merge plan before creating the merged version
