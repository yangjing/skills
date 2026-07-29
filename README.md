# My Agent Skills

> 个人 AI 编程助手（Agent）技能集——通过 [skills.sh](https://www.skills.sh/) / `npx skills` 在 Claude Code、Cursor、Codex、Copilot、Windsurf、Gemini、Cline 等 70+ Agent 间分发复用。

[![skills.sh](https://skills.sh/b/yangjing/my-skills)](https://www.skills.sh/yangjing/my-skills)

本仓库采用 [Agent Skills](https://agentskills.io/) 格式：顶层 `skills/` 目录，每个 skill 一个子目录，含 `SKILL.md`（YAML frontmatter + 指令）与按需的 `references/`、`scripts/`、`evals/`。每个 skill 目录另附 `README.md`，便于在 skills.sh 网站与 GitHub 上展示。

## Skills 一览

### 📚 ebook-ai-notes
读取并精读电子书（epub / pdf），生成仿「微信读书 AI 大纲」风格的中文读书笔记：README 总览 + 每章一份结构化笔记（速览 / 分节精要 / 术语表 / 金句）。
[`README`](skills/ebook-ai-notes/README.md) · [`SKILL.md`](skills/ebook-ai-notes/SKILL.md)

### 🦀 axum-tower
在 Rust 项目中编写或评审 HTTP Web 服务代码时的 axum 0.8 + tower 模式速查与规范（handler / extractor / Router / 中间件栈 / 横切能力 / Common Mistakes）。
[`README`](skills/axum-tower/README.md) · [`SKILL.md`](skills/axum-tower/SKILL.md)

### 🔧 fusions
Fusion Rust 后端框架（`fusions` 及子 crate）的核心库模式与决策规范：依赖注入、类型化 DB 上下文、Axum/ConnectRPC 集成、JWT/MQ/AI、BMC CRUD、RLS 事务。
[`README`](skills/fusions/README.md) · [`SKILL.md`](skills/fusions/SKILL.md)

### 📝 committing
快速创建符合 Conventional Commits 规范的 git commit，message 可自动生成或手动指定，强制无 AI 署名。适合作为斜杠命令使用。
[`README`](skills/committing/README.md) · [`SKILL.md`](skills/committing/SKILL.md)

### 📐 doc-governance
对 Markdown 文档做一致性治理：**审计 → 同步 → 摘要**。发现术语漂移 / 重复定义 / 归属冲突，批量同步收口，产出 PR 描述与交接总结。项目中立，通过 overlay 接入项目专属权威源。
[`README`](skills/doc-governance/README.md) · [`SKILL.md`](skills/doc-governance/SKILL.md)

## 安装

用 [`npx skills`](https://github.com/vercel-labs/skills) 安装到任意支持的 AI 编程助手。

**列出仓库内所有 skill：**

```bash
npx skills add yangjing/my-skills --list
```

**安装单个 skill（最常用）：**

```bash
npx skills add yangjing/my-skills --skill ebook-ai-notes
npx skills add yangjing/my-skills --skill axum-tower
npx skills add yangjing/my-skills --skill fusions
npx skills add yangjing/my-skills --skill committing
npx skills add yangjing/my-skills --skill doc-governance
```

**安装多个 skill：**

```bash
npx skills add yangjing/my-skills --skill axum-tower --skill fusions
```

**安装仓库内全部 skill：**

```bash
npx skills add yangjing/my-skills
```

**全局安装到用户级目录（免提示）：**

```bash
npx skills add yangjing/my-skills --skill fusions -g -y
```

**用完整 GitHub URL：**

```bash
npx skills add https://github.com/yangjing/my-skills --skill axum-tower
```

> 安装前请像审查普通代码一样审查 skill 内容；包含 `scripts/` 的 skill 请留意安全提示。

## 更新

重新运行同一条安装命令即可覆盖更新到最新版本（`npx skills` 会拉取仓库最新内容）。

## 维护：从源仓库同步 skill

本仓库是 skill 的**分发快照**，真相源在各业务仓库（skill 在那里随项目迭代）：

| skill | 源仓库 |
|-------|--------|
| ebook-ai-notes | `~/projects/books/.agents/skills/ebook-ai-notes` |
| axum-tower / committing / fusions / doc-governance | `~/hylxos/.agents/skills/` |

源 skill 更新后，用 [`scripts/sync.sh`](scripts/sync.sh) 把最新内容同步进本仓库。映射表集中在脚本顶部的 `SKILL_SOURCES` 数组，新增/移除 skill 只需改那里。

```bash
# 列出映射表（skill 名 → 源路径）
scripts/sync.sh --list

# 检测哪些 skill 已与源漂移（不改文件；有漂移则退出码 1，适合 CI）
scripts/sync.sh --check

# 同步全部 skill（rsync 覆盖，保留本仓库独有的 README.md）
scripts/sync.sh

# 只同步指定 skill（可多个）
scripts/sync.sh axum-tower fusions
```

**日常同步流程：**

1. 在源仓库（如 `~/hylxos`）改 skill 并 `git commit`（源真相更新）。
2. 回到本仓库跑 `scripts/sync.sh`（或先 `--check` 看漂移范围）。
3. 若源 skill 的功能/用法有实质变化，相应更新 `skills/<name>/README.md`（README 是人工为分发写的，脚本不会覆盖）。
4. `git add -A && git commit && git push`——skills.sh 会在用户下次 `npx skills add` 时自动取到新版。

> 同步设计：脚本 `rsync` 时排除 `README.md`（本仓库为分发人工撰写，源目录没有），且不加 `--delete`，避免误删本仓库独有文件；内容无变化时 rsync 幂等，`git diff` 保持干净。

## 目录结构

```
my-skills/
├── README.md                 # 本文件
├── AGENTS.md                 # Agent 工作区指令
├── skills.sh.json            # skills.sh 网站分组展示配置
├── .gitignore
├── scripts/
│   └── sync.sh               # 从源仓库同步 skill 的快照（--list/--check/同步）
└── skills/
    ├── ebook-ai-notes/       # 电子书读书笔记生成
    │   ├── SKILL.md
    │   ├── README.md
    │   ├── scripts/
    │   ├── references/
    │   └── evals/
    ├── axum-tower/           # axum 0.8 + tower 模式
    │   ├── SKILL.md
    │   ├── README.md
    │   ├── references/
    │   └── evals/
    ├── fusions/              # Fusion 框架规范
    │   ├── SKILL.md
    │   ├── README.md
    │   ├── references/
    │   └── evals/
    ├── committing/           # git commit 生成
    │   ├── SKILL.md
    │   └── README.md
    └── doc-governance/       # 文档一致性治理
        ├── SKILL.md
        ├── README.md
        ├── scripts/
        ├── references/
        └── evals/
```

## Skill 格式约定

每个 skill 目录遵循 [Agent Skills](https://agentskills.io/) 规范：

- **`SKILL.md`**（必需）：YAML frontmatter（`name` 必须等于父目录名、`description` 作为路由规则）+ 面向 Agent 的指令正文。
- **`README.md`**（建议）：人类可读的简介、适用场景、安装与使用说明，用于 GitHub 与 skills.sh 展示。
- **`references/`**（可选）：长文档、模板，按需加载以控制上下文占用。
- **`scripts/`**（可选）：可执行脚本（Python 等）。
- **`evals/`**（可选）：skill 质量评测用例。
