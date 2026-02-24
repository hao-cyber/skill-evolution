# Reflect Mode — Post-Execution Skill Improvement

When a skill execution goes wrong or the user has to correct/guide the outcome, enter reflect mode to capture the lesson into the skill itself.

## Trigger Signals

Automatically enter reflect mode when ANY of these occur:
- Skill execution **failed** (error, wrong output, unexpected behavior)
- User **corrected** the skill's behavior ("不对，应该这样…")
- User provided a **workaround** that bypassed a skill limitation
- You made an **ad-hoc fix** to a skill's script/prompt during execution
- You **bypassed** a skill's guardrail during execution (e.g. editing CLAUDE.md without proper review)
- Skill **should have triggered but didn't** — user manually did something a skill should have handled (silent miss = trigger description too narrow)

## Reflect Process

1. **Identify** — What went wrong? Pin down the root cause:
   - SKILL.md instruction gap or ambiguity?
   - Script bug or missing edge case?
   - Reference/docs outdated or missing?
   - Trigger description too narrow or too broad?
   - Did you bypass another skill's guardrail?
2. **Read** — Re-read the relevant SKILL.md and scripts to confirm the gap exists (don't rely on memory)
3. **Impact scan** — 检查本次修改是否涉及跨 skill 共享概念：
   - 提取要修改的关键词/概念
   - `grep -rl "<关键词>" .claude/skills/` + `grep -l "<关键词>" .claude/CLAUDE.md` 找出引用了该概念的文件
   - 如有其他 skill 或 CLAUDE.md 也引用了同一概念，判断是否需联动修改
   - 在提案中列出扫描结果
4. **Determinism ladder** — 选择正确的修复层级（脚本能做的事不要靠 prompt 指令）：
   - 能内置到 `scripts/` 自动执行？→ 改脚本，删掉 SKILL.md 中对应的手动指令
   - 必须在运行前/后检查？→ 用 hooks 确定性拦截
   - 需要 LLM 判断力（意图理解、权衡取舍）？→ 才写 SKILL.md 指令
   - **反模式**：SKILL.md 写了"必须做 X"，但 X 是确定性操作 → 应该内置到脚本
5. **Propose** — Present a concrete diff-level change to the user:
   - What file to change (SKILL.md / scripts/ / references/)
   - What to add, remove, or modify
   - Why this prevents recurrence
   - 影响扫描结果（"影响 N 个文件，其中 M 个需联动修改"）
6. **Confirm** — Get explicit user approval before editing
7. **Apply** — Make the change, commit, push

## Escalation

- **2 consecutive reflects on same issue** → stop patching. Re-read the skill with fresh eyes and consider if the fundamental approach is wrong.
- **3+ reflects across different issues** → structural problem. Flag to the user: "This skill may need a redesign, not another patch."

## Routing: Model-Specific Issues

When the root cause is a **model deficiency** (not a skill bug), route the fix to `model_guides/` instead of the skill:

1. **Check `MODEL` env var** — identifies the current model (e.g. `glm-4.7`, `kimi-k2.5`)
2. **Ask: would this problem occur with Claude?**
   - Yes → skill bug, fix the skill
   - No → model deficiency, route to model guidance
3. **Determine the model family** — `glm`, `kimi`, `minimax`, `volc` (matches `model_guides/{family}.md`)
4. **Append the lesson** to `model_guides/{family}.md` (create if missing). Format: concise, actionable rule the model can follow
5. Common model deficiencies: hallucinated APIs, missing `await`, wrong indentation, invented file paths, incorrect import names

If unsure whether it's a skill bug or model deficiency, check: did the same skill work correctly with Claude before? If yes → model issue.

## Post-Reflect: Maturity Check

After applying a reflect fix (step 7), check if the skill has reached publish maturity. Read `references/maturity.md` for criteria. If all signals are met and the skill hasn't been published yet, suggest publishing to the user.

## What NOT to reflect on

- One-off issues unrelated to the skill's design (network glitch, transient API error)
- User preference that doesn't generalize ("这次用蓝色" ≠ "永远用蓝色")
- Changes that belong in CLAUDE.md (cross-skill rules) — edit CLAUDE.md directly instead
