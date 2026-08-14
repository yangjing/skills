---
name: doc-governance
description: 文档治理工作流 — 对产品规格 / 技术规范 / 契约口径 / 设计文档 / 指南等所有 Markdown 文档做一致性治理：审计一致性、批量同步术语/字段/链接、生成变更摘要。用户提到"审计文档/检查口径/术语漂移/重复定义/唯一真实源/批量改名/统一字段/按附录收口/避免重复定义/写治理 PR 描述/交接总结"时调用。
compatibility: 需要文件系统读写 + shell（uv 或 python3、git）；适用于 Claude Code / Codex 风格工作区
metadata:
  domain: documentation-governance
  output: audit-report | synchronized-docs | change-summary
  scope-note: 本 skill 项目中立；项目特定权威源 / 系统简称 / 实现约束口径由调用方仓库的 `doc-governance.overlay.md` 提供（见 references/REFERENCE.md）。
---

# 文档治理（doc-governance）

覆盖文档治理三阶段：**审计 → 同步 → 摘要**。

## 何时使用

| 触发短语 | 阶段 |
|---------|------|
| 检查文档口径 / 术语漂移 / 重复定义 / 归属冲突 / 唯一真实源不清 / 审计 Markdown 一致性 | **审计** |
| 批量改名 / 统一字段 / 按术语表或附录收口 / 用链接替代重复定义 / 同步术语 | **同步** |
| 写治理 PR 描述 / 评审说明 / 交接总结 / 概括术语+结构+归属收口结果 / 变更摘要 | **摘要** |

完整阶段 workflow + 输出模板见 [`references/workflow.md`](references/workflow.md)。  
如何在自己的工作区填充本 skill 的项目 overlay（权威源、概念归属、废弃术语映射等），见 [`references/REFERENCE.md`](references/REFERENCE.md)。

## Skill 执行协议

1. Trigger：用户要求审计、同步、统一术语、检查冲突、治理文档或写变更摘要时，MUST 使用本 skill。
2. Load：先读取本 `SKILL.md`、`references/workflow.md`，再按 overlay 自动发现规则读取项目 overlay。
3. Apply：按 audit → sync → summary 执行；用户只要求其中一阶段时只执行该阶段。
4. Stop：发现唯一真源不明、项目 overlay 缺关键权威源、或同步会删除业务上下文时，MUST 暂停并报告。
5. Output：审计输出冲突和修复顺序；同步输出改动文件和校验结果；摘要点名 direct content edits / reference cleanup / ownership changes。
6. MUST NOT：审计阶段不得编辑文件；不得把项目专有规则写进项目中立 skill；不得用解释性段落替代 Agent-facing 执行协议。

**项目 overlay 自动发现（约定优于配置）**：overlay MUST 命名为 `<skill-name>.overlay.md` 并置于 skill 目录同级。当 skill 经 symlink 镜像到其它 skills 树时（如 `.claude/skills/` → `.agents/skills/`，或 skill 主体 vendored 进 submodule 而 `.agents/skills/<name>` 是指向 submodule 的 symlink），overlay 发现按以下优先级：**① 调用方 skills 树内（即 `.agents/skills/` 下的 symlink 同级）的 overlay 优先**——它承载消费方项目落地指针；② 否则回退到 resolve symlink 后的真实安装目录同级。这样 skill 主体可 vendored 进 submodule，而 overlay 留消费方仓。三阶段开始前若该文件存在，则 MUST 先读取它作为项目输入（权威源 / 概念归属 / 协作边界 / 实现约束 SSOT）——发现由命名约定承担，无需在项目 `CLAUDE.md` 另设触发入口；未找到时回退到「调用方把填充后的 overlay 表格作为上下文提交」。

## 核心原则（MUST）

1. **单一真实源（SSOT）** MUST 唯一。一个概念只能在一处正式定义；其他位置 MUST 用相对链接指向真实源
2. **结果驱动写作** MUST 使用 `MUST` / `SHOULD` / `MUST NOT` / `→` / 表 / 命令；MUST NOT 写"为什么/历史背景/推理路径"，除非该文档自身是决策审计型记录
3. **相对链接** MUST 用 `./xxx.md` / `../yyy.md`；MUST NOT 用绝对路径 / 网址指向仓内文件
4. **角色区分** MUST 显式标注"现行规范"vs"历史参考"；旧 PRD / 草稿 / 兼容路径 MUST 标记为历史参考
5. **业务入口 vs 平台底座** MUST 在协作边界文档中显式说明：业务语义归入口系统定义，通用能力归平台系统承载
6. **及时清理** MUST 删除或更新过时内容，保持文档与实现一致；MUST NOT 保留与代码事实矛盾的描述
7. **Agent-facing 规则可执行** MUST 使用执行协议格式；面向 AI Agent / LLM 自动执行、审核或加载的规则必须写清 Trigger / Lookup / Load / Apply / Conflict / Stop / Output / MUST NOT，MUST NOT 只用解释性段落表达

