---
name: skill-dev
description: "Skill 全生命周期管理：创建 → 反思优化 → 评测 → 成熟度判断 → 发布到市场 → 检索多版本 → 选择/安装 → 融合迭代 → 卸载。触发场景：(1) 用户要求创建/修改 skill (2) 发现可提取为 skill 的重复模式 (3) skill 执行出错或用户纠正后需要反思改进 (4) 用户要求发布/搜索/安装/合并社区 skill (5) 反思后自动检查成熟度并建议发布"
---

# Skill Dev

Full lifecycle management for AI agent skills: create, reflect, evaluate, publish, search, install, merge, review, and uninstall.

## Lifecycle Flow

Each stage has a validation gate before advancing to the next:

1. **Create** → verify triggers fire correctly and scripts run (`--help` smoke test)
2. **Use** → observe real executions for failure signals
3. **Reflect** → after failures or user corrections, identify root cause and patch
4. **Evaluate** → run regression tests to confirm fixes don't break other cases
5. **Maturity check** → confirm publish readiness (3+ successful runs, no recent reflects)
6. **Publish** → push to registry: `python3 scripts/publish.py .claude/skills/<name>/`

Fail any gate → loop back. Example: reflect fix at step 3 requires re-evaluation at step 4 before proceeding to step 5.

## Core Principles

### Degrees of Freedom

Match specificity to the task's fragility:

- **High freedom** (text instructions): "Choose an appropriate error message" — multiple valid answers
- **Medium freedom** (pseudocode with params): "Format errors as `ERROR: {context} — {detail}`" — pattern fixed, content varies
- **Low freedom** (exact scripts): `sys.exit(1)` on failure — no variation allowed

## Routing

**Local lifecycle (no registry needed):**
- **Creating/structuring a skill** (directory layout, SKILL.md format, progressive disclosure, verification) → 读取 `references/structure.md`
- **Reflecting after skill failure** (trigger signals, reflect process, impact scan, escalation) → 读取 `references/reflect-mode.md`
- **评测 skill prompt** (eval、跑回归、检查 prompt 改动效果) → 读取 `references/eval-mode.md`
- **Checking skill maturity** (after reflect, after successful runs, "成熟了吗", "该发布了吗") → 读取 `references/maturity.md`

**Registry lifecycle (public registry built-in, works out of the box):**
- **Publishing a skill** ("publish", "发布 skill", "开源这个 skill") → 读取 `references/publish.md`
- **Searching/installing** ("search skill", "有没有XX的skill", "安装 skill") → 读取 `references/search.md`
- **Reviewing a skill** ("review", "评价 skill", "打分") → use `scripts/review.py`
- **Merging skill variants** ("merge", "合并版本", "融合") → 读取 `references/merge.md`
- **Uninstalling a skill** ("uninstall", "删除 skill", "卸载") → use `scripts/uninstall.py --name <skill> --yes`

### Quick Example: Reflect → Evaluate → Publish

```bash
# 1. Reflect — skill failed on "create a meeting" (routed to doc-writer instead of calendar)
#    Fix: narrow trigger in SKILL.md description, add negative example
grep -rl "create" .claude/skills/ | head -5  # impact scan: find colliding triggers

# 2. Evaluate — verify the fix didn't break other cases
python3 .claude/skills/prompt-eval/scripts/run_eval.py \
  --prompts /tmp/skill-system-prompt.md \
  --tests .claude/skills/doc-writer/evals.yaml \
  --task-id reflect-fix-001 --output-dir /tmp/eval-out

# 3. Publish — all tests pass + 3 successful runs + no recent reflects
python3 scripts/publish.py .claude/skills/doc-writer/
```

## When NOT to Create a Skill

Don't build for hypothetical future needs. Skip if ANY apply:
- Used only once — just do it inline
- A one-line CLAUDE.md rule covers it — just edit CLAUDE.md directly instead
- No reusable script AND no non-obvious knowledge — Claude already knows how
- An existing skill handles 80%+ of the use case — extend it instead

## Script Design

Tool design matters more than prompt design. When a skill has `scripts/`, invest in quality:

- **Token-light output**: Print only what the caller needs. `--verbose` for debugging only.
- **Greppable errors**: All errors start with `ERROR:` with key details on same line.
- **Self-documenting**: Support `--help` with one-liner description and parameter list.
- **Clear parameter names**: Use intuitive names (`--document-id`, not `--did`).
- **Absolute paths**: Accept and output absolute paths.
- **Exit codes**: 0 = success, non-zero = failure.
- **Design for agents, not humans**: Output structured data, not formatted text.
- **Progressive disclosure**: Truncated output must include total data size and how to see more. JSON: add `total`/`has_more`/`page_token`. Text: append `(N chars total)` + stderr `HINT:` with continuation command.

## Writing Guidelines

- **Include**: non-obvious procedures, domain specifics, gotchas from real failures
- **Exclude**: things Claude already knows, verbose explanations, auxiliary docs
- **Size**: SKILL.md ≤150 lines; move scenario details to `references/`
- **Litmus test**: "Would removing this line cause Claude to make mistakes?" If not, cut it
