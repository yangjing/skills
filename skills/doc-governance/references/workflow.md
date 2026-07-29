# 文档治理工作流（三阶段详细）

> 主入口：[`../SKILL.md`](../SKILL.md) · 项目 overlay 模板：[`./REFERENCE.md`](./REFERENCE.md)

本文件是**项目中立**的工作流定义。涉及"权威源 / 系统简称 / 实现约束"具体名称的位置，MUST 由调用方按自己项目的 overlay 填入（见 [`./REFERENCE.md`](./REFERENCE.md)）。

> **overlay 加载（三阶段共用，约定优于配置）**：执行任一阶段前，若 skill 目录同级存在 `<skill-name>.overlay.md`（本 skill 即 `doc-governance.overlay.md`；skill 经 symlink 镜像时以 resolve symlink 后的真实安装目录同级为准），MUST 先读取它作为权威源 / 概念归属 / 协作边界 / 实现约束的项目输入；未找到时由调用方在调用上下文提供。

## 阶段 1：审计（audit）

read-only，输出 audit report。

### 步骤

1. **入权威入口**
   - 读工作区权威规则文件（`CLAUDE.md` / `AGENTS.md` 链）、文档索引与已加载的项目 overlay
   - 识别承载概念定义的总纲 / 附录 / 系统文档

2. **建概念清单**
   - 跟踪：账号 / 身份模型、上下文模型、组织范围、权限、事件、字段名、系统简称、附录
   - 记录每个概念在哪些位置被 定义 / 摘要 / 扩展 / 重复

3. **逐处分类**

   | 分类 | 含义 | 处置 |
   |------|------|------|
   | `canonical source` | 该概念的唯一真实源 | 保留 |
   | `valid summary` | 合理摘要 + 链接到真相源 | 保留 |
   | `valid system-specific extension` | 系统特有扩展 | 保留 |
   | `duplicate that should link out` | 重复内容 | 改链接 |
   | `conflict that needs correction` | 与真相源冲突 | 修正 |

4. **命名漂移检查**
   - 中文叙述 / 英文实体名混用造成的歧义
   - 已废弃字段仍被当作现行字段
   - 不一致或含义不清的系统简称 / 缩写
   - 同主题"现行口径 vs 历史口径"并存

5. **结构与引用检查**
   - 摘要型文档 MUST 链接附录 MUST NOT 重复阐述共享契约
   - 索引 MUST 指向正确的权威文档
   - 历史 PRD / 草稿 MUST 标"历史参考"，MUST NOT 被索引误挂权威入口
   - 多 skill 文档树（如 `.agents/skills/` 与 `.claude/skills/`）MUST 显式说明谁是真相源、谁是兼容映射
   - Agent-facing 规则（索引、触发规则、加载规则、review gate、迁移 / 同步 / 治理 workflow）MUST 写成可执行协议，而不是解释性段落

6. **协作边界检查**
   - 业务入口系统 MUST 说明"由谁定义业务语义与真相来源"
   - 平台底座系统 MUST 说明"承载哪些底层能力 / 不重复定义哪些业务语义"
   - 高耦合链路（在项目 overlay 中点名）MUST 成组检查

7. **实现约束 SSOT 检查**
   - 项目 overlay 中登记的实现约束（如分页、i18n、主题、Proto / seed 生成链路等）MUST 有唯一规范文件
   - 总纲 / 架构 / 执行计划 / README 对同一约束给出不同说法 → 高优冲突
   - 面向 Agent / LLM 的实现约束 MUST 至少包含 Trigger / Lookup 或 Load / Apply / Conflict 或 Stop / Output / MUST NOT；缺项 → 改写为执行协议

8. **跑链接校验**

   ```bash
   python3 <path-to-this-skill>/scripts/check-links.py
   ```

### 输出模板（audit-report）

```markdown
# 文档治理审计：<scope>

## Scope
<本次审计覆盖的文档范围>

## Single Sources Of Truth
- <concept> → <canonical file>
- ...

## Conflicts
- <concept>: <fileA> vs <fileB> — 现行真相是 <X>

## Duplicate Content To Refactor
- <file>:<line> 重复了 <canonical>:<line> — 改链接

## Terminology Drift
- 旧术语 `<X>` 出现在：<files...> → 应改为 `<Y>`

## Collaboration Boundary Drift
- <SystemA> 与 <SystemB> 之间 <能力> 归属不清 — 建议 <X 定义，Y 承载>

## Broken Links
- <file> → <broken-target>（脚本输出）

## Recommended Fix Order
1. <最高优>
2. ...
```

## 阶段 2：同步（sync）

file edits，输出 synchronized-docs。

### 步骤

1. **读权威来源** — 识别该术语 / 字段 / 概念的术语表 / 附录 / 总纲章节

2. **建映射表**

   | old term | new term | 允许保留旧术语的位置 |
   |----------|----------|---------------------|
   | `<旧>` | `<新>` | migration tables / deprecation notes |

3. **逐处分类处置**

   | 出现类型 | 处置 |
   |---------|------|
   | narrative usage | 替换为正式术语 |
   | field definition | 替换或改为引用附录 |
   | migration table | 仅作为废弃映射保留旧术语 |
   | system-specific field extension | 只保留增量内容，共享字段改链接 |