## 行文风格速查

| 项目 | DO | DON'T |
|------|----|-------|
| 句式 | `caller MUST 用 ConnectClient` | "建议使用 ConnectClient,因为..." |
| 决策 | 表格 + 列对照 | 多段文字论证 |
| 流程 | `setup-pg → init-db → start` | "首先...然后...接着..." |
| 命令 | 可执行 fenced code block | 文字描述命令做什么 |
| 头部 | frontmatter / 关联链接 / 实现物料 | 长篇引言 |
| 末尾 | 易错点速查表 | 散落在正文 |
| 单 bin / 模块矩阵 | 单张对照表 | per-bin 分散段落 |
| Agent 执行规则 | `Trigger → Lookup/Load → Apply → Conflict/Stop → Output` | 大段解释"遇到这种情况时应该考虑..." |

## 工作流概览

```
  阶段 1：审计       阶段 2：同步       阶段 3：摘要
  (audit)     →    (sync)        →    (summary)

  read-only        file edits         产出文字
  → 报告           → diff             → PR 描述 / 交接说明
```

三阶段可单独触发，也可串联使用（审计 → 同步 → 摘要）。

## 命令速查

链接与锚点校验（删除文件 / 改名 / 移动文档 / **改章节标题**后必跑）：

```bash
uv run <path-to-this-skill>/scripts/check-links.py
```

校验三类引用：相对链接的目标文件、`#anchor` 章节锚点（GitHub slug 规则）、反引号 `ADR-NNNN` 编号。输出 `BROKEN  <文件>  →  <失效引用>`，无残留时返回 `All links & ADR references OK`；反引号 `.md` 引用另列 `CANDIDATE`（非阻断，需人工判断是过期引用还是前瞻性提及）。CANDIDATE 解析依次按仓根 / 源文件目录 / 末段对齐（唯一命中）；人工甄别后确认无需处理的条目登记进白名单（默认 `<仓根>/.doc-gov-candidate-allowlist`，行格式 = 直接粘贴 CANDIDATE 输出行），登记后不再重报——新增候选 MUST 逐条甄别，MUST NOT 未甄别就入白名单。白名单条目防腐由脚本自动承担：一轮扫描中未被消费的条目（引用已消失 / 目标已落地致豁免多余）以 `STALE` 报出（非阻断），出现时 MUST 回删对应行。

**改章节标题是最隐蔽的断链来源**——它不动任何文件名，却能静默作废一批 `#anchor`，且只在有人点开时才暴露。

工作区可通过环境变量自定义扫描范围：

```bash
DOC_GOV_ROOT=. \
DOC_GOV_INCLUDE='^docs/.*\.md$;^(CLAUDE|README)\.md$' \
DOC_GOV_SKIP_DIRS='node_modules,target,dist,.next,doc_build' \
uv run <path-to-this-skill>/scripts/check-links.py
```

脚本是 [PEP 723](https://peps.python.org/pep-0723/) 自包含形态，零第三方依赖——未装 uv 的环境用 `python3` 直接跑等价。每次运行前会自跑 slug 规则 self-test（单独验证用 `--self-test`）：规则写错时结论不可信，故自检失败 MUST 阻断而非降级为警告。详细配置见脚本 docstring。

## 规则

- 审计阶段 MUST NOT 编辑文件；只产出报告
- 同步阶段 MUST 用 `git mv` 重命名 / 移动文件（保留 history）；编辑后 MUST 跑链接校验脚本
- 摘要阶段 MUST 点名所有改动文件（含相对路径）；MUST 区分 `direct content edits` / `reference/link cleanup` / `ownership changes`
- 旧术语 MAY 保留位置：迁移映射表、deprecation notes、显式标记的历史示例
- 旧术语 MUST NOT 出现在：现行规范正文、当前 RPC / schema 描述、索引入口
- 跨多 skill 文档树（如 `.agents/skills/` 与 `.claude/skills/`）MUST 显式说明"真相源 vs 兼容映射"
- 面向 Agent / LLM 的索引、触发规则、review gate、迁移 / 同步 / 治理 workflow MUST 写成执行协议；产品叙述、ADR 背景、用户手册 MAY 保持人类叙述式写法

## 参考

- [`references/workflow.md`](references/workflow.md) — 三阶段详细 workflow + 输出模板
- [`references/REFERENCE.md`](references/REFERENCE.md) — 项目 overlay 模板（权威源 / 归属 / 废弃术语由调用方填充）
- [`scripts/check-links.py`](scripts/check-links.py) — 链接 + `#anchor` 锚点 + `ADR-NNNN` 校验脚本（PEP 723 自包含，INCLUDE / SKIP / 锚点开关可配置）
