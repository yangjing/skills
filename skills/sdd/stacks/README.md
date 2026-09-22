# 技术栈适配层（stacks）

> **Status**: active · **Version**: v1（2026-07-30）
> **本层职责**：承载「换项目不变、换栈就变」的落地形态。规则本身在 [`../references/`](../references/sdd-overview.md)，项目取值在项目 overlay，本层只管**技术选型带来的差异**

## 0. Agent 执行协议

1. **Trigger**：加载的 `references/` 分册在头部或章节标注了「栈落地形态」，且项目使用对应技术栈时，MUST 一并加载该适配层。
2. **Load**：只读与已命中 references 章节对应的节；MUST NOT 预读全部适配层。
3. **Apply**：职责边界与禁忌以 `references/` 为准，API 与配置的具体形态以本层为准。
4. **Conflict / Stop**：本层与 `references/` 原则冲突时，MUST 以 `references/` 为准并报告本层需要修订；项目所用技术栈**无对应适配层**时，MUST 按 §2 判断哪些条款需要替换，并停止报告需要新建适配层，MUST NOT 把默认基线栈的 API 硬套上去。
5. **Output**：交付说明 MUST 点名依据的适配层与节号。
6. **MUST NOT**：MUST NOT 在本层写项目路径、包名、端口、域名、专属词表（那些属项目 overlay）；MUST NOT 在本层重复 `references/` 已有的条款正文（违反 SSOT，改为链接）。

## 1. 现有适配层

| 适配层 | 覆盖技术栈 | 适配的 references 分册 |
| --- | --- | --- |
| [protobuf-connectrpc.md](./protobuf-connectrpc.md) | Protocol Buffers + ConnectRPC + Buf | SPECIFICATION §7 · service-dependency-contract §4 · spec-driven-development §2 |
| [rust-postgres.md](./rust-postgres.md) | Rust + PostgreSQL + sqlx | backend-layering §3.5 |
| [react-tanstack-antd.md](./react-tanstack-antd.md) | React 19 + TanStack Router/Query + Ant Design 6 + Vite | frontend-conventions（全册）· naming-conventions §10 · i18n-conventions §5 / §8 |
| [react-native-ios.md](./react-native-ios.md) | React Native + Hermes + Metro + Xcode（iOS 壳） | frontend-conventions（全册）· SPECIFICATION §13.1 |
| [harmonyos-arkts.md](./harmonyos-arkts.md) | HarmonyOS + ArkTS + hvigor + napi + DevEco Testing Hypium | frontend-conventions（全册）· SPECIFICATION §13.1 |

前三个是 `references/` 各分册的**默认基线栈**——分册中出现的具体类型、API 与协议名均来自它们。使用其它技术栈的项目 MUST 按 §2 建立自己的适配层。

## 2. 新增一个适配层

**Trigger**：项目使用的语言 / 数据库 / 协议 / 前端框架不在 §1 表内，且已命中带「栈落地形态」标注的 references 章节。

**步骤**：

1. **定位替换点**：在目标 references 分册中找出所有绑定默认基线栈的条款。判据是**换掉技术选型后这条还成立吗**——不成立的即替换点。
2. **区分硬要求与形态**：多数条款是「要求」而非「实现」。例如「东西向 transport MUST 自愈」是协议无关的硬要求，「ConnectRPC over HTTP/2」才是形态。**硬要求 MUST 原样保留**，只替换形态。
3. **复制骨架**：以 [`../templates/stack-adapter.md`](../templates/stack-adapter.md) 为骨架新建 `<stack-slug>.md`，节号与被适配分册的节号对齐。
4. **只写差异**：适配层 MUST NOT 复制 references 的条款正文，只写「本栈下这条落成什么」。
5. **登记**：在本文 §1 表中追加一行；在被适配分册的头部「栈落地形态」处补链接。

**命名**：`<语言或框架>-<数据库或协议>.md`，全小写连字符（如 `go-mysql.md`、`kotlin-graphql.md`）。

**MUST NOT**：MUST NOT 为「同一栈的不同版本」新建适配层（版本差异写在同一文件内的版本小节）；MUST NOT 把项目专属封装写进适配层。

## 3. 判断归属

一条规则该放哪层，问两个问题：

| 问题 | 答案 | 归属 |
| --- | --- | --- |
| 换掉技术栈后还成立吗？ | 成立 | `references/` |
| 换个用同样技术栈的项目还成立吗？ | 成立（但换栈不成立） | `stacks/` |
| 两个都不成立 | — | 项目 overlay |

典型误判：把「所有 id 主键 MUST 是 UUID 或 BIGINT」放进 `stacks/`——它换栈依然成立（是数据建模纪律，不是 Rust 特性），应在 `references/`。反过来，把 `sqlx::FromRow` 的字段对齐要求放进 `references/`——它换掉 sqlx 就不成立，应在 `stacks/`。
