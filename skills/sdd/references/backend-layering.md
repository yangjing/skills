# 后端分层架构规范

> **Status**: active · **Version**: v2（2026-07-26）
> **适用范围**：模块化后端服务的分层组织与强类型边界。类型映射表以 Rust + PostgreSQL 为示例栈，分层与依赖规则本身与语言无关
> **规范语言**：BCP 14（RFC 2119/8174）—— MUST、MUST NOT、SHOULD、SHOULD NOT、MAY
> **本文不重述**：契约类型与统一形状 → [SPECIFICATION §7](./SPECIFICATION.md#7-契约类型与统一形状)；模块内部设计判据 → [design-philosophy](./design-philosophy.md)；跨服务依赖治理 → [service-dependency-contract](./service-dependency-contract.md)

## 0. Agent 执行协议

1. **Trigger**：设计后端模块结构、新增 crate / 包、决定字段类型落层、或 review 命中「handler 里写 SQL」「跨层传 wire string」类问题时，MUST 加载本文。
2. **Load**：只读命中章节（分层职责 §3、类型映射 §3.5、依赖规则 §6）；具体 crate 名、路径、框架 API 以项目 overlay 为准。
3. **Apply**：本文定分层边界与类型纪律；项目的物理布局、装配方式、命名以项目架构文档为准。
4. **Conflict / Stop**：出现模块间双向依赖、或某 package 同时被当共享库依赖又需独立进程演进时，MUST 停止并报告边界冲突（§6）。
5. **Output**：交付说明 MUST 点名新增 / 变更的模块边界、跨层类型转换点与依赖方向。
6. **MUST NOT**：MUST NOT 把项目 crate 清单、包名、迁移史写进本文；MUST NOT 用本文的示例栈类型表覆盖项目实际 DDL。

## 1. 目标

- 以业务能力边界组织代码，而不是以技术类型横向切目录
- 让模块默认封装内部实现，只暴露最小 public API
- 让 `api` 层只负责协议适配，不承载业务编排与领域规则
- 让同一用例可被 `ConnectRPC` 与 `HTTP JSON` 复用，而不复制逻辑

## 2. 模块定义

一个模块表示一个清晰、稳定、可独立演进的业务能力边界。模块通常对应一个 bounded context、一个 feature，或一组强相关的子能力。

模块的约束：

- 一个模块 MUST 只承载一个明确的业务归属
- 模块内部 MAY 继续分层，但对外 MUST 只暴露有限入口
- 外部模块 MUST 只依赖该模块导出的能力，MUST NOT 依赖其内部实现
- 跨模块协作 SHOULD 通过 service、契约客户端或事件完成；MUST NOT 直接操作兄弟模块的内部存储

适合成为独立模块的例子：

- order
- account
- catalog
- inventory

## 3. 分层模型

推荐分层：

```text
api -> application -> domain -> infra
```

各层职责如下。

### 3.1 api

`api` 是协议适配层，负责接住外部请求并转换为应用层可消费的输入。

职责：

- 处理 `ConnectRPC` handler
- 处理 `HTTP JSON` handler
- 做参数解析、鉴权上下文提取、幂等键提取、响应序列化
- 做协议级错误映射、header/metadata 处理、分页壳包装
- 把 Protobuf message / HTTP request DTO 转换为传输无关的 command/query

约束：

- MUST NOT 直接访问数据库
- MUST NOT 直接编排事务
- MUST NOT 重复实现业务校验、菜单裁剪、策略判断、分页规则等
- `rpc` handler 与 `http` handler MUST NOT 互相调用；二者都 MUST 只依赖 `application`

协议优先级：

- `ConnectRPC` MUST 作为默认的一等入口
- `HTTP JSON` 为补充入口；模块只提供一个对外入口时 SHOULD 优先提供 `ConnectRPC`
- 浏览器直调、开放集成、Webhook、健康检查、文件上传下载等场景 MAY 补充 `HTTP JSON`

协议边界：

- ConnectRPC 的错误码、metadata、流式语义 MUST 保留在 `rpc` 适配层
- HTTP status code、header、分页响应壳 MUST 保留在 `http` 适配层
- 协议生成类型 MUST NOT 进入 `domain`
- `application` SHOULD NOT 直接依赖协议生成类型

### 3.2 application

`application` 负责用例编排，是模块的业务入口层。

职责：

- 组织 command/query/use case
- 定义事务边界
- 触发权限检查、调用策略服务
- 编排本模块 domain 与 infra
- 协调其他模块导出的 service 或契约客户端

约束：

- MUST NOT 承载协议细节
- MUST NOT 直接暴露数据库行模型
- MUST NOT 把传输层 DTO 当作领域模型长期传递

**事务边界细则**：

- 事务边界（顶层 BEGIN/COMMIT）MUST 由 `application` 用例或定时/异步任务的顶层执行函数界定；`api` / `domain` / `infra` MUST NOT 自行定义跨多操作的业务原子边界。下层持久化方法只在调用方传入的事务上下文内执行 SQL。
- **异步任务粒度**：「定时/异步任务顶层启用事务」MUST NOT 被理解为「整个 tick 包一个事务」。默认按 **per-item / per-batch** 划分事务并配合**幂等标记**——best-effort 巡检中单条失败不应回滚其它已处理条目；把整轮扫描包成一个大事务会放大锁范围、易超时、一条失败全回滚。仅当多步骤确需原子性（如租户 bootstrap：建租户 + 订阅 + 管理员要么全成要么全不成）才在顶层包一个事务。
- **跨服务一致性**：用例若编排其它模块 / 服务（sibling RPC）的写操作，本地事务只保证**本服务边界内**的一致性；被调服务在自己的进程 / 库内独立提交，无法被本地事务回滚。跨服务最终一致性 MUST 走 outbox / saga，MUST NOT 假设单个数据库事务能覆盖跨进程写。

### 3.3 domain

`domain` 负责业务真相和规则建模。

职责：

- 定义实体、值对象、领域服务、领域策略、领域事件
- 定义 repository trait 或持久化抽象接口
- 承载可复用、可测试的业务规则

约束：

- MUST NOT 依赖 Web 框架、RPC 框架、HTTP 库、SQL 驱动等技术框架
- MUST NOT 依赖具体数据库或外部 SDK

### 3.4 infra

`infra` 负责技术实现与外部资源接入。

职责：

- 实现 SQLx repository
- 对接第三方服务、缓存、消息、外部 SDK
- 做 mapper、client、driver 级实现

约束：

- MUST NOT 反向依赖 `api`
- MUST NOT 把协议层对象带回 `domain`

### 3.5 数据类型分层（强类型原则）

`domain` / `application` / `infra` 三层 MUST 使用与数据库列对齐的强类型；`api` 层负责 wire ↔ native 双向转换。禁止把 wire string 一路传递到 SQL bind。

**类型映射（强制）**：

| PostgreSQL 列 | Rust 类型（domain/application/infra） | proto wire（api 层） |
|---|---|---|
| `UUID` | `uuid::Uuid` / `Option<Uuid>` | `string`（RFC 4122） |
| `BIGINT`（i64 主键 / 外键） | `i64` / `Option<i64>` | `int64`（proto JSON 编码为字符串数字） |
| `TIMESTAMPTZ` | `chrono::DateTime<chrono::Utc>` / `Option<DateTime<Utc>>` | `string`（RFC 3339） |
| `DATE` | `chrono::NaiveDate` / `Option<NaiveDate>` | `string`（`YYYY-MM-DD`） |
| `TIME` | `chrono::NaiveTime` / `Option<NaiveTime>` | `string`（`HH:mm:ss`） |
| `JSONB` | `serde_json::Value`（结构化）或 `String`（透传） | `string`（JSON） |
| `DECIMAL(p,s)` / `NUMERIC(p,s)`（金额/费用） | `rust_decimal::Decimal` / `Option<Decimal>` | `string`（`DecimalString`） |
| `TEXT` / `VARCHAR` | `String` / `Option<String>` | `string` |
| 业务 enum (CHECK 约束) | native 整数（`i16` / `i32`），值为上游契约判别数 | proto enum |

> wire 层日期 / 时间格式的精确定义见 [SPECIFICATION.md](./SPECIFICATION.md) §6，本文不重述。
> 金额/费用字段的命名、precision/scale、币种与前端 `DecimalString` 等具体契约由各项目在自身 field-contracts overlay 文档中定义；本文只规范分层与类型映射。
> 取值受限字段（枚举 / 有界值集）落库形态的硬要求与 `proto enum ↔ domain enum ↔ 数据库` 的映射纪律见下方「枚举字段持久层形态（强制）」；具体宽度（`int2` / `int4`）、三层映射表、jsonb 内枚举字段的处理 MUST 由项目 overlay 定义。

**枚举字段持久层形态（强制）**：

跨边界的枚举语义字段（状态 / 类型 / 分类 / 级别 / 来源 / 阶段等有界值集，无论是否有对应 proto enum）在持久层 MUST 满足：

- **DB 列 MUST 用数值类型**（`SMALLINT` / `INTEGER`）；MUST NOT 用 `VARCHAR` / `TEXT` 字符串列存枚举判别值，MUST NOT 用 PG 原生 `CREATE TYPE ... AS ENUM`（值集演进需 `ALTER TYPE`，与数值列的 `CHECK IN (...)` 相比迁移代价高且不可复用 bitmap 索引）。值对齐上游契约的判别数（proto enum wire number，或仓内枚举的判别整数）。
- **CHECK 约束 MUST 排除判别值为 0 的占位变体**（proto 的 `*_UNSPECIFIED = 0`、或领域 enum 的默认占位）：DB 只存有效业务值，占位值不出现在物理行。语义与字符串方案下 CHECK 不含占位字面量一致。
- **jsonb 内的枚举字段同样 MUST 存数值**（不是字符串 key）：从 jsonb 提取时走数值路径（`as_i64()` → `as i32`），MUST NOT 走 `as_str()` + 字符串 match。涉及该 jsonb 字段的表达式索引相应用 `(col->>'field')::int` 或 `(col->'field')::int`。
- **domain / application / infra 层 MUST 以原生整数承载**（`i16` / `i32`），与 DB 列宽度对齐；MUST NOT 在这三层之间用 `String` 传递枚举值。`api` 层负责 wire（proto enum / JSON string）↔ native 整数的双向转换。
- **proto ↔ DB 映射纪律**：DB 存的数值 == proto wire number，故 `EnumValue::from(row_val as i32)` 可直接还原 proto enum，MUST NOT 手写逐值 match 的 `fn parse_xxx(&str)` 转换层。反向（proto → DB）取 `to_i32() as i16`。
- **无 proto 的内部状态枚举**（基础设施层自有的状态机，如任务队列状态）MUST 在代码层定义 `const` 常量对齐 DB 数值约定，并在 schema CHECK 与代码注释双向标注，MUST NOT 让 DB 与代码各持一套魔数。

**理由**：数值稳定（改 enum 字面名不影响已存数据与索引）、存储占用小（`int2` 2 字节定长 vs `VARCHAR` 变长）、B-tree 索引更紧凑、可应用 bitmap 索引。字符串方案的「可读性」是伪命题——业务用户消费的是有业务语义的映射值（尤其多语言场景），不直接读 DB 字面；程序员的直接读库场景随 AI 辅助开发减少，且数值 + schema 注释的可读性不劣于字符串。

> wire JSON 序列化方向不在本规范约束范围：protobuf JSON Mapping 规范要求 enum 序列化为字符串名（数字仅作输入被接受），这是协议层要求，与持久层存数值正交。

**ID 主键类型（UUID 或 BIGINT，二选一）**：

实体主键 / 外键 MAY 使用 `UUID` 或 `BIGINT`（i64）两种形态之一，由各表按需选择；同一实体的主键与引用它的外键 MUST 同型。两种形态的转换纪律不同：

- **UUID**：列 `UUID` → native `uuid::Uuid` → wire proto `string`（RFC 4122）。wire 为 string，故 **`api` 层 MUST 显式 parse**（`Uuid::parse_str`，见下方 helpers `parse_uuid_field`）。适合需全局唯一、客户端可预生成、避免顺序枚举猜测的场景。
- **BIGINT**：列 `BIGINT` → native `i64` → wire proto `int64`。proto `int64` 生成的服务端类型即为 `i64`，故 **`api` 层无需 parse**，各层全程 `i64` 直传。按 proto JSON 映射规范 `int64` 编码为**字符串数字**，以规避 JS `number` 的 53-bit 精度丢失。适合库内自增、有序、高频 join 的场景；平台级、跨大量表参与高频 join 的主键 **MUST 选 `BIGINT`**。
  - **跨前端消费的 id MUST 加字段选项 `[jstype = JS_STRING]`**：TypeScript 生成器据此产出 `string` 而非 `bigint`（wire 仍是字符串数字），规避 JS `bigint` 的生态摩擦。
  - **例外 · 语义上可「无值」的 id 展示字段 MUST 用 proto `string`**：当字段承载 id 但需要表达「未设置 / 无」（典型：会话上下文中指示「当前租户」的字段，个人上下文下无租户），MUST 用 proto `string`（`""` = 无），MUST NOT 用 `int64 [jstype = JS_STRING]`。根因：TypeScript 生成器对 `jstype = JS_STRING` 的 int64 一律产出**非 optional** `string`（默认 `"0"`，即使标注显式 field presence 也不变），调用方拿不到 absent；前端以 falsy 判「无」时，`"0"` 是 truthy 串会被误判为有值。这是 `jstype`（`FieldOptions.jstype`，JS-only 选项）的设计边界而非缺陷，MUST 在契约设计阶段规避。物理主键 / 外键恒有值，不受此例外影响，仍按上一条用 `BIGINT [jstype]`。

**数据表物理主键 MUST 为 `UUID` 或 `BIGINT` 之一，MUST NOT 用 `TEXT` / `VARCHAR`（string）**；对应 domain `id` 字段也 MUST NOT 落为 Rust `String`；跨模块 / 跨进程仍禁止 `id.to_string()` → 再 parse 的往返转换。

**业务自然键 / 对外编号（非物理主键）**：当业务需要人类可读、可对外引用的稳定标识（如工单号、入院号、订单号）时，MUST 用独立字段承载，MUST NOT 拿它当数据表物理主键——物理主键仍是 `UUID` / `BIGINT`。此字段类型为 `TEXT` / `VARCHAR` + `UNIQUE`（native `String`、wire `string`），属普通业务字段，不受本节「ID 主键类型」约束（见下方「例外」中的业务 slug）。**字段名、编号格式与生成规则 MUST 由项目的命名规范 / 编号体系定义**，本文不钉死统一命名。

**强制点**：

- domain model 字段、`*Params`、`*RepoParams`、`*Filter`、service 方法签名、repo 函数签名 MUST 用上表 native 类型。
- repo 层 `sqlx::FromRow` struct 字段必须与列类型严格对齐（错配会在 PG 解析时崩溃为 `map_db_error`）。
- repo 层 `bind(...)` 必须传 native 值，**禁止** `bind(uuid::Uuid::parse_str(s)?)` / `bind(DateTime::parse_from_rfc3339(s)?)`：这种解析归属 `api` 层。
- 金额 / 费用字段 MUST 使用显式 precision / scale 的 `DECIMAL(p,s)` / `NUMERIC(p,s)`；MUST NOT 用无约束 `NUMERIC`。若 SQL 驱动需额外 feature / 扩展才能直接 bind / decode 十进制类型，项目 MUST 在依赖配置中启用。
- 各 service 内部、跨模块调用**禁止** `id.to_string()` 后再 `parse_uuid(...)` 来回转换。
- 不要为持久化字段补「放宽 parse 失败 → 默认值」的兜底（例：`unwrap_or(Uuid::nil())`、`unwrap_or_else(|_| Utc::now())`），这会掩盖输入污染。

**转换位置（唯一）— `api` 层**：

- 入站：handler 入口处显式 parse wire string → native，失败映射 `invalid_argument`，错误信息含字段名。
- 出站：`From<DomainModel> for ProtoModel` 的转换中显式 `to_string()` / `to_rfc3339()` / `format("%Y-%m-%d")`。

**约定 helpers**：每个模块的 `api` 适配层顶部 MUST 统一定义 wire → native 的 parse 函数。函数 MUST 接收字段名，失败 MUST 映射为 `invalid_argument`，且消息中 MUST 点名字段与期望格式（便于调用方定位）。签名形态：

```rust
fn parse_uuid_field(field: &str, s: &str) -> Result<Uuid, ConnectError>;
fn parse_datetime_field(field: &str, s: &str) -> Result<DateTime<Utc>, ConnectError>;
fn parse_date_field(field: &str, s: &str) -> Result<NaiveDate, ConnectError>;
fn parse_decimal_field(field: &str, s: &str) -> Result<Decimal, ConnectError>;
```

实现示意（其余三个同构，仅 parse 调用与期望格式串不同）：

```rust
fn parse_uuid_field(field: &str, s: &str) -> Result<Uuid, ConnectError> {
  Uuid::parse_str(s)
    .map_err(|_| ConnectError::invalid_argument(format!("invalid {field}: expected UUID")))
}
```

**跨模块边界**：

- 被调方 service 接受 native；调用方负责把自己持有的字段转换为 native 后传入。
- 跨进程 RPC 客户端（返回 String id 的 SDK）调用回写 native 字段时，调用方在边界处一次性 `Uuid::parse_str(&entity.id)?`，失败映射 `server_error`（这是上游契约违反）。
- 上下文已是 native：请求级 ctx 持有的 id 字段已是对应 native 类型（`Uuid` 或 `i64`），service 直接传递，不要 `.to_string()` 或重新 parse。

**反例（禁止）**：

| 反例 | 正解 |
|---|---|
| `pub struct Entity { pub id: String, ... }` | `pub id: Uuid`（UUID 主键）或 `pub id: i64`（BIGINT 主键） |
| `bind(uuid::Uuid::parse_str(&model.owner_id)?)` | `bind(model.owner_id)`（model 字段为 `Uuid`） |
| `bind(chrono::DateTime::parse_from_rfc3339(s).ok().unwrap_or_else(|_| Utc::now()))` | api 层 parse + `bind(dt)` |
| `bind(params.amount)`（`amount: String`） | api 层 parse 为 `Decimal`，service / repo 全程传 `Decimal` |
| service 接收 `id: &str`，内部 `parse_uuid(id, "id")?` | service 接收 `id: Uuid` |
| `Entity { id: row.id.to_string(), ... }` 在 row→model 中转字符串 | row 与 model 同为 `Uuid`，直接 `id: row.id` |
| `let entity_id = json_string_required(payload, "entity_id")?;`（payload 是 wire JSON，service 直接拿 String） | 调用 service 前在 `api` 或 service 入口 parse 一次为 `Uuid` |

**例外**：

- 协议透传字段（如 JSONB payload 整体、源系统外部标识 `idempotency_key`、`source_event_id`、业务 slug）保留 `String`。
- 短生命周期的响应壳/冲突报告等不入库的结构体可保留 `String`，但若字段对应 DB 列类型则仍按上表。

**新增字段检查清单**：

1. 看 DDL 确认列类型 → 查上表得到 Rust 类型。
2. 在 `domain` 层模型用 native 类型声明字段。
3. 在 `infra` 层 repo 的 Row 结构同样字段类型；`bind()` 直接传 native。
4. 在 `api` 层 handler parse wire；From 转换出 string；其余层不出现 parse / to_string。

## 4. 目录模板

复杂模块推荐目录：

```text
src/
  modules/
    order/
      mod.rs
      api/
        connect.rs    # ConnectRPC service trait 实现
        error.rs      # 模块错误枚举 → ConnectError 映射
      application/
        service.rs
      domain/
        model.rs
      infra/
        repo_pg.rs
```

说明：

- `mod.rs` 用于声明模块的 public API，导出路由装配函数
- `api/connect.rs` 实现代码生成的 service trait，负责 proto ↔ domain 转换
- `api/error.rs` 定义模块错误枚举及其 `→ ConnectError` 映射
- `application/service.rs` 作为模块 facade service
- `domain/model.rs` 放领域模型与领域策略
- `infra/repo_pg.rs` 放 SQLx 持久化实现

简化规则：

- 中小模块可以折叠为单文件或双文件结构
- 只要依赖方向不变，不要求机械地「每层必须有文件」
- 当一个模块开始同时出现 handler、领域规则、SQL、外部适配器时，应升级为标准目录结构

## 5. 模块对外接口

每个模块 MUST 显式声明对外暴露面。

SHOULD 对外暴露：

- facade service
- 只读 DTO 或 result 类型
- 路由 / RPC 装配函数
- 模块级错误类型

MUST NOT 直接对外暴露：

- 表结构细节
- SQL 语句
- 数据库行模型
- 仅模块内部使用的 mapper / helper
- 仅为存储实现服务的 repo 细节

## 6. 依赖规则

- `api` MUST 只依赖 `application`
- `application` MAY 依赖 `domain`、`infra`，以及其它模块导出的 service 或契约客户端
- `domain` MUST 只依赖纯领域对象与抽象；MUST NOT 依赖协议框架和数据库驱动
- `infra` MAY 依赖 `domain`；MUST NOT 反向依赖 `api`
- 模块之间 MUST NOT 互相引用内部实现

出现双向依赖时，SHOULD 按以下方式之一破解：

- 抽取共享契约
- 改为单向 service 调用
- 改为事件驱动 + 回执契约

> 跨服务依赖治理（在线 / 离线依赖、SoR ↔ Read Model、双向依赖破解的判定标准）见 [service-dependency-contract.md](./service-dependency-contract.md)。

### 6.1 编译单元间依赖（进程单元 vs 共享库）

workspace 内的编译单元分两类：**进程单元**（独占进程与端口的可执行服务）与**共享库单元**（被多个进程单元平行复用的库）。单元间依赖 MUST 遵守：

- **进程单元 MUST NOT 被另一个进程单元以库形式依赖**。进程之间只允许东西向 RPC 调用。库依赖会把整个业务进程的代码链入对方二进制，且依赖方向违背服务边界。
- **多进程复用的 RPC 面 MUST 抽为共享库单元**，装配模式为「库自带契约生成 + service 实现 + 路由注册函数，各进程平行装配」。
- **跨 bounded context 的 RPC 面 MUST 落在依赖图中同时高于各来源单元的共享库**；MUST NOT 塞进某个进程单元，也 MUST NOT 让下层单元反向读上层的表。
  - 此类共享库 SHOULD NOT 自带契约生成。当它的 IDL import 了来源单元的 IDL 时，本地重新编译会分裂出第二份同名类型，跨单元传递即编译不通过或语义漂移；正确做法是借用来源单元的生成类型。推广为通用纪律：**同一契约 package MUST 只在依赖图最低的消费者处编译一次**，且互相引用的 package MUST 在同一次编译中一并列出。
- **共享库携带实现，不携带策略绑定**：endpoint 权限码是各进程自己的表，随进程保留、不随库迁移（同一 service 在不同宿主 MAY 使用不同权限码，这是有意设计）；配置段 key MUST 与宿主单元解耦，使代码归属迁移不引发部署变更。

## 7. 禁止事项（MUST NOT）

> 本节是结构性硬约束清单，与 [design-philosophy §12 十二种气味](./design-philosophy.md#12-十二种气味red-flags) 互补：本节从模块 / 分层组织角度禁止，该表从模块内部代码质量角度判定。

- MUST NOT 在整个应用范围横向分 `controllers` / `services` / `repositories` / `models`
- MUST NOT 在 handler 中内联 SQL、事务或权限分支
- MUST NOT 在根组装层堆积业务装配细节
- MUST NOT 让一个模块同时承载多个领域真相与多套存储职责
- MUST NOT 把不稳定的业务逻辑提前塞进 `shared` / `common`
- MUST NOT 把所有模块做成隐式全局可见，导致依赖关系不可见
