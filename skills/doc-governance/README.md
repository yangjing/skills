# doc-governance

对 Markdown 文档做一致性治理：**审计 → 同步 → 摘要**。

## 简介

文档治理工作流 skill，覆盖产品规格 / 技术规范 / 契约口径 / 设计文档 / 指南等所有 Markdown 文档的一致性治理：

- **审计（audit）**：read-only，发现术语漂移、重复定义、归属冲突、唯一真实源不清等问题，输出报告和修复顺序。
- **同步（sync）**：批量改名 / 统一字段 / 按术语表或附录收口 / 用链接替代重复定义，并校验相对链接。
- **摘要（summary）**：产出治理 PR 描述、评审说明、交接总结，点名所有改动文件与收口结果。

三阶段可单独触发，也可串联（审计 → 同步 → 摘要）。

本 skill **项目中立**；项目特定权威源 / 系统简称 / 实现约束口径由调用方仓库的 `doc-governance.overlay.md` 提供（约定优于配置，三阶段开始前自动发现）。

## 适用场景

| 触发短语 | 阶段 |
|---------|------|
| 检查文档口径 / 术语漂移 / 重复定义 / 归属冲突 / 唯一真实源不清 / 审计 Markdown 一致性 | **审计** |
| 批量改名 / 统一字段 / 按术语表或附录收口 / 用链接替代重复定义 / 同步术语 | **同步** |
| 写治理 PR 描述 / 评审说明 / 交接总结 / 变更摘要 | **摘要** |

## 安装

```bash
# 安装到当前项目
npx skills add <owner>/my-skills --skill doc-governance

# 全局安装
npx skills add <owner>/my-skills --skill doc-governance -g -y
```

## 依赖

需要文件系统读写 + shell（`python3`、`git`）；适用于 Claude Code / Codex 风格工作区。

## 使用说明

本 skill 面向 AI Agent 自动执行。默认按 audit → sync → summary 串联；用户只要求其中一阶段时只执行该阶段。

**项目 overlay 自动发现**：overlay 必须命名为 `doc-governance.overlay.md` 并置于 skill 目录同级（若 skill 经 symlink 镜像到其它 skills 树，以 resolve 后的真实安装目录同级为准）。三阶段开始前若该文件存在，则先读取作为项目输入（权威源 / 概念归属 / 协作边界 / 实现约束 SSOT）。未找到时回退到「调用方把填充后的 overlay 表格作为上下文提交」。

### 链接校验

删除文件 / 改名 / 移动文档后必跑：

```bash
python3 skills/doc-governance/scripts/check-links.py
```

脚本默认扫描仓库常见文档目录与根级规范文件，输出 `BROKEN <文件> → <失效链接>`，无残留返回 `All links OK`。可用环境变量自定义扫描范围：

```bash
DOC_GOV_ROOT=. \
DOC_GOV_INCLUDE='^docs/.*\.md$|^(CLAUDE|README)\.md$' \
DOC_GOV_SKIP_DIRS='node_modules,target,dist,.next,doc_build' \
python3 skills/doc-governance/scripts/check-links.py
```

## 核心原则（MUST）

1. **单一真实源（SSOT）唯一**：一个概念只在一处正式定义，其他位置用相对链接指向真实源。
2. **结果驱动写作**：用 `MUST`/`SHOULD`/`MUST NOT`/`→`/表/命令，不写"为什么/历史背景"。
3. **相对链接**：用 `./xxx.md` / `../yyy.md`，不用绝对路径 / 网址指向仓内文件。
4. **角色区分**：显式标注"现行规范" vs "历史参考"；旧 PRD / 草稿标记为历史参考。
5. **审计阶段不编辑文件**；同步阶段用 `git mv` 重命名/移动并跑链接校验；摘要阶段点名所有改动文件。

## 目录结构

```
doc-governance/
├── SKILL.md                     # 执行协议 + 核心原则 + 工作流概览 + 规则
├── references/
│   ├── workflow.md              # 三阶段详细 workflow + 输出模板
│   └── REFERENCE.md             # 项目 overlay 模板（权威源/归属/废弃术语）
├── scripts/
│   └── check-links.py           # 相对链接校验脚本（INCLUDE/SKIP 可配置）
└── evals/
    └── evals.json
```
