# Search & Install — Community Skills

## When to Search

- Agent discovers a capability gap ("this task needs a skill I don't have")
- User asks "有没有XX的skill", "search skill", "install XX"
- User says "安装 skill", "find a skill for..."

## Search Flow

### 1. Search Registry

```bash
uv run python .claude/skills/skill-dev/scripts/search.py \
  --query "<keywords>" [--tag <tag>] [--limit 10]
```

Output: grouped by skill name, showing variants, installs, description.

### 2. Get Detail

For a specific skill:

```bash
uv run python .claude/skills/skill-dev/scripts/search.py \
  --detail <skill-name>
```

Shows all variants with metadata, requires_env, skill_md line count.

### 3. Variant Selection

When multiple variants exist, use this decision tree:

**Single variant** → install it directly.

**Multiple variants** → evaluate in order:

1. **Filter by audit status** — prefer audited variants. If only unaudited variants exist, warn the user about the risk and let them decide.
2. **Match by description** — read each variant's description and optimization focus. Pick the one that best matches the current task context (e.g., speed-optimized for latency-sensitive tasks, accuracy-optimized for critical tasks).
3. **Break ties by installs** — higher install count = more community validation.
4. **Break further ties by review score** — use `scripts/review.py stats --skill-name <name>` to compare average scores per variant.
5. **Two variants are complementary** — if variant A optimizes X and variant B optimizes Y, and the current task needs both X and Y, suggest merging (read `references/merge.md`).

**Always explain your choice** to the user: "Installing `web-scraper@alice` (audited, 47 installs) — it optimizes for proxy rotation which matches your use case."

## Install Flow

### 1. Install

```bash
uv run python .claude/skills/skill-dev/scripts/install.py \
  --name <skill-name> [--variant <variant>] [--force]
```

This:
- Downloads skill_md + file_tree from registry
- Recreates directory structure at `.claude/skills/<name>/`
- Makes scripts executable
- Increments install counter (best-effort)

### 2. Post-Install Checks

- If `missing_env` in output → warn user about required env vars
- If `depends_on` → check if dependent skills are installed
- Run script `--help` to verify executability

### 3. Report

Show: installed path, file count, any warnings.

## Environment Variables

- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_ANON_KEY` — Anon key (public read access, no auth needed)

### Embedding (optional — enables semantic search)

Set any ONE of these keys to auto-enable semantic search on `--query`:

- `DASHSCOPE_API_KEY` — DashScope text-embedding-v3
- `SILICONFLOW_API_KEY` — SiliconFlow BAAI/bge-m3 (free model)
- `OPENAI_API_KEY` — OpenAI or any compatible API (set `EMBEDDING_BASE_URL` to override endpoint)

Without a key, search uses full-text search only (still works fine).
Use `--no-semantic` to force full-text even when a key is available.
