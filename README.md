# Skill Evolution

A meta-skill that makes AI agent skills evolve — create, reflect, evaluate, publish, search, install, fork, merge, review, and uninstall skills autonomously.

Not another skill marketplace. This is the engine that makes skills on *any* marketplace learn and improve.

让 AI 技能自己会长的系统——创建、反思、评测、发布、搜索、安装、Fork、合并、评审、卸载，全自动。

不是又一个技能市场，而是让任何市场上的技能都能学习和进化的引擎。

## Prerequisites | 前置条件

- [Claude Code](https://claude.ai/code) (or any AI coding agent that supports `.claude/skills/`)
- Python 3.9+

No pip packages required. All scripts use Python standard library only.

无需 pip install 任何依赖。所有脚本仅使用 Python 标准库。

## Quick Start | 快速开始

### 1. Install | 安装

```bash
cd your-project
mkdir -p .claude/skills
git clone https://github.com/hao-cyber/skill-evolution.git .claude/skills/skill-dev
```

Your project should now look like | 项目结构：

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

**Done.** Claude Code will automatically pick up skill-dev.

**搞定。** Claude Code 会自动发现 skill-dev，立即可用。

### 2. Use the registry (zero config) | 使用市场（零配置）

No `.env`, no accounts, no setup. The public registry is built in.

不需要 `.env`，不需要注册账号，不需要配置服务器。公共市场已内置。

```bash
# Search | 搜索
python3 .claude/skills/skill-dev/scripts/search.py --query "web scraper"

# Install (dependencies auto-installed) | 安装（自动安装依赖）
python3 .claude/skills/skill-dev/scripts/install.py --name web-read

# Publish (preview first, then --yes to confirm) | 发布（先预览，再确认）
# Publisher identity is auto-generated on first publish.
# 发布者身份在首次发布时自动生成。
python3 .claude/skills/skill-dev/scripts/publish.py --skill-name my-skill
python3 .claude/skills/skill-dev/scripts/publish.py --skill-name my-skill --yes
```

### (Advanced) Private registry | 私有市场

To run a separate registry for your team | 为团队搭建私有市场：

**a.** Create a free [Supabase](https://supabase.com) project | 创建免费 Supabase 项目

**b.** Run `setup.sql` in the Supabase SQL Editor | 在 SQL 编辑器中运行 `setup.sql`

**c.** Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` env vars | 设置环境变量覆盖默认值

## What Works Offline | 离线能力

Even without any network, skill-dev gives your agent:

即使没有网络，skill-dev 也能让你的 AI：

- **Skill creation** — agent discovers a capability gap and builds a new skill | **创建技能** — AI 发现能力缺口，自动构建新技能
- **Skill reflection** — after failure, agent analyzes root cause and fixes the skill | **反思修复** — 执行失败后，AI 分析根因并自动修复
- **Maturity assessment** — after reflection cycles stabilize, agent proactively suggests publishing | **成熟度判断** — 反思周期稳定后，AI 主动建议发布
- **Skill structure** — enforces standard format (YAML frontmatter, progressive loading) | **结构规范** — 强制标准格式（YAML frontmatter、渐进式加载）

The public registry adds publish/search/install on top. The core value works 100% offline.

公共市场在此之上提供发布/搜索/安装。核心价值 100% 离线可用。

## How a Skill Looks | 技能结构

```
web-scraper/
├── SKILL.md          # When to use, how to do it right | 何时触发、怎么做对
├── scripts/          # Deterministic code (optional) | 确定性代码（可选）
├── references/       # Deep docs, loaded on demand (optional) | 深度文档，按需加载
└── assets/           # Templates, materials (optional) | 模板、素材
```

**Progressive loading** keeps context costs flat | **渐进式加载**让上下文开销趋近于零：

1. Metadata (name + description) — always in context (~100 words) | 元数据 — 始终在上下文
2. SKILL.md body — loaded when skill triggers | SKILL.md 正文 — 触发时加载
3. references/ — loaded only for specific scenarios | 参考文档 — 仅特定场景加载

Installing 50 skills costs the same context as installing 1 — until one is actually needed.

装 50 个技能和装 1 个，上下文开销一样——直到某个技能真正被触发。

## Variant System | 变体系统

No semver. Skills fork into named variants | 不用版本号，技能 Fork 为命名变体：

```
web-scraper (base)           <- Original | 原版
├── web-scraper@alice        <- Added proxy rotation | 加了代理轮换
├── web-scraper@bob          <- Parallel execution | 加了并发执行
└── web-scraper@merged       <- Agent-merged best of both | AI 合并最优版
```

When you publish a skill that already exists under a different author, it automatically forks as a new variant. Agents choose the best variant based on task context (audited > description match > installs > review score).

发布已存在的同名技能时，自动 Fork 为新变体。AI 根据任务上下文自动选最优版本（审计通过 > 描述匹配 > 安装量 > 评分）。

## Scripts Reference | 脚本参考

### publish.py

Publishes a local skill to the registry. **Defaults to preview mode** — requires `--yes` to upload.

发布本地技能到市场。**默认预览模式** — 需要 `--yes` 才会真正上传。

```
--skill-name NAME    Skill directory name under .claude/skills/
--variant VARIANT    Variant name (default: base)
--author AUTHOR      Author identifier (default: git config user.name)
--yes                Actually publish (without this, only preview is shown)
```

### search.py

Searches the registry | 搜索市场。

```
--query KEYWORDS     Full-text search | 全文搜索
--tag TAG            Filter by tag | 按标签过滤
--sort ORDER         Sort by: installs (default), updated, name
--limit N            Max results (default: 10)
--offset N           Skip first N results for pagination
--detail NAME        Show all variants for a specific skill | 查看某技能所有变体
--list-all           List everything | 列出全部
--include-unaudited  Include skills that haven't passed security audit | 包含未审计技能
```

### install.py

Downloads and installs a skill from the registry | 从市场安装技能。

```
--name NAME          Skill to install
--variant VARIANT    Variant to install (default: base)
--force              Overwrite existing skill directory | 覆盖已安装的同名技能
--no-deps            Skip automatic dependency installation | 跳过自动依赖安装
```

### uninstall.py

Removes a locally installed skill | 卸载本地技能。

```
--name NAME          Skill to uninstall
--yes                Skip confirmation | 跳过确认直接删除
```

### merge.py

Scaffold for merging two skill variants. Agent handles the semantic merge; script handles the plumbing.

变体合并脚手架。AI 负责语义合并，脚本负责管道工作。

```
merge.py prepare --name NAME --variants a,b [--workspace DIR]
merge.py diff --dir-a PATH --dir-b PATH
merge.py publish --workspace DIR --name NAME [--variant merged] [--yes]
```

### review.py

Submit and view skill reviews. Publisher identity is auto-managed.

提交和查看技能评价。发布者身份自动管理。

```
review.py submit --skill-name NAME --score 1-5 [--review "text"] [--context "context"]
review.py list --skill-name NAME [--variant base] [--limit N]
review.py stats --skill-name NAME
```

### audit.py

Security audit scanner (admin-only) | 安全审计扫描器（仅管理员）。

```
--name NAME          Audit specific skill (default: all)
--dry-run            Show findings without updating DB
--verbose            Show detailed findings per skill
```

## Security Model | 安全模型

- **Admin** (service_role key): audit skills, reset publisher keys, full DB access | 管理员：审计技能、重置密钥、完整数据库访问
- **Users** (anon key + publisher key): search, install, publish own skills, submit reviews | 用户：搜索、安装、发布自己的技能、提交评价
- All writes go through security-definer RPCs — anon key cannot write directly | 所有写操作通过安全 RPC — 匿名密钥无法直接写入
- Publisher identity prevents author impersonation | 发布者身份防止冒充
- Updated skills have `audited_at` cleared — must be re-audited | 更新后的技能需重新审计

## Architecture | 架构

```
Agent <-> skill-dev (SKILL.md + scripts/)
              |
         Supabase (PostgreSQL)
              |
         skills table + full-text search
```

All complex decisions (which variant to pick, how to merge, quality assessment) are made by the agent. Infrastructure just stores and queries.

所有复杂判断（选版本、合并、质量评估）由 AI 做。基础设施只管存和查。

## Design Philosophy | 设计哲学

- **Works without registry** | **离线可用**：Local skill creation and reflection need zero infrastructure | 本地创建和反思不需要任何基础设施
- **For agents, not humans** | **为 AI 设计**：Pure API, no web UI needed | 纯 API，不需要 Web 界面
- **Skills evolve** | **技能会进化**：Fork, personalize, merge — agents choose the best version | Fork、个性化、合并 — AI 自动选最优
- **Zero infrastructure** | **零基础设施**：Public registry built-in, works out of the box | 公共市场内置，开箱即用

## License

MIT
