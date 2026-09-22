---
status: active
version: v1  # 2026-07-30
---

# 栈适配层：Protocol Buffers + ConnectRPC + Buf

> **适配对象**：[`../references/SPECIFICATION.md`](../references/SPECIFICATION.md) §7 · [`../references/service-dependency-contract.md`](../references/service-dependency-contract.md) §4 · [`../references/spec-driven-development.md`](../references/spec-driven-development.md) §2
> **规范语言**：BCP 14（RFC 2119/8174）
> **本层职责**：工具链细则 + **换协议时的映射判据**。契约条款本身在上述分册，本文 MUST NOT 复制

## 0. Agent 执行协议

1. **Trigger**：项目契约技术为 Protobuf + ConnectRPC，且命中 SPECIFICATION §7 / service-dependency-contract §4 / spec-driven-development §2 时，MUST 与该章节一并加载本文。
2. **Load**：只读命中节。
3. **Apply**：契约要求以 `references/` 为准，工具链形态以本文为准。
4. **Conflict / Stop**：项目需要偏离 ConnectRPC 默认协议时，MUST 走 [service-dependency-contract §4.4](../references/service-dependency-contract.md#44-东西向通信协议强制) 的例外申报流程（项目 ADR），MUST NOT 在本文放宽。
5. **Output**：交付说明 MUST 点名依据的适配节号，以及跑过的 `buf lint` / `buf breaking` / 生成产物一致性校验结果。
6. **MUST NOT**：MUST NOT 在本文重复 §7 与 §4 的条款正文；MUST NOT 写项目契约目录路径（属项目 overlay）。

---

## 1. 工具链细则

`references/` 要求「项目 MUST 在自己的 overlay 中声明契约目录、Buf workspace、生成命令与 CI gate」。本栈的通用形态：

| 环节 | 工具 | 硬要求 |
| --- | --- | --- |
| 格式与风格 | `buf lint` | MUST 进 CI；MUST NOT 靠人工 review 替代 |
| 兼容性 | `buf breaking` | MUST 对比已发布基线分支；对外契约进入兼容窗口后 MUST 阻断破坏性变更 |
| 生成 | `buf generate` | 生成配置 MUST 锁定在代码库中；CI MUST 验证签入的生成产物与重新生成的结果一致 |
| 依赖 | Buf workspace / BSR | 跨 package 引用 MUST 在同一 workspace 内解析，MUST NOT 靠相对路径 include 拼凑 |

**同一契约 package MUST 只编译一次**：当共享库的 IDL import 了来源单元的 IDL 时，本地重新编译会分裂出第二份同名类型，跨单元传递即编译不通过或语义漂移。正确做法是借用来源单元的生成类型（判据见 [backend-layering §6.1](../references/backend-layering.md#61-编译单元间依赖进程单元-vs-共享库)）。

**Editions**：消息定义 SHOULD 使用 Protobuf Editions 2023+。目标语言或生成工具尚不支持时，项目 overlay MUST 声明降级语法与兼容策略。

**`jstype = JS_STRING` 的边界**：跨前端消费的 `int64` id MUST 加该选项以规避 JS `bigint` 生态摩擦；但 TypeScript 生成器对它一律产出**非 optional** `string`（默认 `"0"`），故语义上可「无值」的 id 展示字段 MUST 改用 proto `string`。完整判据见 [backend-layering §3.5](../references/backend-layering.md#35-数据类型分层强类型原则)。

## 2. 换协议映射判据

换掉 Protobuf / ConnectRPC 时，`references/` 中**哪些是协议无关的硬要求、哪些是形态**：

### 2.1 SPECIFICATION §7

| 条款 | 性质 | 换协议时 |
| --- | --- | --- |
| API 定义 MUST 单一来源，生成代码是产物且 MUST NOT 手改 | 硬要求 | **不变**（换成 OpenAPI spec / GraphQL SDL 同样成立） |
| 契约 MUST 过 lint 与 breaking 检查并进 CI | 硬要求 | **不变**（替换为对应工具） |
| 契约包 MUST 版本化命名 | 硬要求 | **不变** |
| 错误码 MUST 稳定可枚举、MUST NOT 靠 message 文案判别 | 硬要求 | **不变** |
| 业务语义细分走强类型详情字段 | 硬要求 | **不变**（替换为对应的结构化错误载荷） |
| 审计字段内嵌于实体消息末尾、不复用编号 | 硬要求 | 「内嵌 + 不复用标识」不变；「字段编号」概念随协议变化 |
| 服务方法粒度与合并规则（§7.5） | 硬要求 | **不变**——这是契约面治理，与协议无关 |
| `.proto` 为 source of truth、`buf` 工具链、Connect 错误码表、字段编号规则 | 形态 | **替换** |

### 2.2 service-dependency-contract §4

| 条款 | 性质 | 换协议时 |
| --- | --- | --- |
| 在线调用用于命令型交互；高频读走 Read Model | 硬要求 | **不变** |
| 契约技术 SHOULD NOT 用于统一服务内领域模型 | 硬要求 | **不变** |
| 东西向 transport MUST 自愈（有界探测半开连接、重连有 connect-timeout 上界） | 硬要求 | **不变** |
| MUST 用生成的 typed client，MUST NOT 手拼 body | 硬要求 | **不变** |
| 错误经「领域 → 模块 → 传输」逐层收口 | 硬要求 | **不变** |
| 新增绕过默认协议的通道 MUST 先落 ADR | 硬要求 | **不变** |
| §4.6 边界信任模型（A/B 二选一 + ADR 声明） | 硬要求 | **完全不变**——与协议无关的架构选择 |
| 「ConnectRPC over HTTP/2」「h2c / ALPN h2」「proto `stream` 关键字」「4 MB 单消息上限」 | 形态 | **替换** |

**替换协议时 MUST 逐条回答**：新协议如何满足上表每一条硬要求？任一条无法满足的，MUST 在项目 ADR 中记录该缺口与补偿手段，MUST NOT 默认它不重要。

### 2.3 spec-driven-development §2

「① 定义契约 → ② 准备 fixtures + schema → ③ 生成代码骨架 → ④ 并行实现」的**顺序**是硬要求（契约冻结先于实现）；`buf generate`、`.proto` 文件组织、proto enum 承载状态与权限码是形态，换协议时替换为等价物。

## 3. 常见替换目标的对应关系

| 本栈 | OpenAPI + REST | GraphQL |
| --- | --- | --- |
| `.proto` | OpenAPI 3.x spec | SDL |
| `buf lint` / `buf breaking` | spectral / oasdiff | graphql-inspector |
| `buf generate` | openapi-generator | codegen 插件 |
| Connect 错误码（与 gRPC 一致） | HTTP status + `application/problem+json` 的 `type` 字段 | `errors[].extensions.code` |
| 字段编号 + `reserved` | 字段名 + `deprecated` 标注 | 字段名 + `@deprecated` |
| package 版本号 | URL 路径版本或 media type 版本 | schema 版本策略（通常单版本 + 弃用周期） |

无论替换成哪个，**错误码可枚举**与**破坏性变更可自动检出**这两条 MUST 落实到工具，MUST NOT 退化为人工约定。
