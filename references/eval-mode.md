# Eval Mode — Skill Prompt 回归测试

> **Dependency:** This mode requires the `prompt-eval` skill to be installed separately.
> Install it from the registry: `install.py --name prompt-eval`

在修改 SKILL.md 之后，运行评测验证 prompt 改动没有引入回归。

## 边界说明

Eval 测试的是 **SKILL.md 指令的清晰度和路由准确性**：
- 给定用户输入，模型是否按 SKILL.md 指令产出了期望结构/内容？
- 路由是否正确（该触发的触发，不该触发的不触发）？

**不是**端到端测试——真实执行环境（Claude Code SDK、tool 调用、sandbox）无法在 promptfoo 中复现。

## evals.yaml 格式

每个 skill 目录下可放 `evals.yaml`，格式与 promptfoo test case 兼容：

```yaml
# .claude/skills/<skill-name>/evals.yaml
- description: "正常触发：用户要求创建日程"
  vars:
    user_input: "帮我明天下午3点建个会议"
  assert:
    - type: contains
      value: "日程"
    - type: llm-rubric
      value: "应该调用日历相关操作，提取时间和主题"
      threshold: 0.7

- description: "负面：不应触发（纯提醒）"
  vars:
    user_input: "提醒我下午喝水"
  assert:
    - type: not-contains
      value: "创建日程"
    - type: llm-rubric
      value: "应该识别为简单提醒而非会议创建"
```

## 运行流程

1. 读取 `<skill>/evals.yaml`
2. 将 SKILL.md 的正文（frontmatter 之后）作为 system prompt 写入临时文件
3. Prompt 模板使用 `[{{user_input}}]` 包裹 user_input 变量
4. 调用 prompt-eval 的 run_eval.py：

```bash
python3 .claude/skills/prompt-eval/scripts/run_eval.py \
  --prompts <system_prompt_file> \
  --tests <skill>/evals.yaml \
  --task-id <unique-id> \
  --output-dir <output-dir>
```

5. 解读结果：
   - 全部通过 → 改动安全，继续提交
   - 有失败 → 分析是 SKILL.md 改动导致还是 test case 需要更新
   - 向用户报告结果和建议

## 何时运行

- **主动**：修改 SKILL.md 的路由规则、触发条件、核心指令后
- **被动**：用户要求 "测一下这个 skill" 或 "跑个回归"
- **可选**：reflect 修复后验证修复有效

## 编写 evals.yaml 的原则

- 覆盖 **正面**（应触发/应包含）和 **负面**（不应触发/不应包含）
- 优先使用确定性断言（contains、not-contains、regex），llm-rubric 用于语义判断
- 5-15 个 test case 即可，不需要穷举
- 变量名统一用 `user_input`（与 prompt 模板对应）
