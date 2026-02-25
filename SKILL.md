---
name: skill-dev
description: "Skill 全生命周期管理：创建 → 反思优化 → 评测 → 成熟度判断 → 发布到市场 → 检索多版本 → 选择/安装 → 融合迭代 → 卸载。触发场景：(1) 用户要求创建/修改 skill (2) 发现可提取为 skill 的重复模式 (3) skill 执行出错或用户纠正后需要反思改进 (4) 用户要求发布/搜索/安装/合并社区 skill (5) 反思后自动检查成熟度并建议发布"
---

# Skill Dev

Full lifecycle management for AI agent skills: create, reflect, evaluate, publish, search, install, merge, review, and uninstall.

## Core Principles

### Concise is Key

The context window is a shared resource. Only add context Claude doesn't already have. Challenge each piece: "Does Claude really need this?" Prefer concise examples over verbose explanations.

### Degrees of Freedom

Match specificity to the task's fragility:

- **High freedom** (text instructions): Multiple approaches valid, context-dependent decisions
- **Medium freedom** (pseudocode/scripts with params): Preferred pattern exists, some variation OK
- **Low freedom** (specific scripts): Operations fragile, consistency critical, exact sequence required

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

- **Do** include: non-obvious procedures, domain specifics, gotchas from real failures
- **Don't** include: things Claude already knows, verbose explanations, auxiliary docs
- **Keep** SKILL.md ≤150 lines (routing layer); move scenario details to references/
- **Challenge each line**: "Would removing this cause Claude to make mistakes?" If not, cut it.
- **Prefer examples over explanations**: One concrete pair teaches more than a paragraph
