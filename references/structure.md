# Skill 结构规范与创建流程

## Skill Structure

```
skill-name/
├── SKILL.md          (required - YAML frontmatter + markdown instructions)
├── scripts/          (optional - executable code for deterministic tasks)
├── references/       (optional - docs loaded into context as needed)
└── assets/           (optional - files used in output, not loaded into context)
```

### SKILL.md Format

**Frontmatter** (YAML, required fields):
- `name`: Skill name
- `description`: What the skill does AND when to trigger it. This is the primary trigger mechanism - all "when to use" info goes here, not in the body.

**Frontmatter** (YAML, optional fields):
- `depends_on`: List of skill names this skill requires (auto-installed on `install.py`)

```yaml
---
name: my-skill
description: Does X when Y happens
depends_on:
  - web-read
  - llm-gateway
---
```

**Body** (Markdown): Instructions and guidance, loaded only after skill triggers.

### Progressive Disclosure

Context is your scarcest resource. Every line loaded dilutes attention on what matters.

Three-level loading:
1. **Metadata** (name + description) — Always in context (~100 words)
2. **SKILL.md body** — When skill triggers. This is the **routing layer**: decide what to do, then load only what's needed.
3. **Bundled resources** — Loaded on demand via Read tool (references/, scripts can run without reading)

**Size targets for SKILL.md body:**
- **≤150 lines** — ideal. Routing + shared rules + reference index.
- **150–300 lines** — acceptable if the skill has only one workflow (no split benefit).
- **>300 lines** — must split. Move scenario-specific content to `references/`.

### How to Split

Split by **usage scenario**, not by content type:

**SKILL.md keeps:**
- Routing logic (what does the user want → which reference to Read)
- Rules shared across ALL scenarios
- Reference index with one-line descriptions and trigger conditions

**references/ gets:**
- Complete workflow for each scenario (e.g., `create-new.md`, `edit-existing.md`)
- Lookup tables and reference data (page sizes, API params, format specs)
- Low-frequency scenarios and edge cases

**Reference file naming rules:**
- Name by **content essence**, not by source/author/tool name
  - `top-blog-rss.md` not `karpathy-rss-feeds.md` (decouple from person)
  - `gotchas.md` not `reference.md` (too generic = useless)
- **No redundant prefix** when directory already provides context
  - `google-calendar/references/operations.md` not `calendar-operations.md`
  - `doc-writer/references/write.md` not `doc-write.md`
- **Tool/library names OK** when the file is genuinely tool-specific and alternatives exist (e.g. `pptxgenjs.md` alongside potential `python-pptx.md`)
- **Style consistency within a skill**: same naming pattern across sibling files (e.g. all `platform-api.md` or all `operation-verb.md`)

**Reference index format** (at bottom of SKILL.md):
```markdown
## References
- `references/create-new.md` — Creating documents from scratch. Read when user wants a new file.
- `references/edit-existing.md` — Modifying existing files. Read when user provides a file to edit.
```

**Key principle**: A skill that handles 3 scenarios should load ~⅓ of its knowledge per invocation, not 100%.

### Skill Split Checklist

When splitting one skill into two (e.g. project-mgmt → task-mgmt + calendar):

1. **Physical ownership** — Move files, don't symlink. Each skill owns its scripts and references.
2. **Path consistency** — All script paths in references/ and SKILL.md point to the skill's own directory.
3. **Trigger dedup** — Check every trigger phrase: does it unambiguously belong to exactly one skill? If ambiguous (e.g. "把XX拉进来" fits both tasks and calendar), remove from both — let context decide.
4. **Minimal depends-on** — Only list dependencies whose context is needed at runtime. Don't add cross-references "for routing" — description text handles that.
5. **Impact scan** — `grep -rl "<old-skill-name>" .claude/` and update all downstream references (CLAUDE.md, other skills' depends-on, script paths in references/).

## Creation Process

### 1. Understand with Concrete Examples

Ask the user:
- What functionality should this skill support?
- Give examples of how it would be used
- What should trigger this skill?

Skip if usage patterns are already clear.

### 2. Plan Reusable Contents

For each example, consider:
- What code gets rewritten each time? → `scripts/`
- What documentation is needed repeatedly? → `references/`
- What files are used in output? → `assets/`

### 3. Create the Skill

Create directory at `.claude/skills/<skill-name>/` and write SKILL.md.

**Frontmatter tips:**
- Description should include both what the skill does and specific triggers
- Example: "Comprehensive document creation and editing. Use when working with .docx files for: (1) Creating new documents, (2) Modifying content, (3) Working with tracked changes"

**Body tips:**
- Use imperative/infinitive form
- Keep instructions focused on what another Claude instance needs to know
- Include non-obvious procedural knowledge and domain-specific details
- All Python scripts use stdlib only — invoke with `python3` (no pip install needed)
- Do NOT create README.md, CHANGELOG.md, or other auxiliary files

### 4. Boundary Check

Before finalizing, verify the new skill doesn't collide with existing ones:
- Search existing trigger descriptions: `grep -rl "<key terms>" .claude/skills/`
- If triggers overlap, narrow the new skill's description or add explicit routing rules
- Routing rules go in CLAUDE.md when two skills share an ambiguous boundary

### 5. Verify

Verification is the highest-leverage step. Don't skip it.

- Trigger test: confirm the skill fires on intended inputs and does NOT fire on similar-but-wrong inputs
- Script smoke test: run each script with `--help` or minimal args to confirm it executes
- End-to-end: use 1-2 real scenarios and check the **full** output
- Context cost: note the SKILL.md line count — ≤150 ideal, >300 must split into references/

### 6. Consider Hooks

If the skill has rules that MUST be enforced with zero exceptions, define hooks:

```yaml
---
name: my-skill
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "$CLAUDE_PROJECT_DIR/.claude/skills/my-skill/scripts/validate.sh"
---
```

Hooks can also go in `.claude/settings.json` (project-wide) or `~/.claude/settings.json` (global).
