# SDD 分册总览（Spec-Driven Development）

> **Status**: active · **Version**: v3（2026-07-30）
> **定位**：通用的基于规格的开发规范集。**业务与项目无关**——不绑定具体项目、仓库路径、服务名、crate / 包名、命令脚本或组织命名
> **规范语言**：全集统一使用 BCP 14（RFC 2119/8174）—— MUST、MUST NOT、SHOULD、SHOULD NOT、MAY
> **本文职责**：分册总览 + overlay 边界（§2）+ 规范自审方法（§3）。规范条款一律在各分册，本文不复述
> **加载入口**：触发路由与执行协议在 [`../SKILL.md`](../SKILL.md)，本文不重复该表

## 0. Agent 加载协议

skill 主入口 [`../SKILL.md`](../SKILL.md) 承担 Trigger 路由与执行协议。加载任一分册后 MUST 追加遵循：

1. **Load**：只读命中章节；跨领域任务 MAY 加载多册。MUST NOT 预读全集。
2. **Apply**：通用规则以本文档集为准；取值与落点以项目 overlay 为准（§2）；技术栈落地形态以 [`../stacks/`](../stacks/README.md) 对应适配层为准。各分册的 §0 给出该册自己的执行协议，加载后 MUST 一并遵循。
3. **Conflict / Stop**：通用规则与项目 overlay 冲突时，按 §2 冲突表判断归属；无法判断时 MUST 停止并报告，MUST NOT 自行取舍。
4. **Output**：交付说明 MUST 点名依据的分册与章节号。
5. **MUST NOT**：MUST NOT 把项目特例写回本目录（§2 禁写清单）；MUST NOT 在分册之间重复定义同一规则（§3.4）。

## 1. 分册与默认基线栈

触发场景表见 [`../SKILL.md`](../SKILL.md)。本表只登记各分册的**默认基线栈**——即该册条款所假定的技术选型，以及换栈时的替换指引落点。

| 分册 | 职责 | 默认基线栈 | 换栈时 |
| --- | --- | --- | --- |
| [SPECIFICATION.md](./SPECIFICATION.md) | 总纲：文档内容准入（§1.0）、契约先行、术语、兼容性、安全、质量门禁、分页 | §7 假定 Protobuf + ConnectRPC | [protobuf-connectrpc](../stacks/protobuf-connectrpc.md) |
| [spec-driven-development.md](./spec-driven-development.md) | 迭代执行物料：契约定义、代码生成、并行开发、联调、checklist | §2 假定 proto codegen 链 | [protobuf-connectrpc](../stacks/protobuf-connectrpc.md) |
| [design-philosophy.md](./design-philosophy.md) | 模块内部设计判据：复杂度、深模块、信息隐藏、设计两次、注释准入、代码气味 | 无 | — |
| [naming-conventions.md](./naming-conventions.md) | 命名词表与清单：三层分工、casing、权限码、字段映射、禁用词 | §10 假定文件路由体系 | [react-tanstack-antd](../stacks/react-tanstack-antd.md) |
| [service-dependency-contract.md](./service-dependency-contract.md) | 服务依赖治理：SoR ↔ Read Model、在线 / 离线依赖、通信协议与例外 | §3 假定 PostgreSQL 逻辑复制；§4 假定 ConnectRPC | [protobuf-connectrpc](../stacks/protobuf-connectrpc.md) |
| [backend-layering.md](./backend-layering.md) | 后端分层：api / application / domain / infra、强类型边界、编译单元依赖 | §3.5 类型表假定 Rust + PostgreSQL | [rust-postgres](../stacks/rust-postgres.md) |
| [frontend-conventions.md](./frontend-conventions.md) | SPA 前端工程原则：route 职责、远程数据分层、fixtures 禁令、金额 / 日期渲染 | 栈无关（具体 API 已下沉） | [react-tanstack-antd](../stacks/react-tanstack-antd.md) |
| [i18n-conventions.md](./i18n-conventions.md) | i18n 工程规范：语言状态、命名空间、内容分类、fallback | §5 / §8 假定 react-i18next + antd + dayjs | [react-tanstack-antd](../stacks/react-tanstack-antd.md) |
| 本文 §3 | 规范自审方法：第一性原理、Agent-facing 规则格式、审查清单 | 无 | — |

