# committing

快速创建符合 Conventional Commits 规范的 git commit。

## 简介

一个小而聚焦的 skill：分析当前改动，生成或使用指定的 commit message 并提交。

- **message 可自动生成**：未提供时分析 `git diff --staged`（无 staged 则 `git diff`），产出简洁、有意义的 message。
- **也可手动指定**：作为斜杠命令带参数调用，直接用给定文本提交。
- **强制 Conventional Commits**：`<type>[optional scope]: <description>`。
- **无 AI 署名**：commit message 不得携带 Claude 或其它 AI Agent 署名 / 水印（生成后自动检查删除）。

## 适用场景

- 快速提交当前改动，不想手写 message
- 想确保 commit message 符合 Conventional Commits 规范
- 作为斜杠命令 `/commit <message>` 使用

## 安装

```bash
# 安装到当前项目
npx skills add <owner>/my-skills --skill committing

# 全局安装
npx skills add <owner>/my-skills --skill committing -g -y
```

## 使用说明

本 skill 设置了 `disable-model-invocation: true`，**仅作为显式命令调用**（不自动触发），用 `model: haiku` 保证快速低成本。

- **带参数**：直接用给定文本作为 commit message。

  ```text
  /commit feat: add user authentication with JWT
  ```

- **不带参数**：自动分析改动并生成 message。流程：
  1. `git status` 查看状态
  2. 无 staged 内容则 `git add .` 暂存所有变更
  3. `git diff --staged` 检查即将提交的内容
  4. 创建 commit
  5. 显示简要确认信息

## Commit Message 规范

结构：`<type>[optional scope]: <description>`

| 要素 | 规则 |
|------|------|
| **type**（必填，小写） | `feat` / `fix` / `docs` / `style` / `refactor` / `perf` / `test` / `build` / `ci` / `chore` |
| **scope**（可选） | 括号标注影响模块，如 `feat(auth): ...` |
| **description** | 祈使句（`add` 而非 `added`）；首行 ≤60 字符、最多 72 字符；结尾不加句号 |
| **body**（可选） | 与 subject 空一行；每行 wrap ≤72 字符；说 **why** 而非 how |
| **原子性** | 一个 commit 只做一件事；同时修 bug 又加功能应拆成两个 |

## 权限

仅声明使用 git 相关命令的最小权限集：`git status` / `git add` / `git commit` / `git diff`。

## 文件

```
committing/
└── SKILL.md    # 完整输入处理、步骤、格式规范与输出模板
```
