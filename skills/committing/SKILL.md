---
name: committing
description: 快速创建 git commit，message 可自动生成或手动指定
argument-hint: "[可选：commit message]"
disable-model-invocation: true
allowed-tools:
- Bash(git status:*)
- Bash(git add:*)
- Bash(git commit:*)
- Bash(git diff:*)
model: haiku
---

# Task：创建一个 git commit

## Input Handling（输入处理）

若已提供 message：$ARGUMENTS
- 直接使用该内容作为 commit message

若未提供 message：
- 用 `git diff --staged`（若无 staged 内容则用 `git diff`）分析变更
- 生成简洁、有意义的 commit message

## Current State（当前状态，自动检测）

Git status：
!`git status --short 2>/dev/null || echo "Not a git repository"`

Staged changes：
!`git diff --staged --stat 2>/dev/null || echo "Nothing staged"`

## Steps（步骤）

1. 用 `git status` 查看当前状态
2. 若无 staged 内容，运行 `git add .` 暂存所有变更
3. 用 `git diff --staged` 检查即将提交的内容
4. 创建带合适 message 的 commit
5. 显示简要确认信息

## Commit Message Format（格式规范）

结构（Conventional Commits）：`<type>[optional scope]: <description>`

- **type**（必填，小写）：`feat`（新功能）、`fix`（修复 bug）、`docs`（文档）、`style`（格式调整，不影响逻辑）、`refactor`（重构，非新增功能也非修复）、`perf`（性能优化）、`test`（测试）、`build`（构建系统/依赖）、`ci`（CI 配置）、`chore`（杂项）
- **scope**（可选）：用括号标注改动影响的模块/范围，如 `feat(auth): ...`
- **description**（subject line）：
  - 用祈使句（imperative mood），如 `add`、`fix`、`update`，而非 `added`、`fixed`（自查句式：「If applied, this commit will ...」要读得通）
  - 首行建议 ≤60 字符，最多不超过 72 字符（均指半角字符/ASCII 宽度；中文汉字在等宽字体下为双宽，若用中文书写需按此标准的一半估算），避免在各类 git 工具中被截断或换行
  - 结尾不加句号
- **body**（可选，改动较复杂时补充）：
  - 与 subject line 之间需空一行分隔
  - 每行 wrap 在 72 字符（半角）以内
  - 重点说明 **why**（为什么改）而非 **how**（怎么改的——代码 diff 本身已说明）
- **原子性**：一个 commit 只做一件事；若同时修了 bug 又加了功能，应拆成两个 commit
- **无 AI 署名**：commit message MUST NOT 携带 Claude 或其它 AI Agent 署名/水印——包括 `Co-Authored-By: Claude ...`、`Generated with Claude Code`、`🤖` 等 trailer 或标记行（AI 工具常默认追加，生成后需检查删除）
- 示例：
  ```
  feat: add user authentication with JWT
  ```
  ```
  fix(parser): handle empty input without panicking

  Empty strings previously caused an index-out-of-bounds panic
  in the tokenizer. Added an early-return guard instead.
  ```

## Output（输出）

显示简要确认信息：
```
√ Committed: [commit message]
[number] files 
```
