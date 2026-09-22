---
status: active
version: v3  # 2026-07-26
---

# Spec-Driven Development（Sprint / Milestone 流程）

> **适用范围**：把 [SPECIFICATION §4](./SPECIFICATION.md#4-sdd-总流程跨边界变更) 的跨边界变更流程落成 Sprint / Milestone 可执行物料——proto 骨架、代码生成链、目录结构、迭代 checklist
> **规范语言**：BCP 14（RFC 2119/8174）—— MUST、MUST NOT、SHOULD、SHOULD NOT、MAY
> **核心原则**：契约先行、并行开发、联调验证
> **本文不重述**：规范性条款一律以 [SPECIFICATION](./SPECIFICATION.md) 为准；本文只给「做什么、按什么顺序、产出放哪」

## 0. Agent 执行协议

1. **Trigger**：拆分迭代任务、定义契约包、准备代码生成链、执行迭代收尾 checklist 时，MUST 加载本文。
2. **Load**：只读命中步骤，再读该步骤引用的 SPECIFICATION 章节与项目 overlay（契约目录、fixtures 包、生成命令）。
3. **Apply**：本文给物料与顺序；约束条款以 SPECIFICATION 为准，两者不一致时以 SPECIFICATION 为准并回本文修订。
4. **Conflict / Stop**：契约冻结后发现契约缺陷时 MUST 回契约层修订并重新冻结，MUST NOT 在实现层打补丁；无法判定现行真相时停止并报告。
5. **Output**：迭代收尾 MUST 输出 §3 checklist 的逐项结果与 gate 证据。
6. **MUST NOT**：MUST NOT 先写实现再补契约；MUST NOT 把项目路径、包名、命令固化进本文（一律走项目 overlay）。

## 1. 迭代周期

每个 Sprint / Milestone 的时长由团队按实际范围自行决定，包含 6 个步骤。进入步骤 ① 前，需求 SHOULD 先收敛为 issue / spec draft；无法由 [Verification Oracle](./SPECIFICATION.md#2-术语最小集合) 机械判定的产品意图或业务取舍 MUST 先通过 Human Approval Gate。

```
前置：issue → spec draft → Human Approval Gate（仅无 Verification Oracle 的判断）
    ↓
① 定义契约（Proto API Spec + fixture + 状态 + 枚举/常量 + 权限码）
    ↓
② 准备测试 fixtures + schema.sql + seed.sql；前端并行开发走 ConnectRPC stub / Empty
    ↓
③ buf generate 生成代码骨架与类型（前端 + 后端）
    ↓
④ 建立 git worktree 并行工作区，前后端 / BFF / 上下游并行开发
    ↓
⑤ 前后端联调 + E2E 测试（对接真实后端）
    ↓
⑥ pre-push check → commit → push → PR
```

## 2. 步骤详解

### 2.1 定义契约

**负责人**: 前后端共同参与（后端主导接口设计，前端 review 可用性）

**产出位置**: 项目 overlay 声明的契约目录（示例：`<contracts-root>/protos/{domain}/v1/`）

本步骤 MUST 产出的契约内容：

| 契约类型        | 说明                                                                                                                            | 产出位置示例                                                                            |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| API Spec        | 服务定义、请求/响应消息、错误码                                                                                                 | `<contracts-root>/protos/{domain}/v1/{resource}.proto`                                                      |
| Fixture 数据    | 类型安全测试/示例数据，含静态 fixtures 和生成函数；API 测试、E2E、组件测试 / 单元测试可通过项目 fixtures 包 import；服务端测试可使用内联或原生测试数据 | 项目 overlay 声明的 fixtures 包 |
| 前端并行策略 | 页面 / 组件 / `.queries.ts` / hook 只走真实 ConnectRPC client；后端 stub 可返回空响应，前端显示 Empty；不建设业务 mock 服务或本地 mock 数据 | `src/api.ts` + 后端 stub |
| 状态定义        | 实体生命周期状态、流转规则                                                                                                      | Proto enum + 文档描述                                                                   |
| 枚举/常量       | 业务枚举值、错误码、魔法值                                                                                                      | Proto `enum` 定义                                                                       |
| 权限码          | `resource:action` 格式权限码清单                                                                                                | Proto `enum` 或独立文档                                                                 |
| 数据库结构      | 当前迭代完整结构定义                                                                                                            | 项目 overlay 声明的 schema 目录                                                            |
| 种子数据        | 开发/测试/演示初始化数据                                                                                                        | 项目 overlay 声明的 seed 目录                                                              |
| 验证判定        | Acceptance ↔ Verification Oracle ↔ Evidence；无机器判定者时标记 Human Approval Gate                                             | Feature Spec / 任务契约                                                                  |

**API Spec 规范要求**：字段命名 / 枚举值 / 成功响应形状 / Connect 错误码 / 日期时间类型 / 分页结构 / 租户隔离 / 审计字段口径，MUST 遵循 [SPECIFICATION.md](./SPECIFICATION.md) §5（命名）、§6（日期时间）、§7（契约类型与统一形状）、§9（多租户与权限）、§15（分页）。本步骤不重述规范，只确保 `.proto` 落到上述约束。

**Comments-First 约束**:

- Proto `service` / `rpc` / `message` MUST 先以语义注释表达对外承诺（参数语义、返回值、副作用、错误条件），再写字段定义。
- 注释写不清楚 / 写得别扭 → 设计未想清，MUST 回头改 API 而非加注释解释。
- 内部实现注释只承载非显然的 why（hidden constraint / invariant / 历史包袱）；MUST NOT 复述代码。
- 详见 [design-philosophy.md §8 注释先写法](./design-philosophy.md#8-注释先写法comments-first)。

**Fixture 数据要求**:

- Fixtures 是 **lifetime 资产**，放在项目 overlay 声明的 fixtures 包中，跨版本持续迭代，**不按 sprint 快照重建**。
- SHOULD 使用目标语言的类型系统编写 fixture 定义，确保类型与生成代码一致。
- SHOULD 按业务域拆分 fixture 文件，导出该域全部 RPC 的静态 fixtures 和生成函数。
- 覆盖正常场景和边界场景（空列表、长文本、特殊字符）；异常/正常路径比例遵循 [SPECIFICATION.md](./SPECIFICATION.md) §4.2。
- Fixtures 含两类内容：
  - **静态数据**：可直接 JSON 序列化的对象数组，用于 API 测试和前端测试
  - **生成函数**：如 `makeXxxResponse(overrides)`，用于测试构造动态输入（如 ID 自增）
- **API 测试 / 前端测试**：通过项目 fixtures 包直接 import fixture 数据，无需业务运行时 codegen step。
- **服务端测试**：不得依赖应用运行 bundle 中的 fixture fallback；按需在测试内构造原生测试数据。

**前端并行开发数据要求**：约束条款（只走真实 ConnectRPC client、运行时源码禁 import fixtures、禁 `try → fallback fixtures`）见 [SPECIFICATION §4.4](./SPECIFICATION.md#44-开发数据策略)，本节不重述。本步骤的物料动作：后端真实实现未完成时先落 proto + service stub，stub 返回空数组 / 空 message，前端按真实响应自然进入 Empty 态。

**分页约定**：分页字段内联在各业务 `ListXxxRequest/Response` 中，遵循 `SPECIFICATION.md` §15；默认使用 AIP-158 风格 Cursor 分页，**不定义共享 `pagination.proto`**。

**按 Sprint / Milestone 划分 proto 文件**: 每个迭代单元 SHOULD 按业务域拆分独立的 proto 文件，文件名包含版本号（如 `v1-{domain}.proto`）。Proto package MUST 包含版本号（如 `{org}.{product}.v1`）。

### 2.2 从 spec 生成代码骨架

生成顺序（两侧同源于同一份 `.proto`）：

- **前端**：`.proto` → 契约生成命令 → 目标语言类型 + RPC client → 数据获取封装（hooks / query helpers，可选）。测试 fixtures 引用生成类型，供组件测试 / 组件文档 / API 测试消费。
- **后端**：`.proto` → 契约生成命令 → 服务端消息类型 + Service interface / trait + client stub → **手写** schema + seed + 重建脚本 → **手写** handler 与业务逻辑。

具体插件、输出目录、语言目标、生成命令与生成配置文件 MUST 由项目 overlay 固化——写进本通用规范的示例配置必然与项目实际漂移。生成产物 MUST NOT 手改（[SPECIFICATION §7.1](./SPECIFICATION.md#71-api-契约定义语言)）。

### 2.3 并行开发（前后端 / BFF / 上下游）

并行开发的规范约束——契约先冻结再拆任务、`git worktree` 隔离工作区、前端只走真实 ConnectRPC client、stub 空响应自然 Empty——见 [SPECIFICATION.md](./SPECIFICATION.md) §4.3（并行开发约束）与 §4.4（开发数据策略）。本节只给前端 / 后端实现的组件级落地。

**较大计划的标准拆分模板**：跨全栈的较大 Milestone SHOULD 拆为 4 份子计划，串并结合执行——**契约计划**（冻结宣告 = 并行启动信号；概念模型过设计两次评审、外部输入先留痕）→ **后端计划**（领域实现 + API 集成测试同批交付）∥ **前端计划**（UI + 组件测试 + E2E **编写不执行**）→ **集成计划**（E2E 执行权 + smoke 实跑 + UAT + 范围审计，持最终验收判定权）。要点：

- **冻结质量决定并行收益**：冻结前完成概念模型评审与外部输入留痕，并行期的契约返工趋零。冻结后仍需变更契约时 MUST 单点登记、双侧同步，MUST NOT 在实现层绕过。
- **E2E 编写与执行分离**：前端计划交付「可枚举、可编译」的 E2E（用测试框架的用例枚举命令验证其可执行性），执行权归集成计划——既避免前端线阻塞在后端可用性上，又不给「测试后补」留口子。
- **集成计划 MUST 例行核对弱类型接缝**：强类型契约面（proto / SQL / 生成物）在此模式下缺陷率趋零，残余缺陷集中在**弱类型接缝**——前端 i18n key 与后端目录码的漂移、会话字段的 UI 消费语义歧义、编排脚本的登记遗漏、声明式配置数值与外部商定值的偏差。集成计划 MUST 把这四类接缝列入核对清单，MUST NOT 只凭测试全绿就合拢。

#### 前端

**组件架构**: 页面组件经数据获取 hook 拿 `{ data, isLoading, error }` 并传给展示组件；展示组件纯 props 驱动、不依赖 API，因而可独立测试与组件文档渲染。

**单元测试**:

- 单元测试 MAY 用测试框架的模块 mock 能力替换 ConnectRPC client，并用测试 fixtures 构造输入；业务代码 MUST NOT import fixtures
- 覆盖正常渲染、loading 状态、空状态、错误状态
- 异常路径数量 MUST 至少为正常路径数量的 1.5 倍（[SPECIFICATION §4.2](./SPECIFICATION.md#42-bdd-场景原则)）

**组件文档**（如 Storybook）:

- 每个展示组件编写 Story
- 使用 fixture 数据作为 args
- 覆盖 Default / Empty / Loading / Error 变体

#### 后端

- Handler + 业务逻辑单元测试
- 数据库集成测试（`schema.sql` + `seed.sql` + CRUD 验证）
- 权限边界测试（403 场景）

#### 数据库重建

- 开发阶段 SHOULD 通过 Docker 一键重建数据库。
- 开发阶段 MAY 不维护 migration 链，但 MUST 保持 `schema.sql` 与 `seed.sql` 可重复执行。
- Sprint / Milestone 结束前 MUST 至少验证一次从空库重建到 E2E 可运行。

### 2.4 前后端联调 + E2E 测试

**异常场景前置约束**:

- 设计异常路径前 MUST 先问：能否通过重设计语义消除该路径（[design-philosophy.md §6 把错误从语义里消除](./design-philosophy.md#6-把错误从语义里消除define-errors-out-of-existence)）。
- 典型可消除场景：删除幂等（已不在 ≡ 刚被删，不抛 NotFound）、查询返回 `Option`/空集合而非 NotFound、权限差异化收敛到 `Obligation.mask_fields` 而非拆 `:list` / `:get` 权限码。
- 不能消除的异常路径再纳入下方 BDD 场景。

**E2E 测试覆盖**：最少场景集（成功、权限拒绝、参数校验失败、依赖降级/超时、回滚/补偿）见 [SPECIFICATION.md](./SPECIFICATION.md) §4.2（BDD 场景原则）；越权返回 `permission_denied`、校验失败返回 `invalid_argument`、认证失败返回 `unauthenticated`，错误码完整口径见 [§7.2](./SPECIFICATION.md#72-connect-协议南北向--东西向默认)。

**联调流程**:

1. 启动后端服务（数据库 + 所有领域服务）
2. 启动前端 dev server，配置 API 地址指向真实后端
3. 运行 E2E 测试
4. 修复联调发现的不一致

说明：

- 前端业务运行时不使用 local mock 数据；后端 stub 空响应即为并行开发时的真实响应。
- Sprint / Milestone 末的联调与 E2E MUST 对接真实后端与真实 API。

### 2.5 提交与 PR

**每个任务完成后及时 commit**，不要积攒到 Sprint / Milestone 结尾。

PR 描述的最小字段集（Why/What、验收标准、契约变更、影响边界、设计权衡、回滚/灰度）以 [SPECIFICATION.md](./SPECIFICATION.md) §14 为准；一个 PR 合并多个变更单元时，按 §14 在 PR 级别汇总各变更要件。

**Pre-push check**：交付前 MUST 跑通项目质量门禁（格式化、lint、类型检查、构建、测试）；通用门禁要求见 [SPECIFICATION.md](./SPECIFICATION.md) §13。

### 2.6 完成计划回流

迭代交付完成后，执行计划只保留审计价值；仍然有效的规则 MUST 回流到长期规格，计划本身降级为非权威材料。

回流的完整规则——执行协议（Trigger / Load / Assess / Apply / Conflict / Output / MUST NOT）、归档清理纪律、BDD 场景——见 [SPECIFICATION §4.6](./SPECIFICATION.md#46-执行计划归档回流)（**唯一真实源**），本节不重述。

**在迭代中的位置**：功能合入主线（§2.5）之后执行；回流未完成或未记录「无需回流」判定时，MUST NOT 关闭该迭代。

## 3. 迭代 Checklist

每个 Sprint / Milestone 结束时 MUST 验证：

```
契约
□ Proto API 定义已完成，覆盖本次迭代全部接口
□ fixture 数据已编写（类型安全定义，覆盖正常 + 边界场景）
□ 前端业务代码未 import fixtures，未维护 local mock 数据，stub 空响应可显示 Empty
□ 状态定义与流转规则已明确
□ 枚举/常量已定义
□ 权限码已列出（resource:action 格式）
□ Proto 错误码符合 SPECIFICATION §7.2（Connect 错误码，可枚举）
□ Proto 分页结构统一
□ Proto 日期时间字段遵循 SPECIFICATION §6 与项目 overlay 的 wire 类型约定
□ 每条关键验收已映射 Verification Oracle；无机器判定者的验收已标记 Human Approval Gate
□ 契约 lint 通过（执行方式由项目 overlay 声明，通常包含 `buf lint`）
□ 前后端对 Proto 字段无歧义
□ 每个 service 已评估接口/实现比，无浅模块气味（[design-philosophy §3](./design-philosophy.md#3-模块深度深-vs-浅)）
□ 异常场景已先尝试"消除"而非"处理"（[design-philosophy §6](./design-philosophy.md#6-把错误从语义里消除define-errors-out-of-existence)）

代码生成
□ 契约生成产物已生成（目标语言与插件由项目 overlay 声明）
□ 前端 fixture 数据已编写（或已输出目标测试框架可消费的格式）
□ 前端生成 client 和数据获取 hooks / query helpers 已编写（如适用）

前端
□ 组件级单元测试通过
□ 组件文档（Storybook）故事已编写
□ 构建、lint、类型检查通过

后端
□ handler + 业务逻辑单元测试通过
□ `schema.sql` + `seed.sql` 就绪并可重建数据库
□ 构建与测试通过

联调
□ 前后端联调通过
□ E2E 测试通过（覆盖正常 + 异常路径）

提交
□ 每个任务完成后已 commit
□ PR 已发起，描述包含完整契约信息
```

## 4. 资产落点

各迭代产出的资产分四类，落点由项目 overlay 声明具体路径；本节只固定**归属纪律**：

| 资产 | 归属纪律 |
| ---- | -------- |
| `.proto` 契约 | 按 `{domain}/v1/` 组织，package 含版本号；契约目录是 API 唯一真相源 |
| 契约生成产物 | 与手写代码分目录隔离，MUST NOT 手改 |
| 测试 fixtures | **lifetime 资产**，独立包，跨版本持续迭代；MUST NOT 进入业务运行 bundle |
| SQL schema + seeds | **lifetime 资产**，`schema.sql` 恒为当前主线的全量最新结构；seed 按用途（base / e2e）分文件 |

后端模块内部的分层目录形态见 [backend-layering §4](./backend-layering.md#4-目录模板)，前端 app 与包的组织见项目前端架构文档；本文不给第二份目录树。
