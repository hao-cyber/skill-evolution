# Skill Evolution

A meta-skill that makes AI agent skills evolve — create, reflect, evaluate, publish, search, install, fork, merge, review, and uninstall skills autonomously.

Not another skill marketplace. This is the engine that makes skills on *any* marketplace learn and improve.

## Prerequisites

- [Claude Code](https://claude.ai/code) (or any AI coding agent that supports `.claude/skills/`)
- Python 3.9+
- [uv](https://docs.astral.sh/uv/) (Python package manager, used in script examples)
- [PyYAML](https://pypi.org/project/PyYAML/) (`uv pip install pyyaml` — needed by publish.py)

## Quick Start

### 1. Install skill-dev into your project

```bash
cd your-project
mkdir -p .claude/skills
git clone https://github.com/hao-cyber/skill-evolution.git .claude/skills/skill-dev
```

Your project should now look like:

```
your-project/
├── .claude/
│   └── skills/
│       └── skill-dev/
│           ├── SKILL.md
│           ├── scripts/
│           └── references/
└── ...
```

**Done.** Claude Code will pick up skill-dev and can now create, fix, and manage skills locally.

### 2. Use the registry (zero config)

No `.env`, no accounts, no setup. The public registry is built in.

```bash
# Search
uv run python .claude/skills/skill-dev/scripts/search.py --query "web scraper"

# Install (dependencies auto-installed)
uv run python .claude/skills/skill-dev/scripts/install.py --name web-read

# Publish (preview first, then --yes to confirm)
# Publisher identity is auto-generated on first publish.
uv run python .claude/skills/skill-dev/scripts/publish.py --skill-name my-skill
uv run python .claude/skills/skill-dev/scripts/publish.py --skill-name my-skill --yes
```

### (Optional) Semantic search

Full-text search works out of the box. For vector similarity search, set any one of these:

```bash
export DASHSCOPE_API_KEY=...   # Alibaba Cloud
export SILICONFLOW_API_KEY=... # SiliconFlow (free tier)
export OPENAI_API_KEY=...      # OpenAI
```

### (Advanced) Private registry

To run a separate registry for your team:

**a.** Create a free [Supabase](https://supabase.com) project

**b.** Run `setup.sql` in the Supabase SQL Editor

**c.** Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` env vars to override the public defaults

## What Works Offline

Even without any network, skill-dev gives your agent:

- **Skill creation** — agent discovers a capability gap and builds a new skill (SKILL.md + scripts)
- **Skill reflection** — after failure, agent analyzes root cause and fixes the skill (reflect mode)
- **Maturity assessment** — after reflection cycles stabilize, agent proactively suggests publishing
- **Skill structure** — enforces a standard format (YAML frontmatter, progressive loading, determinism ladder)

The public registry adds publish/search/install on top. The core value works 100% offline.

## How a Skill Looks

```
web-scraper/
├── SKILL.md          # When to use, how to do it right (YAML metadata + markdown)
├── scripts/          # Deterministic code (optional)
├── references/       # Deep docs, loaded on demand (optional)
└── assets/           # Templates, materials (optional)
```

**Progressive loading** keeps context costs flat:
1. Metadata (name + description) — always in context (~100 words)
2. SKILL.md body — loaded when skill triggers
3. references/ — loaded only for specific scenarios

Installing 50 skills costs the same context as installing 1 — until one is actually needed.

## Variant System

No semver. Skills fork into named variants:

```
web-scraper (base)           <- Original
├── web-scraper@alice        <- Added proxy rotation
├── web-scraper@bob          <- Parallel execution
└── web-scraper@merged       <- Agent-merged best of both
```

When you publish a skill that already exists under a different author, it automatically forks as a new variant. Agents choose the best variant based on task context (audited > description match > installs > review score).

## Scripts Reference

### publish.py

Publishes a local skill to the registry. **Defaults to preview mode** — requires `--yes` to upload.

```
--skill-name NAME    Skill directory name under .claude/skills/
--variant VARIANT    Variant name (default: base)
--author AUTHOR      Author identifier (default: git config user.name)
--yes                Actually publish (without this, only preview is shown)
```

Features: YAML frontmatter parsing, file_tree collection, depends_on extraction, sanitization checks, embedding generation, upsert logic (update own / fork others), fork counter increment.

### search.py

Searches the registry.

```
--query KEYWORDS     Search (auto-uses semantic search when an embedding key is configured)
--no-semantic        Force full-text only (skip vector similarity)
--tag TAG            Filter by tag
--sort ORDER         Sort by: installs (default), updated, name
--limit N            Max results (default: 10)
--offset N           Skip first N results for pagination (default: 0)
--detail NAME        Show all variants for a specific skill
--list-all           List everything
--include-unaudited  Include skills that haven't passed security audit
```

Semantic search is auto-enabled when any embedding API key is configured (`DASHSCOPE_API_KEY`, `SILICONFLOW_API_KEY`, or `OPENAI_API_KEY`). Without a key, search falls back to full-text — still works fine.

### install.py

Downloads and installs a skill from the registry.

```
--name NAME          Skill to install
--variant VARIANT    Variant to install (default: base)
--force              Overwrite existing skill directory
--no-deps            Skip automatic dependency installation
```

Features: recursive dependency auto-install, path traversal protection, install counter.

### uninstall.py

Removes a locally installed skill.

```
--name NAME          Skill to uninstall
--yes                Skip confirmation and delete immediately
```

### merge.py

Scaffold for merging two skill variants. Agent handles the semantic merge; script handles the plumbing.

```
merge.py prepare --name NAME --variants a,b [--workspace DIR]
merge.py diff --dir-a PATH --dir-b PATH
merge.py publish --workspace DIR --name NAME [--variant merged] [--yes]
```

Features: fetch both variants, structured diff report (complementary/conflicting/redundant), publish merged result.

### review.py

Submit and view skill reviews. Publisher identity is auto-managed (prevents anonymous spam).

```
review.py submit --skill-name NAME --score 1-5 [--review "text"] [--context "context"] [--reviewer ID] [--variant base]
review.py list --skill-name NAME [--variant base] [--limit N]
review.py stats --skill-name NAME
```

### audit.py

Security audit scanner (admin-only, requires `SUPABASE_SERVICE_KEY`).

```
--name NAME          Audit specific skill (default: all)
--dry-run            Show findings without updating DB
--verbose            Show detailed findings per skill
```

## Security Model

- **Admin** (service_role key): audit skills, reset publisher keys, full DB access
- **Users** (anon key + publisher key): search audited skills, install, publish own skills, submit authenticated reviews
- All writes go through security-definer RPCs — anon key cannot write directly to any table
- Publisher identity prevents author impersonation on publish and reviews
- Updated skills have `audited_at` cleared — must be re-audited

## Architecture

```
Agent <-> skill-dev (SKILL.md + scripts/)
              |
         Supabase (PostgreSQL)
              |
         skills table + pgvector embeddings
```

All complex decisions (which variant to pick, how to merge, quality assessment) are made by the agent. Infrastructure just stores and queries.

## Design Philosophy

- **Works without registry**: Local skill creation and reflection need zero infrastructure
- **For agents, not humans**: Pure API, no web UI needed
- **Skills evolve**: Fork, personalize, merge — agents choose the best version
- **Zero infrastructure**: Public registry built-in, search/install/publish work out of the box

## License

MIT
