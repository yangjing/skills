# SDD 规范（Spec-Driven Development）

> **Status**: active · **Version**: v2.2（2026-07-30）· **Compliance**: L1（默认）
> **适用范围**：面向微服务或单体架构的跨边界交付；不假定编程语言、框架与仓库形态
> **规范语言**：BCP 14（RFC 2119/8174）—— MUST、MUST NOT、SHOULD、SHOULD NOT、MAY
> **定位**：SDD 文档集总纲，**业务与项目无关**。项目路径、命令、词表、迁移策略一律走项目 overlay（边界见 [sdd-overview §2](./sdd-overview.md#2-项目-overlay-边界)）
> **本文不重述**：命名词表 → [naming-conventions](./naming-conventions.md)；服务依赖治理 → [service-dependency-contract](./service-dependency-contract.md)；模块内部设计 → [design-philosophy](./design-philosophy.md)；Sprint 执行物料 → [spec-driven-development](./spec-driven-development.md)

## 0. Agent 执行协议

1. **Trigger**：设计或修改 Contract Surface（API / 事件 / Schema / 权限码 / 错误码）、编写或评审 specs / design 文档、定义跨边界变更流程时，MUST 加载本文。
2. **Load**：只读命中章节，再按 §1.3 读对应规范性来源与项目 overlay；MUST NOT 预读全量 SDD 文档集。
3. **Apply**：通用约束以本文为准，取值与落点以项目 overlay 为准；§1.3 列出的三份文档在其主题域内优先于本文。**任何写入文档的内容 MUST 先过 §1.0 准入**——写什么先于怎么写。
4. **Conflict / Stop**：本文与代码 / 契约冲突时，以代码为事实并回本文修订；需要新增架构例外、或无法判定现行真相时，MUST 停止并报告。
5. **Output**：交付说明 MUST 点名依据章节、每条关键验收的 Verification Oracle 与 gate 证据形态。
6. **MUST NOT**：MUST NOT 把项目路径、命令、crate / bin / app 名、专属权限 action 写进本文；MUST NOT 用 Agent 自述替代 gate 证据。

## 1. 规范语言与文档载体

### 1.0 文档内容准入（第一原则）

**文档只写代码无法表达的内容。** 本节先于本文档集的一切载体、结构与流程规则——一段内容若不能通过本节，写得再规范也是负债：读者要读它，维护者要跟着代码改它，而它本可以由读代码直接得到。

**准入清单（MUST 写）**——五类内容代码表达不了，缺失即知识失传：

| 类别 | 承载什么 | 缺失的后果 |
| --- | --- | --- |
| 意图与规格 | 为什么需要它、它必须满足什么、范围与非范围 | 后来者只能从实现反推需求，把缺陷当特性 |
| 对外契约 | 跨边界的接口、字段、错误码、事件、权限码及其兼容承诺 | 消费方靠猜，破坏性变更无从识别 |
| 决策理由 | 为何这样选、否决了哪些替代方案、代价是什么 | 已被否决的方案被反复重提 |
| 领域术语 | 业务词汇的精确定义与边界，同名异义的消歧 | 同一个词在两个模块指两件事 |
| 运维知识 | 部署形态、环境差异、故障信号与处置、密钥与凭证纪律 | 代码里根本不存在这些事实 |

**禁入清单（MUST NOT 写）**：

- **复述代码逻辑**：函数体、算法步骤、可由读代码直接得到的控制流与数据结构。
- **复述外部标准与官方文档**：协议规范、语言/库的通用用法、通用安装命令序列。MUST 改为链接到权威来源，只保留**本项目做出的选择**。
- **复述已在别处正式定义的条款**：违反 SSOT（§13 docs 门禁）。MUST 改为相对链接；确需摘要时 MUST NOT 附带条款正文——「主题 → 链接」即可，带正文的摘要必然滞后于真相源。

**豁免（即使可推断、即使读代码能得到，也 MUST 写明）**——判据是**推断错误的代价**，不是能否推断：

- **对外接口**：跨边界契约面一律显式写明，消费方不该被要求去读提供方的实现。
- **推断错误代价高的行为**：fail-closed 与降级分支、撤销与失效语义、幂等与重放、顺序与时序依赖、安全与隔离边界、best-effort 与"看起来可靠"的差别。这类行为的默认推断往往是乐观的，而错误后果不可逆。

**标注义务**：临时方案、未装配的设计、规划中的形态 MUST 显式标注为非现行事实，并写明**解除或触发条件**；MUST NOT 与已生效条款并列陈述——评审与验收会把它当作已有防线。

**自检**：写下每一段前问一句——**「删掉它，只读代码的人会失去什么？」** 答不上来，或答案是"少打几分钟字"，则 MUST 删。

### 1.1 文档载体与图示

规格 / 设计 / overlay 文档的载体与图示遵循：

- 文档 MUST 以 Markdown 编写，并确保在仓库采用的 preview / 静态站点工具链（如 mkdocs）下正确渲染——表格、代码块、锚点链接、mermaid 均不破版。
- 关键业务流程或技术流程（实体状态机、跨边界调用链、数据流、关键时序）MUST 用 mermaid 绘制；MUST NOT 用 ASCII art 或仅以散文替代可维护的图示。
- 图示是规格的一部分而非装饰：流程语义变更时，维护者 MUST 同步更新对应 mermaid 图。
- 面向 AI Agent / LLM 自动执行、审核或加载的规则 MUST 写成执行协议，格式见 [sdd-overview §3.3](./sdd-overview.md#33-agent-facing-规则检查)；MUST NOT 只用解释性段落表达可执行规则。

术语一致性、无重复定义、用语精准简练的规范见 §2（术语）与 §13（质量门禁 docs），本节不重述。

### 1.2 实现引用与代码摘录

本节是 [§1.0](#10-文档内容准入第一原则)「禁止复述代码逻辑」在**引用实现**这一动作上的具体化：文档不可避免要指向代码，本节定何为合法指向。

设计 / 规格 / overlay 文档承载技术方案、架构约束、契约意图、数据流、状态机、风险与验收口径；它们不是生产实现的副本。

- MUST NOT 复制生产实现体（函数体 / 具体算法逐行抄录）。文档说明「为什么这样设计、约束与数据流」，「怎么实现」以代码为准。
- MUST NOT 用 `path:line` / `path:line-line`（含 `xx.md:line`）作为现行规范的引用依据——行号随实现 / 重构漂移使引用失效。引用其它文档用标题锚点（`#heading`），不用行号。
- 现有实现引用 MUST 使用稳定可 grep 锚点：文件 / 模块路径、类型 / 接口 / 函数 / 方法名、RPC method / 消息（message）名、数据库表 / 索引 / 约束 / 触发器 / 函数名。
- MAY 使用 mermaid、Gherkin、命令、目录树、接口签名（signature）、类型形状，以及显式标注「示意」的短伪码——这些是设计意图的表达，非实现副本。
- 契约 IDL / SQL DDL 的现行真相源 MUST 回链项目契约目录（具体路径见项目 overlay）；设计文档只保留与设计决策相关的字段 / 约束摘要，MUST NOT 整段复制 schema。
- 适用强度按文档类型分层（项目的文档类型总览见项目 overlay）：
  - 架构规范 / 治理规范 / 权限模型 / 合规（长期 SSOT）：MUST 全面遵循，几乎不含实现代码。
  - 技术设计：MUST 遵循；需要技术细节时用「意图 + 符号引用 + 示意伪码」表达。
  - 调研：MAY 保留较多代码片段（选型对比所需），但仍 MUST NOT 用行号锚定现行规范。
  - 历史归档 / 工作产物：豁免（某时刻快照），但 MUST NOT 被现行规范作为引用目标。

### 1.3 优先级与规范性来源

1. 法规 / 合规 / 安全策略（PIPL / PDPA 等）优先于一切。
2. 下表文档在其主题域内是本文的规范性来源。本文与其不一致时，MUST 以来源为准并修正本文：

| 主题域 | 规范性来源 |
| --- | --- |
| 命名、词表、字段映射 | [naming-conventions.md](./naming-conventions.md) |
| 服务依赖、通信协议 | [service-dependency-contract.md](./service-dependency-contract.md) |
| 模块内部设计准则 | [design-philosophy.md](./design-philosophy.md) |

## 2. 术语（最小集合）

- Bounded Context：DDD 边界上下文（团队/数据/权限边界对齐）。
- Contract Surface：跨边界且可观察/可持久化的接口面（API、事件、Schema、权限码、错误码）。
- Compatibility Mode：混合版本现实下的演进模式；跨边界默认处于兼容模式。
- SoR（Source of Record）：某类事实的唯一写入权与语义演进责任方。
- Producer / Consumer：事实生产方（SoR）与消费方（决策/查询/编排）。
- Read Model：为查询/决策优化的只读视图（复制/事件投影/物化视图）。
- Verification Oracle：能够以可追踪、可重复方式判定某项验收是否成立的权威机制，例如类型检查、静态分析、契约生成一致性、自动化测试、人工 approval 记录。
- Human Approval Gate：当产品意图、业务取舍、合规判断或其它非机械判定事项无法由 Verification Oracle 自动判断时，由明确负责人做最终确认的显式停顿点。

## 3. 仓库与运行时边界

代码仓库形态（mono-repo / multi-repo / submodule）MAY 按团队治理与合规要求选择；本文不作强制假定。若使用 git，MUST 设置以下 hooks：

- pre-commit：运行代码格式化、静态分析、单元测试等。
- pre-push：运行软件供应链检查、端到端测试或集成测试等。

运行时边界（概念模型）：

- 接入层：南北向入口。是否设置统一网关 / BFF 属架构选择，见 [service-dependency-contract §4.6](./service-dependency-contract.md#46-边界信任模型项目-must-择一并落-adr)
- 领域服务：按 Bounded Context 划分（东西向）
- 共享能力：跨域基础设施（数据平台等）
- 治理能力：审计与存证

## 4. SDD 总流程（跨边界变更）

本节定义跨边界变更的规范流程；其 Sprint / Milestone 可执行落地（proto 骨架、代码生成链、目录结构、迭代 checklist）见 [spec-driven-development.md](./spec-driven-development.md)。

对任何 Contract Surface 的变更（新增/修改/废弃）：

- MUST 先更新契约（Proto 定义/字段与语义/错误码/权限码/测试 fixtures），再实现代码。
- MUST 明确 Producer(SoR) 与 Consumer，以及兼容窗口与回滚方案。
  - 项目未发布 1.0 之前可以不考虑兼容窗口与回滚方案。
- MUST 为关键验收列出 Verification Oracle；若验收只能由人判断，MUST 标记 Human Approval Gate 及其 evidence 形态。
- MUST 以迭代单元（Sprint / Milestone）执行「契约冻结 → 并行实现 → 集成验收」的顺序；MUST NOT 先写实现再补契约。

### 4.1 功能规格文档（Feature Spec）最小结构

每个跨边界功能 SHOULD 先写规格文档（可放在仓库约定的 `specs/` 或 `docs/specs/` 目录），结构必须可被机器提取。

规格目录组织（`<specs-root>/` = 项目约定的规格根目录）：

- `<specs-root>/` 根 MUST 以 `README.md` 作为规格目录的说明与子文档索引（总纲体裁，§4.1.1）。
- 每个系统 / 能力 MUST 使用独立子目录 `<specs-root>/<system>/`，主规格固定命名 `main.md`（系统主要功能说明）；MUST NOT 以集中式公共子目录（如 `systems/`）平铺多个系统的规格文件。
- 系统复杂需要拆分多份文档时，拆分文档与 `main.md` 同目录，并 MUST 以该目录的 `README.md` 作为文档索引；仅有 `main.md` 的系统无需 `README.md`。
- 跨系统总纲 / 词表类文档（体裁见 §4.1.1）直接放 `<specs-root>/` 根。

规格文档结构：

- 文档控制：Title、Status(draft|active|deprecated)、Owner、LastUpdated、Compliance(L0|L1|L2)
- 目标：Why、InScope、OutOfScope
- 边界：BoundedContext、Producer(SoR)、Consumer、依赖强度（运行时强依赖/事实输入/治理/可选增强）
- 契约：API/事件/Schema/错误码/权限码/策略字段映射（概念↔API↔策略）
- 场景：Given/When/Then（见 4.2 BDD 场景原则）
- 数据：数据所有权、复制/一致性（如有）、MaxStaleness（如有）
- 开发与测试资产：测试 fixtures、`schema.sql`、`seed.sql`（若项目采用重建库模式）
- 验证：Acceptance ↔ Verification Oracle ↔ Evidence；无机器判定者时标记 Human Approval Gate
- 安全与审计：最小权限、敏感数据口径、审计点与 proof 口径
- 演进：兼容窗口、灰度/回滚、废弃策略

Compliance 分级判据（按文档所辖 Contract Surface 与数据面的最高敏感度取档）：

| 档 | 判据 | 治理要求 |
|----|------|---------|
| L0 | 不涉及个人数据与受监管业务行为（纯技术 / 工具 / 流程文档） | 常规评审 |
| L1（默认） | 涉及一般个人数据（PII）或常规业务规则 | 标准安全基线与审计（§12 / §10） |
| L2 | 涉及受监管高敏数据（如 PHI / 医疗健康）、法定义务（如知情同意、临床问责）或监管注册边界（如 SaMD） | 变更 SHOULD 经合规负责人复核并留痕（Human Approval Gate）；合规负责人由项目 overlay 指定，未指定时由文档 Owner 承担 |

#### 4.1.1 体裁边界（本结构的适用范围）

文档分三种体裁，各自适用不同结构要求。体裁由**文档自身承载什么**判定，与它落在哪个目录无关。

**① 功能 / 系统规格** —— 有自身行为、契约与验收，且**承载产品功能范围**：适用 §4.1 全结构 + §4.2 BDD 场景。

**② 总纲 / 索引 / 词表**（架构总纲、目录索引、概念模型入口、术语表）：

- MUST NOT 强套 §4.1 结构——此类文档没有自身 contract surface 与行为面，强套的结局只有两种：复述下游规格的真相源（制造第二真实源，违反 [sdd-overview §3.4](./sdd-overview.md#34-审查清单) 审查项），或产出无信息量的空场景。
- MUST 保留文档控制字段（Status / Owner / LastUpdated / Compliance），使治理工具可对文档目录做统一提取。
- MUST 遵守单一真实源指针纪律：只链接、不复述；本文档回答哪些问题、把哪些问题委派给哪个真相源，SHOULD 在文首显式声明。

**③ 技术设计 / 架构裁决** —— 有自身的技术不变式与验收，但**不承载产品功能范围**（技术选型、分层与归属、契约分层、机制裁决、装配口径等）：

- MUST 保留文档控制字段（同 ②）。
- MUST NOT 复述所辖功能规格的 Why / InScope / OutOfScope 与产品取舍——那些字段归对应的 ① 类文档。**强套 §4.1 全结构即制造第二份功能范围声明**，与 ② 的禁令同源。
- MUST 提供「验收 ↔ Verification Oracle ↔ Evidence」表：技术不变式若无判定者，它就只是一段主张。
- BDD 场景按文档是否引入**新的跨边界不变式**分档：
  - 引入者（可被测试 / 静态检查机械验证的 MUST / MUST NOT 条款）—— MUST 为每条此类不变式提供 BDD 场景，且 MUST 覆盖其**拒绝 / fail-closed / 降级**分支。
  - 只承载落地口径与装配说明、不引入新不变式者 —— BDD 场景 SHOULD；验收或测试落点表仍是 MUST。
- §4.2 的「异常路径 ≥ 正常路径 × 1.5」对本体裁降为 **SHOULD**：架构裁决的场景多为不变式断言，正常路径本就稀少，按比例凑数只会灌水。**但上一条的「失败分支 MUST 有场景」不降级**——比例是手段，覆盖失败路径才是目的。

判据：**承载产品功能范围 → ①；是地图（系统关系 / 索引 / 词表）→ ②；有技术不变式但不定功能范围 → ③**。BDD 纪律落在行为与不变式所在的文档，不落在地图上。项目侧各目录文件的逐份归类由项目 overlay 登记。

### 4.2 BDD 场景原则

规格契约 MUST 采用 BDD 风格（Given/When/Then）编写场景，并遵循以下原则（本节按 §4.1.1 ① 类文档写；③ 类「技术设计 / 架构裁决」的分档与比例降级见 [§4.1.1](#411-体裁边界本结构的适用范围)）：

- 异常路径数量 MUST 至少为正常路径数量的 1.5 倍（③ 类降为 SHOULD）
- 最少覆盖场景：成功、权限拒绝、参数校验失败、依赖降级/超时、回滚/补偿
- 每个场景 SHOULD 指明 Verification Oracle；无法机械验证的产品判断 MUST 回到 Human Approval Gate。
- **Oracle MUST 跑在能产出反例的载体上**：判据若在当前测试数据集上**恒真**（例「越界主体被拒」跑在只有一个主体的库上、「筛选生效」跑在没有筛选入口的调用面上），它的「通过」不构成证据。MUST 先把反例前提建出来再断言——否则整类缺陷会以「测试全绿」的形式长期存在，而这种缺陷比报错更难发现。
- BDD / Gherkin 在本文中是规格表达格式，不等于必须采用 Cucumber 或其它 BDD runner；自动化绑定方式由项目 overlay / 测试架构文档决定。
- AI Agent MUST 将场景映射为 `Acceptance → Verification Oracle → Evidence`；可自动化场景落到项目既有测试 runner，不可自动化场景保留 Human Approval Gate。

### 4.3 并行开发约束

在迭代单元（Sprint / Milestone）内，为支持前端 / 后端 / BFF / 上下游并行开发：

- MUST 先冻结契约包，再拆分实现任务。
- 契约冻结后，前端、后端、BFF、上下游联调任务 SHOULD 使用 `git worktree` 或等效隔离工作区并行推进。
- 契约包 MUST 至少包含：Feature Spec、`.proto`、测试 fixtures、错误码、权限码、BDD 场景，以及项目采用的开发与测试数据资产。
- 任何破坏契约语义的改动 MUST 回到契约层修订并重新冻结；MUST NOT 仅在实现层临时打补丁规避。
- 跨计划 / 跨迭代依赖：下游的前置判据 MUST 取上游「已交付」而非「已立项」，且下游开工前 MUST 用**已建成**的上游能力对自身范围逐项做开工准入实测——承载力与表达力缺口只有对着已建成的实现比对才会暴露，立项文档上不可见。

### 4.4 开发数据策略

对需要快速迭代并在每个迭代末进行真实集成验收的项目：

- 前端业务运行链路 MUST 使用真实 ConnectRPC client 调用后端服务；页面 / 组件 / `.queries.ts` / hook MUST NOT import 项目 fixtures 包或 fixture 源文件。
- 前端业务层 MUST NOT 编造静态业务数据，MUST NOT 使用 `try → fallback fixtures` 掩盖 RPC 失败；后端 stub 返回空响应时，前端按真实响应自然进入 Empty 状态。
- 测试 fixtures 仅是测试资产，只允许 API 测试、E2E、组件测试或单元测试 import；不得进入应用运行 bundle。
- 若真实后端/API 预期会在同一迭代内可用，MUST NOT 为并行开发额外建设和维护 mock 服务 API。
- 若项目采用「重建数据库」模式，MUST 将 `schema.sql` 与 `seed.sql` 作为该迭代的规范资产，并通过容器化方式验证可重复重建。
- 每个迭代末 MUST 以真实服务和真实接口完成 E2E 集成测试或人工验收；测试 fixtures 仅用于自动化测试构造输入 / 断言，不作为业务运行时数据源。

### 4.5 设计两次门槛（契约冻结前）

跨边界 / 跨模块 / 难以撤销的设计 MUST 在契约冻结**前**完成「设计两次」。候选方案的构成与对决方法见 [design-philosophy §7](./design-philosophy.md#7-设计两次design-it-twice)，本节只固定流程门槛：

- 契约冻结 MUST NOT 早于候选方案对决完成。
- 实施阶段 MUST NOT 切换方案；联调发现契约缺陷 MUST 回到契约层修订（§4.3），MUST NOT 仅在实现层打补丁。

### 4.6 执行计划归档回流

执行计划、完成报告和临时 review 记录 MAY 作为历史审计材料，但 MUST NOT 作为现行规格或实现约束的引用目标。跨边界能力交付完成后，团队 MUST 把仍然有效的规则回流到对应规格文档，并把历史计划降级为非权威材料。

**本节是回流规则的唯一真实源**；Sprint / Milestone 流程中的执行位置见 [spec-driven-development §2.6](./spec-driven-development.md#26-完成计划回流)。

**执行协议**：

1. **Trigger**：计划从 active 转 completed、完成报告生成、长期文档引用 completed 计划、或代码 / 契约与计划描述不一致时，MUST 执行回流。
2. **Load**：读 completed 计划、当前代码 / 契约 / 测试证据，以及对应产品规格 / 设计文档 / 项目 overlay。
3. **Assess**：**回流是「按需」动作**。逐去向（specs / designs / SDD）判定是否存在**仍有效且尚未落到 SSOT** 的规则，只回流需要的。判为无需回流的常见情形 = 纯执行无规则产出、结论已在功能提交时回流、结论已被后续 PR 覆盖或作废。
4. **Apply**：只迁移仍被当前实现和契约验证的规则。技术实现约束 MUST 并入设计文档或项目 overlay；产品 / 功能行为 MUST 并入产品规格；可跨项目复用的协作规则 MUST 并入 SDD 文档集。一次性执行步骤、分支名、验证日志、临时 TODO 和过期路径 MUST 留在历史材料。
5. **Conflict / Stop**：计划与当前代码、契约或测试冲突时，MUST 先确认根因，并以当前实现和契约为准；无法判定现行真相时 MUST 停止并请求维护者决策。
6. **Output**：归档总结 MUST 点名已回流的 SSOT、保留为历史参考的文件、删除或标注的过时口径；**Assess 判为无需回流的去向 MUST 记录判定与理由**，供后续治理免于重复判断。
7. **MUST NOT**：MUST NOT 为满足回流步骤复制已在 SSOT 的内容；MUST NOT 把代码路径、表结构、索引名、函数名、PR / commit / 批次 / 实施阶段写进产品规格与设计文档；MUST NOT 让现行 specs / designs / overlays / UAT / ADR / TODO 链接完成计划作为规范依据。

**归档清理**：完成计划中的执行步骤、批次拆分、commit、测试日志和临时裁定 SHOULD 删除，或保留在显式历史归档中；若保留，文档头部 MUST 标记为历史参考，且 MUST NOT 被索引挂为权威入口。删除或移动完成计划后 MUST 跑文档链接校验——broken link 即回流未完成的证据。

```gherkin
Feature: 执行计划完成后的规格回流

Scenario: 完成计划包含仍有效的跨边界约束
Given 一个完成计划描述了已经落地的 API、Schema、权限、错误码、消息或工作流语义
When 该计划从 active 状态转为 completed 或等价历史状态
Then 维护者 MUST 把仍有效的约束合并到 Feature Spec、产品规格、设计文档或项目 overlay
And 维护者 MUST 把旧计划中的「执行步骤、分支名、临时评审意见、一次性验证日志」留在历史材料，不复制进现行规范
And 其它文档 MUST 链接现行规格，MUST NOT 链接历史计划作为规范依据

Scenario: 完成计划已回流并准备删除
Given specs / designs / overlays 已承载该能力的现行约束
When 维护者删除或移动 completed plan
Then 维护者 MUST 更新所有入站链接到长期真相源
And 文档链接校验 MUST 通过
And UAT / ADR / TODO / index MUST NOT 把 deleted plan 当作规范入口

Scenario: 代码实现与历史计划冲突
Given 当前代码、契约或 seed 已经与完成计划中的描述不一致
When 文档治理或功能变更复核该主题
Then 维护者 MUST 以当前代码实现和现行契约为事实来源修正规格
And 维护者 MUST 删除或标注过时叙述
And 维护者 MUST NOT 为了保留历史计划而复制错误口径

Scenario: 完成计划无有效可回流规则
Given 完成计划的结论已全部在现行 specs / designs / SDD 中，或计划未产生新的跨边界约束
When 该计划转为 completed
Then 维护者 MUST 逐去向确认后判定「无需回流」
And 维护者 MUST 把该判定与理由记录在计划中，供后续免于重复判断
And 维护者 MUST NOT 为满足回流步骤而复制已有规范
```

## 5. 命名与字段映射（强制）

命名分工与大小写以 [naming-conventions.md](./naming-conventions.md) 为准；本文只固定最低约束：

- 概念/文档层：PascalCase；缩写全大写（ID/API/PDP 等）
- API/schema 层：snake_case；枚举值 snake_case
- 策略契约层：`namespace.snake_case`（如 subject./resource./grant./env./context.）

跨层字段映射必须显式写成三列（概念 ↔ API/schema ↔ 策略契约），避免实现层「二次翻译」。

## 6. 日期时间格式（强制）

标准本身（ISO 8601 / RFC 3339 的语法）不在此复述，本节只定**本规范做出的选择**。

### 6.1 wire 与存储形态

- 纯日期字段 MUST 用 `yyyy-MM-dd`，纯时间 MUST 用 `HH:mm:ss`（24 小时制）。
- 日期时间字段在 API 上 MUST 用 **RFC 3339 含时区**字符串；MUST NOT 传无时区的本地时间。
- 数据库存储 MUST 为 **UTC**。若 DB 支持带时区的日期时间类型，MUST 选带时区的；不支持时 MUST 以 **UTC 毫秒整数**存储并在应用层统一转换。
- API 响应 MUST 直接返回上述标准形态；**转换成本归调用方**，服务端 MUST NOT 按调用方时区预渲染。

> 前端控件 ↔ wire ↔ 数据库列的完整类型映射见 [backend-layering §3.5](./backend-layering.md#35-数据类型分层强类型原则)，本节不重复第二份表。

### 6.2 时区归属

| 场景 | 时区 |
| ---- | ---- |
| 数据存储 / 日志记录 | UTC |
| API 传输 | RFC 3339 含时区 |
| 前端展示 | 调用方按本地时区自行转换 |
| 报表导出 | 按租户配置时区 |

### 6.3 区间与边界语义

推断错误代价高，MUST 显式约定：

- 时间范围查询 MUST **左闭右开**：开始时间含（`>=`），结束时间不含（`<`）。
- `00:00:00` 属于当天。

业务口径的日期计算（计费折算、天数含端点约定、年龄与闰年生日归一等）随业务语义变化，MUST 由项目 overlay 或产品规格定义，MUST NOT 写入本通用规范。

## 7. 契约类型与统一形状

### 7.1 API 契约定义语言

MUST 使用 [Protocol Buffers](https://protobuf.dev/) (`.proto`) 作为 API 契约的 source of truth，通过 [Buf](https://buf.build/) 或等价工具链生成多语言代码。ConnectRPC 三协议（Connect + gRPC + gRPC-Web）统一由同一份 Proto 定义服务。

| 生成目标 | 产物 | 用途 |
| --- | --- | --- |
| 服务端消息类型 | 语言原生 message / view 类型 | Protobuf 运行时 |
| 服务端 stub | service trait / interface + client + dispatcher | RPC 框架集成 |
| 客户端 SDK | TypeScript / Kotlin / Swift / Java 等目标语言类型和 client | 前端、移动端或 Node.js API client |
| OpenAPI 文档 | OpenAPI 3.x YAML / JSON | API 文档与工具链消费（可选） |

约束：

- API 定义 MUST 以 `.proto` 文件为单一来源；所有生成代码均为产物，MUST NOT 手动修改。
- Proto 定义 MUST 通过 `buf lint` 和 `buf breaking` 验证格式一致性和向后兼容性。
- 项目 MUST 在自己的 overlay 中声明契约目录、Buf workspace、生成命令与 CI gate；通用 SDD 不固定仓库路径。
- 代码生成 MUST 通过可重复的生成命令执行，生成配置 MUST 在项目代码库中锁定。
- Proto 包 MUST 版本化命名：`identity.v1`、`access_control.v1`（示例）。
- CI MUST 验证生成产物的一致性（签入生成代码时 MUST 与 `buf generate` 输出一致）。
- **服务间 RPC 调用 MUST 使用 codegen 生成的客户端和类型**：禁止通过通用 HTTP client + 手拼 JSON 调用 ConnectRPC 端点。请求构造、header / metadata 传递、响应解析和客户端集中管理方式由项目 overlay 固化。

### 7.2 Connect 协议（南北向 + 东西向，默认）

ConnectRPC 统一三协议（Connect + gRPC + gRPC-Web），同一 handler 同时服务浏览器、移动端和微服务。除文件上传 / 下载与流媒体传输可走专项协议外，前后端交互与后端服务间交互 MUST 使用 ConnectRPC；默认启用 HTTP/2。

- **南北向**（浏览器/APP → 后端）：Connect 协议，默认 HTTP/2；浏览器直连无需 gRPC-Web 代理
- **东西向**（微服务间）：ConnectRPC over HTTP/2，由项目选定的 ConnectRPC 实现统一处理 gRPC / Connect / gRPC-Web 协议族
- MUST 使用 Protobuf 序列化（二进制或 JSON）；字段命名 snake_case。
- MUST 明确：认证方式、租户作用域、权限码、审计要求、幂等策略（如需要）。
- 项目若设有 BFF / 编排层，跨域聚合 SHOULD 放在该层，避免领域服务隐式耦合；无该层时聚合 SHOULD 由调用方完成，MUST NOT 让领域服务互相拉取以拼装视图。
- 成功响应 MUST 使用标准 HTTP 状态码（Connect 协议自动映射）。
- 错误详情格式：`code`（Connect 错误码字符串）、`message`（人类可读描述）、`details`（强类型 Protobuf 错误详情）。

约束：

- 错误 MUST 使用 [Connect / gRPC 标准错误码](https://connectrpc.com/docs/protocol/#error-codes)（与 gRPC status code 完全一致，到 HTTP 状态码的映射由协议规定，本文不复制该表）；**MUST NOT 自定义错误码**。
- code MUST 稳定、可枚举；message MUST 面向调试但不得包含敏感明文。
- **业务语义细分 MUST 走 `details` 的强类型详情（如 `ErrorInfo.reason`）或项目约定的 metadata，MUST NOT 靠 message 文案判别**——文案是给人看的，不是协议。同一业务错误的 wire code 可能与直觉不符，调用方按 code 分流会误判。
- MUST 优先用「消除错误路径」重设计 API 语义（Define Errors Out of Existence），而非新增错误码；详见 [design-philosophy.md §6](./design-philosophy.md#6-把错误从语义里消除define-errors-out-of-existence)。典型反模式：把 `unimplemented` / `internal` 当作设计选择，或为「看起来健壮」而抛异常 —— 每多一条异常路径，调用方多一条必须考虑的分支。

### 7.3 Protobuf 演进规则（Proto 字段变更，强制）

- MUST 仅新增字段；MUST NOT 重用字段号；删除用 `reserved`；语义变化视为破坏性变更并升 v2。
- MUST 用于在线命令/强约束交互；MUST NOT 用于高频事实读取（高频读走 Read Model）。
- 字段编号 MUST 在同一 message 内唯一且单调递增（不回收已用编号）。
- 消息定义 SHOULD 使用 Protobuf Editions 2023+；若目标语言或生成工具尚不支持，项目 overlay MUST 声明降级语法与兼容策略。

### 7.4 审计字段规范（强制）

所有跨边界暴露的持久化聚合根 / 实体 message MUST 在消息末尾直接内嵌审计字段，不得复用 `created_at / updated_at / created_by / updated_by` 字段编号。值对象、纯输入 message、嵌套响应壳不强制携带审计字段，除非项目 spec 明确要求。

**字段约束**：

| 字段         | 类型   | 约束 | 说明                           |
| ------------ | ------ | ---- | ------------------------------ |
| `created_at` | string | MUST | RFC 3339 时间戳                |
| `updated_at` | string | MUST | RFC 3339 时间戳                |
| `created_by` | string | MAY  | 操作人 user_id，匿名操作可为空 |
| `updated_by` | string | MAY  | 操作人 user_id，匿名操作可为空 |

**使用方式**：

```protobuf
message Order {
  string id = 1;
  string tenant_id = 2;
  string customer_name = 3;
  // ... 业务字段 4-9
  string created_at = 10;
  string updated_at = 11;
  string created_by = 12 [features.field_presence = EXPLICIT];
  string updated_by = 13 [features.field_presence = EXPLICIT];
}
```

**约束**：

- 审计字段必须位于消息末尾，连续排列。
- 字段编号在同一 message 内必须唯一且单调递增。
- 项目未发布 1.0 前，内部契约 MAY 在项目 overlay 中声明更宽松的编号兼容策略；对外契约进入兼容窗口后不得重用字段号。
- 禁止使用 `message AuditFields` 组合方式。

### 7.5 服务方法粒度（Contract Surface 收敛，强制）

Contract Surface 的规模 = 服务方法数。方法数不是中性计数：每个方法都是**调用方要理解的一条分支**、**权限模型要覆盖的一个授权单元**、**能力 / 端点治理目录要标注的一条注册项**（风险等级、数据分级、幂等与补偿语义）。因此方法数的增长会同时放大集成成本、授权面与治理成本。

**方法 MUST 按「动作」切分；MUST NOT 按「状态跃迁」或「聚合根」切分。**

合并规则（强制）：

| # | 场景 | 反模式 | 正确形态 |
| --- | --- | --- | --- |
| 1 | 同一动作的不同**结果** | `Approve` / `Reject` 各一个方法 | 一个方法 + 结果字段（拒绝态的理由字段服务端校验非空） |
| 2 | 同一动作的不同**终态** | `Cancel` / `Close` 各一个方法 | 一个方法 + 终态枚举 |
| 3 | 同一阶段的**多字段写入** | 每个字段一个 `SetXxx` | 一个方法承载该阶段的字段集 |
| 4 | 两个聚合根上**语义同构**的动作 | 每个聚合各切一套（读面、登记面成对复制） | 归属多态的一个方法：用 `oneof` 承载归属与差异化载荷 |

合并后的差异 MUST 由**枚举或 `oneof`** 承载，MUST NOT 退化为自由字符串参数——那等于把类型约束换成运行时字符串比对。

**粒度下限（MUST NOT 越过，三条边界任一被跨越即 MUST 拆开）**：

1. **风险边界**：合并后的方法 MUST 能标注**单一**风险等级（可逆写 / 不可逆 / 高危领域动作）。把「撤销一份草稿」与「不可逆的跨聚合改写」并进同一方法，会让治理目录只能取其一标注。
2. **授权边界**：当接口与授权单元一一对应（一个方法对应一个权限码）时，合并方法即合并授权。跨越不同授权意图的方法 MUST NOT 合并——除非**该授权收敛本身就是意图**，此时 MUST 在权限词表中同步落一条共用码，并检查被取代的旧码是否已无任何方法使用（无使用即为死码，MUST 删除而非留存）。
3. **合法跃迁集**：MUST NOT 收敛为单一 `Transition(target_state, payload)` 型方法。那会把「哪些跃迁合法」从契约层退到运行时，调用方失去类型级约束，且风险等级不可分。

**Review 判据（可机械执行）**：在一个服务的方法清单中，若存在 N 个方法**仅在目标状态上不同**、其余入参与副作用同构，则该组 MUST 收敛为 1 个；若存在两个聚合根各自一套**入参与副作用同构**的方法，则该两套 MUST 收敛为归属多态的一套。

> 与 [design-philosophy §3.2 浅模块气味](./design-philosophy.md#32-浅模块气味must-避免) 的关系：本节是深 / 浅模块准则在**跨边界契约面**上的具体化——逐跃迁切分产生的正是「接口规模 ≈ 实现规模」的浅接口。模块内部的深浅判断仍以该文为准，本节只管契约面。

### 7.6 事件与回执（跨域闭环推荐）

事件用于发布「领域事实」；回执用于闭环对齐（触达/语音确认/履约节点等）。

EventEnvelope（最小）：

```json
{
  "event_id": "string",
  "event_type": "namespace.snake_case.v1",
  "occurred_at": "RFC3339",
  "producer": "service_name",
  "tenant_id": "string",
  "subject": { "type": "snake_case", "id": "string" },
  "payload": {},
  "trace": { "request_id": "string" }
}
```

约束：

- tenant_id MUST 存在且不可从 payload 推断。
- event_type MUST 稳定；payload MUST 最小化（下游必需字段）。

ReceiptEnvelope（最小）：

```json
{
  "receipt_id": "string",
  "receipt_type": "namespace.snake_case.v1",
  "occurred_at": "RFC3339",
  "tenant_id": "string",
  "ref": { "event_id": "string", "object_type": "snake_case", "object_id": "string" },
  "result": { "status": "snake_case", "reason": "string" },
  "proof": { "audit_ref": "string" }
}
```

### 7.7 数据库与复制（服务间事实输入优先离线）

- MUST 明确每张表/实体的唯一 SoR（数据所有权）。
- SHOULD 采用离线复制机制（CDC / 逻辑复制 / 事件投影等）形成 Consumer 本地 Read Model（见服务依赖契约）。
- Producer 对外发布表 SHOULD 放入独立 schema 或独立库；Consumer 复制表 SHOULD 只读。
- MUST 接受最终一致，并定义 Max Staleness 与超阈处理策略（拒绝/降级/只读）。

## 8. 服务依赖治理（强制）

以 [service-dependency-contract.md](./service-dependency-contract.md) 为准；本文只固定不可协商项：

- MUST 默认单向：Consumer 依赖 Producer 的事实输出；MUST NOT 反向依赖。
- MUST NOT 跨服务写入对方归属数据（包括「补字段/状态位」）。
- SHOULD 离线依赖优先（复制/事件/投影）；在线强依赖必须有超时边界与降级策略。
- 治理依赖（审计/合规校验）可异步/补偿，但 MUST 可追溯、可复现。

## 9. 多租户、权限与策略契约（强制）

- 所有跨边界请求与事件 MUST 显式携带 tenant_id。
- 所有持久化对象 SHOULD 具备 tenant_id 维度（或能严格映射到 tenant_id），并在查询层强制隔离。
- 权限码 MUST 为 `resource:action`（全小写）；action 词表以命名规范为准。
- 访问控制决策 MUST 基于权限码（permission code），MUST NOT 基于角色码（role code）。角色仅是权限的命名集合，角色→权限映射由数据库管理、随时可变；硬编码角色码会导致映射变更后访问控制不生效、新增角色被遗漏。
- PDP/策略输入字段 MUST 使用 `namespace.snake_case`；禁止在策略层引入未映射字段。

## 10. 审计与存证（强制）

目标：全链路可追溯证据链。

- 关键写操作 MUST 落审计：授权/撤销/紧急访问/关键角色变更/高风险设备变更等。
- 审计记录 MUST 具备：tenant_id、actor、action、object、occurred_at、request_id（或可关联号）。
- 链上存证 MUST 最小化：仅摘要/指纹/必要引用；明细留链下。
- 高频场景 SHOULD 批量摘要（如 Merkle Root）以控成本与延迟。

## 11. 兼容性与演进（跨边界默认兼容模式）

通用规则：

- MUST 先扩展后收缩：新增字段可空/有默认；删字段先停用再删除。
- MUST 为破坏性变更提供迁移路径（双写/双读/灰度/回滚）。
- MUST NOT 静默改变字段语义；必须升版本或引入新字段。
- MUST NOT 通过字段顺序、隐式时序、约定俗成的 magic 值等非显式渠道传播契约语义（避免信息泄漏式破坏；见 [design-philosophy.md §4 信息隐藏与泄漏](./design-philosophy.md#4-信息隐藏与泄漏)）。契约破坏不止于字段编号变化。

复制/DDL（若使用逻辑复制）：

- MUST 通过迁移流程保持结构兼容；Consumer 侧先加字段再 Producer 侧开始写入并发布。
- MUST 监控复制延迟与失败，并在超阈时触发降级策略。

## 12. 安全编码（强制）

- MUST NOT 硬编码凭证：密钥、密码、Token 等敏感信息 MUST 通过安全配置源（环境变量/密钥管理服务）注入；MUST NOT 提交到代码仓库。
- 所有用户输入 MUST 校验：包括但不限于 API 参数、表单数据、文件上传；校验范围涵盖类型、格式、长度、枚举值；MUST 对输出进行编码以防范 XSS。
- 认证相关代码 MUST 有安全测试：覆盖密码/Token 校验、会话管理、权限边界、暴力破解防护等场景。

## 13. 质量门禁（通用）

- 交付前 MUST 至少执行与项目栈匹配的格式化、静态分析、类型检查（如适用）、测试与供应链检查（如适用）。
- MUST 在 CI 中固化并可追溯质量门禁结果。
- MUST NOT 用 AI Agent 自述替代 Verification Oracle 的证据；gate evidence MUST 来自命令输出、测试结果、生成产物一致性、审查记录或 approval 记录。
- docs：MUST 通过 [§1.0](#10-文档内容准入第一原则) 内容准入；SHOULD 保持链接可用、术语一致、无重复与无冲突，变更同步更新引用。
- design：PR 描述 SHOULD 标注是否触发 [design-philosophy.md §12 十二种气味](./design-philosophy.md#12-十二种气味red-flags)（A-L）；连续 ≥3 项气味 MUST 回炉至 [§7 设计两次](./design-philosophy.md#7-设计两次design-it-twice)，不允许仅在实现层修补绕过。

### 13.1 测试分层

项目 SHOULD 采用分层测试架构，具体框架与命令由项目 overlay 固化：

1. **Level 1 — 单元测试**：纯逻辑，无 DB/HTTP，快速反馈，开发时频繁运行。
2. **Level 2 — API 契约测试**：通过真实 RPC / HTTP 请求验证服务是否严格遵守 proto 契约，覆盖正常路径和异常路径。
3. **Level 3 — E2E 测试**：端到端覆盖真实认证链路、权限边界和完整 UI / 客户端交互流程。
4. **Level 4 — UAT 人工验收**：由人工执行，覆盖 Verification Oracle 无法自动判定的主观体感、真实物理链路、上线签字与 Human Approval Gate。

CI 流水线 SHOULD 遵循：契约生成一致性 → 单元测试 → API 契约测试 → E2E。

### 13.2 UAT 执行记录纪律

适用于任何项目的 UAT；项目专属载体（报告路径、缺陷模板、通过项计数）由项目 UAT 文档登记，本节不复述。

- **Trigger**：执行 UAT 验收（含回归 / 季度验收 / 上线前验收）时 MUST 加载本节。
- **Load**：先读本节，再读项目 UAT 文档（runbook / 章节模板 / 缺陷模板）。
- **Apply**：
  1. 只记录失败的用例及问题描述；通过项按章节记计数即可。MUST NOT 现场修复被测代码，MUST NOT 现场分析失败原因。
  2. 失败源于用例本身（过时 / 漂移 / 不正确）时，MUST 先修正用例再重新执行，按修正后结果记录。
  3. 出现阻塞后续用例执行的失败时 MUST 立即终止本轮验收，并记录终止原因与终止位置。
  4. 验收后修复报告所记缺陷并复验时，MUST **就地更新原报告**：缺陷条目补处置与复验结论、签收状态与受阻场景就地刷新；MUST NOT 为复验另立新报告文件——一轮验收自始至终一份报告（报告是该轮验收的单一事实源，拆分即漂移）。
- **Conflict / Stop**：项目缺失 UAT 文档或缺陷模板时停止并报告，MUST NOT 自创记录格式。
- **Output**：报告含失败用例清单、问题描述，以及（如发生）终止原因与终止位置；发生修复复验时含各缺陷的处置与复验结论。
- **MUST NOT**：逐条记录通过用例、现场修复被测代码、现场归因、跳过阻塞继续后续用例、为修复复验另立报告文件。

### 13.3 UAT 与自动化测试的边界（AUTO 证据规则）

UAT 是 Level 4 人工验收层（§13.1），**不是**自动化测试的别称——Level 1-3（单元 / API 契约 / E2E）的产出在 UAT 语境下只是「AUTO 证据」，不是 UAT 判定结论本身。Agent 维护或编写 UAT 文档时 MUST 遵守：

- **不可替代**：自动化测试通过（绿）≠ UAT 已验收 / 已签收。UAT 判定结论只来自人工执行当轮的 `reports/` 签收记录或 Human Approval Gate 留痕。
- **AUTO 的语义**：UAT 文档（覆盖矩阵、章节「自动化证据」块）中标注 `AUTO` / 引用某测试文件，仅声明「该自动化证据文件存在」，**不声明**「本轮已执行」「本轮已通过」。
- **不混同两层产出**：MUST NOT 用自动化测试计数 / 覆盖率 / 套件清单冒充 UAT 覆盖；MUST NOT 把「有测试文件」写成「UAT 已覆盖」。UAT 文档维护自动化测试的映射时，MUST 以「证据指针」形态登记（文件路径 + 用例计数），与「人工验收签收状态」分列。
- **何为 UAT 不可替代的判定**：§13.1 Level 4 定义的四类——主观体感、真实物理链路、上线签字、Human Approval Gate。`expect(x).toBe(y)` 可表达的确定性断言归自动化（Level 1-3），不进 UAT 判定面（具体落地判据由项目固化，如本仓 `docs/designs/test-architecture.md` §6「UAT vs E2E 分工」）。

> 本条是 UAT 文档中「AUTO 证据」概念的唯一真相源；项目 UAT 文档的本地措辞（如本仓 `docs/uat/coverage-matrix.md` 的 AUTO 定义）MUST 与本条一致，MUST NOT 另立口径。

## 14. AI Agent 最小任务输出

任务描述与 PR 描述只保留下列最小字段，以控制 Agent 加载的上下文规模。

**任务描述**（`tasks.md` 或 issue）SHOULD 包含（最小字段）：

- Why/What（目标与非目标）
- 验收标准（Given/When/Then 或 checklist）
- Verification Oracle（每条验收的判定者与 evidence 形态；无机器判定者时标记 Human Approval Gate）
- 契约变更（API/事件/Schema/错误码/权限码/兼容策略）
- 影响边界（仓库/模块/服务；Producer/Consumer）
- 设计权衡（考虑过的替代方案与放弃理由 —— [设计两次](./design-philosophy.md#7-设计两次design-it-twice)的最小落地形式）

**PR 描述**（Ship 阶段统一撰写）MUST 在上述基础上额外包含回滚/灰度（如有）。多个 change 合并为一个 PR 时，PR 描述汇总各 change 信息即可，不要求每个 change 的 `tasks.md` 单独产出 PR 描述。

## 15. 分页

List 风格 RPC MUST 支持分页。本规范定义两种分页模式，API 提供方 MUST 选择其中一种作为主模式，MAY 同时支持两种。

### 15.1 Cursor-based 分页（默认，符合 AIP-158）

适用于大数据集、实时性要求高的场景。

**Request 字段（内联在各业务 proto 的 ListXxxRequest 中）**：

| 字段         | 类型   | 约束 | 说明                                               |
| ------------ | ------ | ---- | -------------------------------------------------- |
| `page_size`  | int32  | MUST | 每页最大条数，默认 20                              |
| `page_token` | string | MUST | 首次请求为空串，后续使用响应中的 `next_page_token` |

**Response 字段（内联在各业务 proto 的 ListXxxResponse 中）**：

| 字段              | 类型   | 约束 | 说明                                              |
| ----------------- | ------ | ---- | ------------------------------------------------- |
| `next_page_token` | string | MUST | 空串表示无更多数据                                |
| `total_size`      | int32  | MAY  | 符合筛选条件的总记录数；省略可避免昂贵 COUNT 查询 |

**约束**：

- `page_token` 对客户端 opaque；服务端 MUST 编码游标位置（推荐以排序键 id 编码）。
- 首次请求 `page_token` MUST 为空串（「」）。
- 服务端查询模式：`WHERE id > decode(page_token) ORDER BY id LIMIT page_size + 1`，若结果 > page_size 则存在下一页，`next_page_token` = 最后一项的编码 id。
- `next_page_token` 为空串表示无更多数据。
- `total_size` 为 optional；服务端 SHOULD 在数据量可控时返回，大数据集下可省略。

### 15.2 Offset-based 分页（备选）

适用于页码型 UI 分页控件需要跳页的场景。

**Request 字段**：

| 字段        | 类型  | 约束 | 说明                  |
| ----------- | ----- | ---- | --------------------- |
| `page`      | int32 | MUST | 页码，1-based，默认 1 |
| `page_size` | int32 | MUST | 每页条数，默认 20     |

**Response 字段**：

| 字段    | 类型  | 约束 | 说明                   |
| ------- | ----- | ---- | ---------------------- |
| `total` | int32 | MUST | 符合筛选条件的总记录数 |

### 15.3 模式选择指南

| 场景                           | 推荐模式              | 理由                           |
| ------------------------------ | --------------------- | ------------------------------ |
| 后端微服务间 List RPC          | Cursor                | 高性能、无 offset 漂移         |
| BFF → 前端（使用分页 UI 控件） | Cursor + `total_size` | 桥接 UI 控件，同时保持标准兼容 |
| 后台管理（数据量小、需跳页）   | Offset                | 简单直接，适配 UI 控件         |

### 15.4 页码型 UI 控件桥接

Cursor 分页与页码型 UI 控件（需要 `当前页 / 总数`）语义不匹配时，调用方 MUST 在客户端维护 token 缓存桥接，MUST NOT 为迁就控件把服务端改成 Offset：

- 维护 `pageTokens` 数组：索引 0 为空串，索引 n = 请求第 n 页所用的 token。
- 翻到第 n 页时取 `pageTokens[n-1]` 发起请求，把响应的 `next_page_token` 写回 `pageTokens[n]`。
- 总数优先用服务端返回的 `total_size`；未返回时按 `当前页 × page_size + (有下一页 ? page_size : 0)` 近似。

具体 UI 库的 props 绑定见项目前端规范（本文档集内的 React 栈落地见 [frontend-conventions §6.3](./frontend-conventions.md#63-cursor-分页与页码控件桥接)）。

### 15.5 全量获取豁免

以下场景的 List 风格 RPC MAY 不提供分页字段，但 MUST 在对应 spec 中显式注明豁免理由：

- 返回数据量为有限集合（如系统菜单树、角色列表、权限码列表），总记录数可预期远小于 `page_size` 默认值
- 返回需要构建树形结构，分页会破坏父子关系完整性
- 调用方需要全量数据做客户端过滤或本地缓存

豁免时 MUST 在 spec 中写明：豁免原因、预期最大数据量、当数据量增长超过阈值时的应对方案。
