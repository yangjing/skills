---
name: sdd
description: 基于规格的开发（Spec-Driven Development）通用规范集 —— 编写或评审任何规格 / 设计 / 架构文档、设计或变更跨边界契约（API / 事件 / Schema / 权限码 / 错误码）、拆迭代任务与定义契约包、决定后端分层与字段类型落层、命名与权限码、服务依赖与通信协议选型、前端 route 与远程数据接入、i18n 工程约定时使用。即使用户只说「加个接口」「这字段该叫什么」「这段要不要写进文档」「这模块该不该拆」「这条规则放哪」而没提 SDD / 规范 / 契约，也适用。不负责文档一致性审计、术语漂移排查与批量同步（那是 doc-governance skill）。
compatibility: 需要文件系统读写 + shell（python3）；适用于 Claude Code / Codex 风格工作区
metadata:
  domain: spec-driven-development
  output: spec-conformant-docs | contract-first-changes | design-decisions
  scope-note: 本 skill 项目中立。项目路径 / 包名 / 词表 / 命令由调用方仓库的 `sdd.overlay.md` 提供；技术栈落地形态在 `stacks/`。
---

# Spec-Driven Development（SDD）通用规范集

跨边界交付的通用规范：**契约先于实现，文档只写代码无法表达的内容，规则必须可验证**。

规范条款全部在 [`references/`](references/sdd-overview.md) 分册中，本文只做**触发路由**与**执行协议**，不复述任何条款。

## Skill 执行协议

1. **Trigger**：命中 §1 路由表任一行时，MUST 使用本 skill。**写任何文档前 MUST 先过内容准入**（§3）。
2. **Load**：先读本文 §1 定位分册 → 只加载命中行指向的章节 → 该行标注了栈落地形态且项目使用对应栈时，一并加载 [`stacks/`](stacks/README.md) 适配层 → 再按 §4 自动发现项目 overlay。**MUST NOT 预读全部分册**。
3. **Apply**：通用规则以 `references/` 为准；技术栈形态以 `stacks/` 为准；取值与落点以项目 overlay 为准。各分册 §0 有该册自己的执行协议，加载后 MUST 一并遵循。
4. **Conflict / Stop**：规范与代码 / 契约冲突时，**以代码为事实**并回头修订规范。需要新增架构例外、无法判定现行真相、或需扩展受控词表（权限码 action、术语表）时，MUST 停止并报告，MUST NOT 自行取舍。
5. **Output**：交付说明 MUST 点名依据的分册与**章节号**，以及每条关键验收的 Verification Oracle 与 gate 证据形态。
6. **MUST NOT**：MUST NOT 把项目路径 / 命令 / 包名 / 专属权限 action 写进 `references/` 或 `stacks/`；MUST NOT 用 Agent 自述替代 gate 证据；MUST NOT 在分册之间重复定义同一规则。

## 1. 触发路由表

命中即加载对应分册的对应章节。跨领域任务 MAY 命中多行。