## 2. 项目 Overlay 边界

SDD 文档集只记录可跨项目复用的规则。以下内容 MUST 放在具体项目的设计文档或 overlay 中，不能写进本目录：

- 真实仓库路径、包名、crate 名、app 名、bin 名、端口、域名。
- 具体命令封装，例如 `make` target、部署脚本、数据库重置脚本。
- 项目专属权限 action、模块订阅、菜单映射、SaaS 分层、URL 历史迁移。
- 项目选择的代码生成插件、客户端集中管理类名、框架封装、测试 harness。
- 当前发布阶段下的兼容性放宽、迁移策略和运维流程。

引用方向：

| 来源 | 允许引用 | MUST NOT |
| --- | --- | --- |
| `references/` 通用规范 | 本目录其它分册、`stacks/` 适配层、外部标准 URL | 项目文档、项目根 Agent 规则文件、执行计划、仓库路径、项目命令 |
| `stacks/` 技术栈适配层 | `references/` 分册、该栈的官方文档 URL | 项目路径、项目包名、项目专属词表 |
| 项目 overlay / design docs | `references/` + `stacks/` + 项目真相源 | 把项目特例写回本 skill |

需表达项目级内容时，MUST 用业务无关的占位措辞（如「项目 overlay」），MUST NOT 写具体文件名。

三层的分工判据是**变化源**，不是内容主题：

| 层 | 收什么 | 变化源 |
| --- | --- | --- |
| `references/` | 换栈、换项目都不变的规则 | 方法论演进 |
| `stacks/` | 换项目不变、换栈就变的落地形态（类型映射、框架 API、生成链） | 技术选型 |
| 项目 overlay | 换栈可能不变、换项目一定变的取值（路径、包名、词表、命令） | 项目决策 |

判断归属时问：**这条规则在另一个用同样技术栈的项目里还成立吗？**成立 → `stacks/`；不成立 → 项目 overlay。**换掉技术栈还成立吗？**成立 → `references/`。

通用规则与项目 overlay 冲突时，MUST 先判断冲突来源，再按下表处理：

| 冲突类型 | 处理 |
| --- | --- |
| 通用规则过窄，不能覆盖合理项目差异 | 更新通用 SDD，保留抽象约束 |
| 项目为了当前实现绕过通用规则 | 回到设计评审，优先修项目实现或记录临时例外 |
| 项目存在合法特殊约束 | 放入项目 overlay，并说明触发条件、风险与退出条件 |

### 2.1 项目 overlay 文件命名

项目 overlay 是扩展或覆盖某份 SDD 通用规范的项目文档（承载项目专属命令、路径、词表、迁移策略等 §2 禁止写入本 skill 的内容）。为让「通用规范 ↔ 项目 overlay」配对可被人与 Agent 一眼识别，overlay 文件 MUST 按下列规则命名：

| 项 | 规则 | 示例 |
| --- | --- | --- |
| 同名覆盖 | overlay 与被覆盖的 SDD 分册同名，并在扩展名前插入 `.overlay`：`<file-name>.overlay.md` | `naming-conventions.md` → `naming-conventions.overlay.md`；`i18n-conventions.md` → `i18n-conventions.overlay.md` |
| 不同名 / 无对应通用文档 | 不加 `.overlay`；用项目命名约定命名（如业务前缀） | `backend-architecture.md`（无对应 SDD 分册，不写 `*.overlay.md`） |
| 位置 | overlay 放在项目侧文档目录，MUST NOT 放进本 skill 的 `references/` 或 `stacks/` | 项目 `<designs-root>/i18n-conventions.overlay.md` |