4. **应用更新**
   - 统一正文业务术语
   - 统一共享契约章节的字段名
   - 附录已承载通用字段时 MUST 从系统文档移除重复内容
   - 重复定义 MUST 改为指向权威文档的相对链接
   - 业务入口系统已是真相源时,平台文档 MUST 压缩为"必要说明 + 引用链接"
   - 旧 PRD / 旧草稿 MUST 显式改为"历史参考"
   - 同一实现约束已有专项规范时 MUST 改写次级文档与之一致
   - Agent-facing prose rules MUST 改写为执行协议：`Trigger → Lookup/Load → Apply → Conflict/Stop → Output`，并显式列出 `MUST NOT`

5. **复查引用**
   - 标题 / 编号变化后 MUST 同步更新锚点、索引项、局部引用
   - 回读修改段落 MUST 自然通顺
   - 高耦合系统组 MUST 双向同步边界说明（不可只改一侧）
   - SHOULD NOT 依赖脆弱编号锚点；优先回链文档或稳定标题
   - 多 skill 路径（如 `.agents/skills/` vs `.claude/skills/`）MUST 写清"真相源 / 兼容映射"

6. **必跑链接校验**

   ```bash
   python3 <path-to-this-skill>/scripts/check-links.py
   ```

   零 broken 后才能视为同步完成。

### 同步规则（MUST）

- 文件移动 / 重命名 MUST 用 `git mv`（保留 history）
- 链接 MUST 用相对路径（`./`、`../`）
- 摘要型文档 MUST 简洁
- MUST NOT 删除系统文档独有的业务上下文
- MUST NOT 静默删除迁移说明用的废弃映射
- 业务入口与平台底座同时提到同一能力时，业务语义 MUST 留入口系统，通用能力 MUST 留平台系统
- 术语同步 MUST 同时覆盖业务名词与实现约束口径（具体清单见项目 overlay）
- Agent-facing 文档同步 MUST 保留执行语义：触发信号、检索 / 加载步骤、应用规则、冲突处理、停止条件、输出证据和禁止行为

### 适合处理的目标

- 账号与组织术语
- 上下文术语
- 字段与载荷命名
- 系统简称
- 能力项名称
- 协作边界表述
- 实现约束口径

## 阶段 3：摘要（summary）

输出 change-summary，用于 PR 描述 / 评审 / 交接。

### 输出模板

```markdown
# 文档治理变更摘要：<scope>

## Scope
<本轮变更覆盖范围>

## Canonical Sources
- <concept> → <file>（本轮明确为唯一真实源）

## Terminology Changes
| old | new | 影响文件数 |
|-----|-----|----------|
| `<X>` | `<Y>` | N |

## Structural Changes
- 新增 / 重命名 / 移动：<files...>
- 拆分 / 合并：<details>

## Duplicate Content Removed Or Replaced
- <file>: 删除 N 行重复说明，改为链接 → <canonical>
- ...

## Collaboration Boundary Alignment
- <SystemA> 现承载 <X>；<SystemB> 现仅链接引用
- ...

## Systems Affected
- <System1>: <change>
- ...

## Validation Result
- `check-links.py` 0 broken
- 项目相关 diagnostics（typecheck / linter / 等）通过

## Remaining Risks
- <若有>
```

### 写作规则（MUST）

- 关键改动文件 MUST 点名（含相对路径）
- 唯一真实源 MUST 明确写出
- 删除或收口的重复内容 MUST 描述准确（行数 / 字段 / 章节）
- 区分三类变化（MUST）：
  - `direct content edits` — 直接内容修改
  - `reference/link cleanup` — 引用 / 链接清理
  - `ownership changes` — 归属调整（业务入口 / 平台底座 / 历史参考）
- 跨系统边界变更时 MUST 写"业务语义归 X，底层能力归 Y"
- "现行规范 → 历史参考"角色调整 MUST 显式写明保留链接但不再权威
- 实现约束统一 MUST 点名（指向项目 overlay 中登记的唯一规范文件）
- Agent-facing 规则改写 MUST 点名涉及的 Trigger / Lookup / Load / Apply / Conflict / Stop / Output / MUST NOT 变化

### 校验清单（输出前）

- [ ] 关键改动文档都点名
- [ ] 唯一真实源明确写出
- [ ] 重复内容描述准确
- [ ] 跑过 `check-links.py` 并交代结果
- [ ] 高耦合链路双向同步已确认
- [ ] 残余风险（若有）已列出

## 三阶段衔接

```
audit-report          sync diff             change-summary
  ↓ Recommended         ↓ files modified      ↑ Systems Affected
  Fix Order      →                       →    ↑ Validation Result
  (输入 sync)              (输入 summary)
```

- audit 的 `Recommended Fix Order` MUST 成为 sync 的 todo list
- sync 的 file diff MUST 成为 summary 的 `Structural Changes` / `Duplicate Content Removed` 输入
- summary 的 `Validation Result` MUST 反过来验证 audit 是否完成
