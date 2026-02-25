# Publish — Skill to Community Registry

## When to Publish

- Skill has been used successfully at least once in production
- User explicitly says "publish", "发布", "开源这个 skill"
- After skill creation/iteration, agent assesses quality is ready

## Flow

### 1. Quality Gate

Before publishing, verify:
- SKILL.md exists with `name` and `description` in frontmatter
- SKILL.md ≤300 lines
- Scripts have `--help` and exit 0

### 2. Preview (default behavior)

Run without `--yes` — the script defaults to preview mode:

```bash
python3 .claude/skills/skill-dev/scripts/publish.py \
  --skill-name <name>
```

Show the user: name, variant, file count, tags, sanitize warnings.

### 3. Sanitize Review

The script auto-checks for:
- Hardcoded paths (`/home/xxx/`)
- Possible API keys/secrets
- Internal env var references

If warnings appear, fix them before publishing. Replace hardcoded paths with generic paths, move secrets to `requires_env`.

### 4. User Confirmation (MANDATORY)

**MUST wait for explicit user approval before proceeding.** Present the preview and ask:
- Skill name and variant
- Files to include
- Any warnings to address

**Do NOT pass `--yes` until the user explicitly confirms.** This is a hard gate — no exceptions.

### 5. Publish

Only after user says "确认" / "发布" / "ok" / "yes":

```bash
python3 .claude/skills/skill-dev/scripts/publish.py \
  --skill-name <name> --yes [--variant <variant>] [--author <author>]
```

**Upsert logic:**
- Same name + variant + same author → update
- Same name + variant + different author → fork (new variant = author name)
- New name → create

### 6. Report

Show the user: action (published/updated/forked), ID, file count.

## Environment Variables

No env vars needed for normal use. Public registry and publisher identity are auto-managed.

- `SUPABASE_URL` — Override to use a private registry
- `SUPABASE_ANON_KEY` — Override to use a private registry

## Publisher Identity

Each author has a unique publisher key (UUID) stored in the `publishers` table. This prevents author impersonation.

- **First publish**: Auto-registers and saves the key to `.publisher_key` in the skill directory.
- **Subsequent publishes**: The key is loaded from `.publisher_key` and validated server-side against the claimed author.
- **Key lost**: Admin runs `reset_publisher_key` RPC (requires service key) to issue a new key. Old key is immediately invalidated.