- **Trigger**：新增 / 重命名一份扩展或覆盖某 SDD 分册的项目文档时。
- **Apply**：先查 `references/` 是否存在同义通用分册；存在 → 命名为 `<对应文件名>.overlay.md`；不存在 → 用项目命名约定，不加 `.overlay`。
- **MUST NOT**：MUST NOT 把 `.overlay.md` 文件放进本 skill；MUST NOT 对无对应通用文档的项目文件加 `.overlay`；MUST NOT 用 `.overlay.md` 表达「草稿 / 废弃」语义（那是 `status:` frontmatter 的职责）。
- **Output**：项目侧索引（设计文档索引、仓库根导航等）MUST 用 `.overlay.md` 真实文件名登记 overlay 文件。

## 3. 第一性原理审查方法

第一性原理在 SDD 中作为审查方法使用，不替代 SDD 流程。审查目标是判断某条规范是否真正降低跨边界交付复杂度，而不是增加文档负担。

### 3.1 战略三步法

| 步骤 | SDD 审查问题 | 产出 |
| --- | --- | --- |
| 解构 | 这条规则要保护的基本事实是什么？例如 SoR 唯一、契约稳定、真实集成、安全可审计 | 基本事实列表 |
| 重构 | 是否有更少、更稳定的规则表达同一事实？是否存在重复定义、项目绑定或不可验证条款 | 收敛后的规则或删除建议 |
| 执行 | 能否用最小闭环验证？例如一个 Feature Spec、一个 proto、一个 fixture、一次 API 契约测试 | 可执行检查项 |

### 3.2 工程五步法

1. **基本事实**：先确认 Contract Surface、Producer/Consumer、SoR、合规与安全边界。
2. **删除**：删掉重复定义、项目路径、实现细节、不可检查的口号。
3. **简化优化**：把规则改成可机读字段、表格、checklist、命令占位或 PR gate。
4. **标准化**：沉淀为 Feature Spec 模板、契约包清单、设计两次记录、测试分层清单。
5. **自动化**：最后再引入 lint、link check、契约生成一致性、fixture import 禁止规则、CI gate。

### 3.3 Agent-facing 规则检查

面向 AI Agent / LLM 自动执行、审核或加载的规则，MUST 写成执行协议，而不是解释性段落：

| 段 | 必须回答的问题 |
| --- | --- |
| Trigger | 什么时候必须加载 / 执行这条规则 |
| Lookup / Load | 先检索或读取哪些真相源 |
| Apply | 命中后按什么顺序执行 |
| Conflict / Stop | 冲突、缺证据或缺决策时如何停止 |
| Output | 必须报告哪些证据、文件、gate 或风险 |
| MUST NOT | 哪些捷径或扩权行为被禁止 |

产品背景、ADR 背景、用户手册可保留叙述式写法；文档索引、自动触发规则、review gate、迁移 / 同步 / 治理 workflow MUST 使用本格式。

### 3.4 审查清单

对 SDD 规则或 Feature Spec 做 review 时，逐项检查：

- 是否通过 [SPECIFICATION §1.0](./SPECIFICATION.md#10-文档内容准入第一原则) 内容准入（该节自带准入清单、豁免与逐段自检问题）——**这是第一项，不过即删，无需再看后续**。
- 这条规则是否指向一个基本事实，而不是偏好或历史习惯。
- 是否只有一个真实源；其它文档是否只链接，不重复定义。
- 是否能被执行者在 Sprint / Milestone 内验证。
- 是否能被工具或 CI 部分自动化。
- 是否把项目特定路径、命令或实现类名放进了通用 SDD。
- 是否先完成「做不做 / 做什么」的判断，再讨论「怎么做」的优化与自动化。
- 面向 Agent / LLM 的规则是否具备 Trigger / Lookup 或 Load / Apply / Conflict 或 Stop / Output / MUST NOT。
