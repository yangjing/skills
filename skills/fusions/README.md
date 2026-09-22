# fusions

Fusion Rust 后端框架（`fusions` 及子 crate）的核心库模式与决策规范。

## 简介

[`fusions`](https://github.com/fusion-data/fusions) 是一个**应用无关**的 Rust 框架（v0.3）：`Application` + 依赖注入（`Component` / `Plugin`）、基于 `fusion-sql`（sqlx / `DbxPostgres`，**非 ORM**）的类型化 `ModelManager<C>`、经 `fusion-web` 集成 Axum、经 `fusion-rpc` 集成 ConnectRPC、经 `fusion-security` 提供 JWT、独立 `fusion-mq` 提供 MQ、`fusion-weixin` 编排微信登录 / xpay / 推送、`fusion-storage` 提供对象存储、`hetuflow` 提供 durable workflow。

框架对具体租户、scope、claims、RLS 策略一无所知——这些由**应用 crate** 通过 `AppContext: ModelContext` 实现和配置结构体提供。扩展 fusion crate 时，业务语义须留在应用层。

> **源码仓库**：<https://github.com/fusion-data/fusions>

## 适用场景

在以下 Rust 后端代码或文档工作中使用：

- `fusions`、`fusion-common`、`fusion-core`、`fusion-db`、`fusion-web`、`fusion-rpc`、`fusion-security`、`fusion-ai`、独立 `fusion-mq`、`fusion-sql`（原 `fusionsql`，v0.3 改名）、独立 `fusion-weixin`、`fusion-storage`、`hetuflow`
- 依赖注入（`Application`/`Plugin`/`Component`）
- 类型化 DB 上下文（`ModelManager`/`ModelContext`/`DbxPostgres`/`TypedDbPlugin`）
- Axum 集成（`WebError`/`WebServerBuilder`）、ConnectRPC（`AuthLayer`/`ContextValidationLayer`/`ConnectTransport`）
- JWT/OAuth/ACS3、MQ producer/consumer 插件、AI factory/graph_flow、手写 sqlx 仓储（`DbxPostgres`）、RLS/session-var 事务、trusted-header 认证、东西向客户端 transport
- 从 v0.2 `fusionsql` / sea-query / BMC API 迁移到 v0.3（迁移表见 [fusion-sql](references/fusion-sql.md)）
- 微信登录编排（App / Web / MiniProgram 三凭据面 + 锚定策略）、xpay 虚拟支付、推送回调验签
- 对象存储 `Operator` 工厂、预签名 URL（云 native / fs HMAC）
- Durable workflow：定义校验 / 推进决策 / `WorkflowService` / outbox·timer worker

**不适用于**：前端代码、绕过 `DbxPostgres` 事务封装的无关裸 SQL 工作。

## 安装

```bash
# 安装到当前项目
npx skills add <owner>/my-skills --skill fusions

# 全局安装
npx skills add <owner>/my-skills --skill fusions -g -y
```

## 使用说明

本 skill 面向 AI Agent 自动加载。`SKILL.md` 常驻上下文，包含决策树、Gotchas、核心模板、Feature flags、错误处理——按需再打开具体 reference。

**决策树（读前必看）**：每个部件归入且仅归入一个槽位——

1. **长期进程单例**（无每请求状态）：连接池、调度器、MQ producer、`TypedDbPlugin` 注册的 base `ModelManager` → `#[derive(Component)]`，在 `Plugin::build` 注册。
2. **应用服务**（每请求 DB 工作、需要调用方身份/scope）：`pub fn new(mm) -> Self`，**不 derive Component**，在 handler 内用请求级 `mm` 构造。
3. **公开/豁免端点**（无认证上下文）：应用提供 helper 构建带 "system" `AppContext` 的 base `mm`。

应用 crate（而非 fusions）负责把请求导向 (2) 或 (3)。

## 关键 Gotchas（与默认 Rust/Axum/sqlx 约定不同）

- **不要自建 `AppState`**：用 `Application` 作 Axum state。
- **`DataError` 在 `fusions::error`，不在任何子 crate**：跨 crate `From` 实现集中在 `fusions::error` 并按 feature gate。
- **应用服务不 derive `Component`**：Component 在启动时用 base `ModelManager` 装配，不携带当前调用方上下文。
- **`SET LOCAL` 事务作用域**：若 `ModelContext::db_session_vars()` 返回 vars，则**每次读写都在事务内**，否则 RLS 表静默空结果。读用 `begin_txn_read_only()`、写用 `begin_txn`；闭包式 `mm.transaction(|mm| ...)` 是裸 `BEGIN/COMMIT`（无 `set_config`），RLS 应用必须走在其上叠加 session vars 的应用侧 helper。
- **v0.3 无 BMC / 查询构造器**：DB 访问 = 手写 sqlx 经 `DbxPostgres`（repo 函数持 `&DbxPostgres`）；避免 `dbx.db()` 裸池（绕过事务与 `SET LOCAL`）；审计列不再自动填充，从 `mm.ctx_ref()?` 显式写；客户端 `ORDER BY` 无框架校验，MUST 经应用侧列白名单映射为静态列名。
- **东西向客户端 transport 用工厂**：`build_connect_transport(uri)` 注入内核层 TCP 探测，半开连接 ~30s 自愈；不要手搓裸 `Http2Connection`。

## 参考文档（按需加载）

| 工作于… | Reference |
|---------|-----------|
| `Ctx`/`CtxPayload`、time helpers、`codes` | [fusion-common](references/fusion-common.md) |
| `Application` 生命周期、`Plugin` 顺序、`CoreError` | [fusion-core](references/fusion-core.md) |
| `TypedDbPlugin`、`DbxPostgres` 手动事务 | [fusion-db](references/fusion-db.md) |
| Axum handler、`WebError`、`WebServerBuilder`、`WebAuth`、`RateLimiter` | [fusion-web](references/fusion-web.md) |
| ConnectRPC、`AuthLayer`（JWE / opaque 双模）、`TrustedSubject`、东西向 transport 自愈 | [fusion-rpc](references/fusion-rpc.md) |
| JWT、密码哈希、OAuth2 / Aliyun ACS3、`captcha`、`wechat` 原语 | [fusion-security](references/fusion-security.md) |
| MQ producer/consumer、zombie reaping | [fusion-mq](references/fusion-mq.md) |
| 微信登录编排（三凭据面 / 锚定策略 / session_key 纪律）、xpay 虚拟支付、push 回调验签 | [fusion-weixin](references/fusion-weixin.md) |
| 对象存储 Operator 工厂、预签名 URL（云 native / fs HMAC）、后端 feature 映射 | [fusion-storage](references/fusion-storage.md) |
| Durable workflow：定义校验 / 推进决策 / `WorkflowService` / outbox·timer workers | [hetuflow](references/hetuflow.md) |
| `ModelManager<C>`/`ModelContext`、`DbxPostgres` + sqlx repo 形态、事务、`SqlError`、v0.2 → v0.3 迁移表 | [fusion-sql](references/fusion-sql.md) |
| OpenAI-compatible LLM wire（Chat / Responses 工厂分化）、graph-flow、usage 计量 + 批量落库、STT/TTS/声纹 | [fusion-ai](references/fusion-ai.md) |
| Feature flag 组合、顶层 re-export | [fusions](references/fusions.md) |

## 目录结构

```
fusions/
├── SKILL.md                         # v0.3 破坏性变更 + 模块地图 + 决策树 + Gotchas + 核心模板 + Feature flags + 错误处理
├── references/                      # 13 个子模块详细参考（按需加载）
│   ├── fusions.md
│   ├── fusion-common.md
│   ├── fusion-core.md
│   ├── fusion-db.md
│   ├── fusion-web.md
│   ├── fusion-rpc.md
│   ├── fusion-security.md
│   ├── fusion-mq.md
│   ├── fusion-weixin.md
│   ├── fusion-storage.md
│   ├── hetuflow.md
│   ├── fusion-sql.md
│   └── fusion-ai.md
└── evals/
    └── evals.json
```
