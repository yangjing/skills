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

需要文件系统读写 + shell（`uv` 或 `python3`、`git`）；适用于 Claude Code / Codex 风格工作区。链接校验脚本零第三方依赖，未装 uv 的环境用 `python3` 直跑等价。

## 使用说明

本 skill 面向 AI Agent 自动执行。默认按 audit → sync → summary 串联；用户只要求其中一阶段时只执行该阶段。

**项目 overlay 自动发现**：overlay 必须命名为 `doc-governance.overlay.md` 并置于 skill 目录同级。当 skill 经 symlink 镜像到其它 skills 树（或 skill 主体 vendored 进 submodule）时，**调用方 skills 树内（symlink 同级）的 overlay 优先**，否则回退到 resolve 后的真实安装目录同级——这样 skill 主体可 vendored 进 submodule，而 overlay 留在消费方仓库。三阶段开始前若该文件存在，则先读取作为项目输入（权威源 / 概念归属 / 协作边界 / 实现约束 SSOT）。未找到时回退到「调用方把填充后的 overlay 表格作为上下文提交」。

### 链接校验

删除文件 / 改名 / 移动文档 / **改章节标题**后必跑：

```bash
uv run skills/doc-governance/scripts/check-links.py
```

校验三类引用：相对链接的目标文件、`#anchor` 章节锚点（按 GitHub slug 规则）、反引号 `` `ADR-NNNN` `` 编号。输出 `BROKEN <文件> → <失效引用>`，无残留返回 `All links & ADR references OK`；反引号 `` `.md` `` 引用另列 `CANDIDATE`（非阻断，需人工判断是过期引用还是前瞻性提及）。

> **改章节标题是最隐蔽的断链来源**——它不动任何文件名，却能静默作废一批 `#anchor`，且只在有人点开时才暴露。

可用环境变量自定义扫描范围（`DOC_GOV_INCLUDE` 多模式用分号 `;` 分隔，不可用 `|`，以免与正则 alternation 冲突）：

```bash
DOC_GOV_ROOT=. \
DOC_GOV_INCLUDE='^docs/.*\.md$;^(CLAUDE|README)\.md$' \
DOC_GOV_SKIP_DIRS='node_modules,target,dist,.next,doc_build' \
uv run skills/doc-governance/scripts/check-links.py
```

脚本是 [PEP 723](https://peps.python.org/pep-0723/) 自包含形态，每次运行前会自跑 slug 规则 self-test——规则写错时结论不可信，故自检失败 MUST 阻断而非降级为警告（单独验证用 `--self-test`）。详细配置见脚本 docstring。

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
│   └── check-links.py           # 链接 + #anchor 锚点 + ADR-NNNN 校验（PEP 723 自包含，INCLUDE/SKIP/锚点开关可配置）
└── evals/
    └── evals.json
```