| 触发场景 | 加载 | 栈落地形态 |
| --- | --- | --- |
| **写或评审任何文档**（规格 / 设计 / 架构 / overlay / README） | [SPECIFICATION §1.0](references/SPECIFICATION.md#10-文档内容准入第一原则) 内容准入——**第一项，不过即删** | — |
| 文档载体、图示、实现引用与代码摘录、禁 `path:line` | [SPECIFICATION §1.1–1.2](references/SPECIFICATION.md#11-文档载体与图示) | — |
| 设计或变更 Contract Surface（API / 事件 / Schema / 权限码 / 错误码） | [SPECIFICATION §4](references/SPECIFICATION.md#4-sdd-总流程跨边界变更)（总流程）+ [§7](references/SPECIFICATION.md#7-契约类型与统一形状)（契约形状） | [protobuf-connectrpc](stacks/protobuf-connectrpc.md) |
| 写功能规格文档 / BDD 场景 | [SPECIFICATION §4.1–4.2](references/SPECIFICATION.md#41-功能规格文档feature-spec最小结构) + 模板 [`templates/feature-spec.md`](templates/feature-spec.md) | — |
| 日期时间格式、时区归属、区间边界语义 | [SPECIFICATION §6](references/SPECIFICATION.md#6-日期时间格式强制) | — |
| 审计字段、多租户、权限策略契约、存证 | [SPECIFICATION §7.4](references/SPECIFICATION.md#74-审计字段规范强制) · [§9](references/SPECIFICATION.md#9-多租户权限与策略契约强制) · [§10](references/SPECIFICATION.md#10-审计与存证强制) | — |
| **一个域该有多少 RPC / 能否合并 / 粒度下限** | [SPECIFICATION §7.5](references/SPECIFICATION.md#75-服务方法粒度contract-surface-收敛强制) | — |
| 分页口径、cursor / offset 选择、页码控件桥接 | [SPECIFICATION §15](references/SPECIFICATION.md#15-分页) | — |
| 兼容性、破坏性变更、演进窗口 | [SPECIFICATION §11](references/SPECIFICATION.md#11-兼容性与演进跨边界默认兼容模式) | — |
| 质量门禁、测试分层、UAT 记录纪律 | [SPECIFICATION §13](references/SPECIFICATION.md#13-质量门禁通用) | — |
| **维护 / 编写 UAT 文档、覆盖矩阵、自动化证据映射、判定「UAT 已覆盖 / 已签收」** | [SPECIFICATION §13.3](references/SPECIFICATION.md#133-uat-与自动化测试的边界auto-证据规则)（UAT ≠ 自动化测试；AUTO 证据 ≠ 签收） | — |
| **质量专项验收：判定「导出质量 / 兼容性等是否该立专项」、编写验收矩阵或对照证据文档、专项归档时判定矩阵去留与覆盖矩阵回流** | [SPECIFICATION §13.4](references/SPECIFICATION.md#134-质量专项验收矩阵与对照证据)（立项判据 / 产出最小结构 / 归档保留与回流） | — |
| 执行计划归档、规则回流 | [SPECIFICATION §4.6](references/SPECIFICATION.md#46-执行计划归档回流) | — |
| 拆迭代任务、定义契约包、代码生成链、迭代收尾 checklist | [spec-driven-development](references/spec-driven-development.md) | [protobuf-connectrpc](stacks/protobuf-connectrpc.md) §2.3 |
| **评审模块设计 / 判定是否重构 / 新增 service 或 class / 写或改代码注释 / PR 判断代码质量** | [design-philosophy](references/design-philosophy.md)（深模块、信息隐藏、设计两次、十二气味；注释准入 = §8） | — |
| **是否加抽象 / 新依赖 / 新包 / 重写、MVP 范围裁剪、核心架构能否用临时方案、过时代码处置、改 DB schema·API·存储配置是否需审批** | [design-philosophy §14](references/design-philosophy.md#14-实现与依赖取舍基线yagni--依赖最小化--工程纪律)（YAGNI / 依赖最小化 / 工程纪律） | — |
| 新增或重命名概念 / 字段 / 枚举 / 权限码 / 路由；命名争议 | [naming-conventions](references/naming-conventions.md) | [react-tanstack-antd](stacks/react-tanstack-antd.md) §5（路由命名） |
| 设计跨服务依赖、选通信协议、定复制边界、**边界信任模型** | [service-dependency-contract](references/service-dependency-contract.md)（信任模型 = §4.6） | [protobuf-connectrpc](stacks/protobuf-connectrpc.md) §2.2 |
| 后端模块结构、新增 crate / 包、**字段类型落哪层**、handler 里写 SQL 类问题 | [backend-layering](references/backend-layering.md)（类型分层 = §3.5） | [rust-postgres](stacks/rust-postgres.md) |
| 前端 route / Provider / 远程数据 / 组件用法 / 样式 / 金额与日期渲染 | [frontend-conventions](references/frontend-conventions.md) | [react-tanstack-antd](stacks/react-tanstack-antd.md) |
| 多语言能力、命名空间、文案真相源归属、fallback | [i18n-conventions](references/i18n-conventions.md) | [react-tanstack-antd](stacks/react-tanstack-antd.md) §6 |
| **判断某条规则该不该存在 / 是否重复 / 是否可验证 / 该放哪层** | [sdd-overview §2–3](references/sdd-overview.md#2-项目-overlay-边界)（overlay 边界 + 第一性原理审查） | — |
| 项目技术栈不在 `stacks/` 表内 | [stacks/README §2](stacks/README.md#2-新增一个适配层)（新增适配层） | — |

## 2. 三层内容模型

规则、形态、取值分属三层。**写任何规则前先判断归属**，放错层会导致换项目或换栈时整册失效。

| 层 | 收什么 | 变化源 |
| --- | --- | --- |
| `references/` | 换栈、换项目都不变的规则 | 方法论演进 |
| `stacks/` | 换项目不变、换栈就变的落地形态（类型映射、框架 API、生成链） | 技术选型 |
| 项目 overlay | 换项目一定变的取值（路径、包名、词表、命令、迁移策略） | 项目决策 |

判据见 [sdd-overview §2](references/sdd-overview.md#2-项目-overlay-边界)。典型误判：把「所有 id 主键 MUST 是 UUID 或 BIGINT」放进 `stacks/`（它换栈依然成立，属 `references/`）。

## 3. 第一原则：文档内容准入

**文档只写代码无法表达的内容。** 这一条先于本 skill 的一切载体、结构与流程规则——一段内容若不能通过它，写得再规范也是负债。

写下每一段前问一句：**「删掉它，只读代码的人会失去什么？」** 答不上来，或答案是「少打几分钟字」，则 MUST 删。

准入清单、禁入清单、豁免（对外接口 + 推断错误代价高的行为）、临时方案标注义务的完整条款是 [SPECIFICATION §1.0](references/SPECIFICATION.md#10-文档内容准入第一原则)——**唯一真相源，本文不复制**。

## 4. 项目 overlay 自动发现

overlay MUST 命名为 `sdd.overlay.md` 并置于 **skill 安装目录同级**（skill 经 symlink 镜像到其它 skills 树时，以 resolve symlink 后的真实安装目录同级为准）。

加载任一分册前，若该文件存在则 MUST 先读取它作为项目输入（路径、包名、词表、命令、迁移策略、受控 action 清单）；未找到时回退到「调用方在上下文中提供」。发现由命名约定承担，无需在项目 Agent 规则文件中另设触发入口。

骨架见 [`templates/project-overlay.md`](templates/project-overlay.md)。

## 5. Gotchas

这些是**违反后果不明显、但代价高**的点，多数回归缺陷出在这里。

- **章节号是公共引用锚点**。分册的 `§N` 被其它文档、源码注释、门禁脚本引用。改标题或调整章节号会**静默断链**——改之前 MUST 先 grep 全仓该锚点，改之后 MUST 跑链接校验。新增章节优先追加编号，MUST NOT 插队重排。
- **`path:line` 引用会静默失效**。行号随重构漂移，把审计与设计判断指向错误代码。现行规范 MUST 用稳定可 grep 锚点（模块路径 + 类型 / 函数 / RPC method / 表 / 约束名），引用文档用标题锚点。判据 [SPECIFICATION §1.2](references/SPECIFICATION.md#12-实现引用与代码摘录)，可用 §6 脚本检出。
- **BCP 14 关键词 MUST 大写**。小写的 "must" 不是规范性语言，只是叙述。评审时无法区分「硬约束」与「作者语气」。
- **Agent-facing 规则 MUST 写成六段执行协议**（Trigger / Lookup 或 Load / Apply / Conflict 或 Stop / Output / MUST NOT）。文档索引、自动触发规则、review gate、迁移与治理 workflow 都属此类。用解释性段落表达可执行规则会让 Agent 在边界情形上自由发挥。格式见 [sdd-overview §3.3](references/sdd-overview.md#33-agent-facing-规则检查)。
- **摘要一旦带条款正文就必然滞后**。引用其它文档只写「主题 → 链接」，MUST NOT 附带条款正文。带正文的摘要会在真相源更新后变成第二个（错误的）真相源。
- **临时方案 MUST 标注解除条件**。未装配的设计、规划中的形态若与已生效条款并列陈述，评审与验收会把它当作已有防线。
- **契约先于实现，不可倒置**。先写实现再补契约会让契约退化为实现的描述，失去约束力。顺序是硬要求，见 [SPECIFICATION §4](references/SPECIFICATION.md#4-sdd-总流程跨边界变更)。
- **验收 MUST 有 Verification Oracle**。「已测试」「应该没问题」不是证据。只能由人判断的验收 MUST 显式标记为 Human Approval Gate 并写明 evidence 形态。
- **overlay 文件名决定它能否被发现**。扩展某分册的项目文档 MUST 命名为 `<对应文件名>.overlay.md`；无对应通用分册的项目文档 MUST NOT 加 `.overlay`。规则见 [sdd-overview §2.1](references/sdd-overview.md#21-项目-overlay-文件命名)。

## 6. 命令速查

规范符合性检查（改动任一分册、overlay 或项目规范文档后 MUST 跑）：

```bash
uv run <path-to-this-skill>/scripts/check-spec-conformance.py
```

检出五类机械违规：`path:line` 行号锚点、Agent 执行协议缺段、BCP 14 关键词小写、`.overlay.md` 命名违规、文档头缺 Status/Version。默认扫描本 skill 的 `references/` 与 `stacks/`；扩到项目文档：

```bash
SDD_SCAN_ROOTS='docs/designs,docs/specs' uv run <path-to-this-skill>/scripts/check-spec-conformance.py
```

脚本是 [PEP 723](https://peps.python.org/pep-0723/) 自包含形态（依赖声明内嵌，无需 venv）。零第三方依赖，故未装 uv 的环境用 `python3` 直接跑等价。

**扫描面 MUST 限定为 [§4.1.1](references/SPECIFICATION.md#411-体裁边界本结构的适用范围) 的 ①②③ 类规格体裁**。执行计划、运营跟踪、UAT 执行记录、对外文稿、外部参考资料 MUST NOT 纳入——它们不承担文档控制字段义务，英文对外稿里的 "must" 也只是普通英语，纳进来只会产出满屏假阳性，而会误报的 gate 最终会被绕过。`CLAUDE.md` / `AGENTS.md` / 仓库根 `README.md` / ADR 已内置豁免。

C1（行号锚点）例外：它约束的是**引用形态**而非文档体裁，故扫描面 SHOULD 扩到全部现行规范载体，含 Agent 规则文档链——`CLAUDE.md` / `AGENTS.md` 由 harness 按目录注入、Agent 直接照其执行，行号在此漂移的代价与规格文档等同。用 `SDD_CHECKS=C1` 配合更宽的扫描面单独跑：

```bash
SDD_CHECKS=C1 SDD_STRICT_ROOTS=1 \
SDD_SCAN_ROOTS='docs/designs,docs/specs,docs/adr,docs/*.md,CLAUDE.md,apps/*/AGENTS.md' \
  uv run <path-to-this-skill>/scripts/check-spec-conformance.py
```

扫描根支持 glob（`apps/*/AGENTS.md` 覆盖文档链，`docs/*.md` 限定顶层不递归）。CI MUST 加 `SDD_STRICT_ROOTS=1`：写错的 glob 会静默漏掉整批文件，而总数非零让结论看起来照常全绿。

完整选项见 `--help`。**链接与锚点校验不在本 skill**——那是 doc-governance skill 的 `check-links.py`，本 skill MUST NOT 重复实现。

## 7. 参考

- [`references/sdd-overview.md`](references/sdd-overview.md) — 分册总览、overlay 边界（§2）、第一性原理审查方法（§3）
- [`stacks/README.md`](stacks/README.md) — 技术栈适配层清单与新增流程
- [`templates/`](templates/project-overlay.md) — 项目 overlay / Feature Spec / 栈适配层骨架
- [`scripts/check-spec-conformance.py`](scripts/check-spec-conformance.py) — 规范符合性检查
- 文档一致性审计、术语漂移、批量同步、治理 PR 描述 → **doc-governance skill**（本 skill 不承担）
