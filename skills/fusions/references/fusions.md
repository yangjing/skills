# fusions

聚合包：统一入口、Feature Flags 组合。

## Cargo.toml 配置

```toml
[dependencies]
fusions = { version = "0.3", features = ["full"] }

# 或按需选择
fusions = { version = "0.3", features = ["web", "db", "security"] }

# 微服务（ConnectRPC）
fusions = { version = "0.3", features = ["microservice"] }

# 含 OAuth2
fusions = { version = "0.3", features = ["api", "oauth"] }
```

## Feature Flags

### 功能模块

| Feature     | 描述                       | 依赖                                   |
| ----------- | -------------------------- | -------------------------------------- |
| `web`       | Axum Web 框架              | fusion-web, axum, tower-http           |
| `db`        | PostgreSQL + typed ModelManager | fusion-db, fusion-sql, sqlx/postgres |
| `db-sqlite` | SQLite 支持                | fusion-sql/with-sqlite, sqlx/sqlite    |
| `security`  | JWT 认证                   | fusion-security/with-jwt               |
| `oauth`     | JWT + OAuth2               | security + fusion-security/with-oauth  |
| `ai`        | LLM providers + graph_flow | fusion-ai                              |
| `rpc`       | ConnectRPC                 | fusion-rpc, connectrpc                 |
| `ulid`      | ULID 支持                  | ulid, utoipa/ulid                      |

### 可选功能

| Feature    | 描述            |
| ---------- | --------------- |
| `openapi`  | utoipa API 文档 |
| `logforth` | 日志框架        |
| `tracing`  | 分布式追踪      |

### 便捷组合

| Feature        | 包含                            |
| -------------- | ------------------------------- |
| `full`         | web + db + security + ai + rpc  |
| `api`          | web + db + security             |
| `web-server`   | web + db                        |
| `microservice` | web + db + security + rpc       |

### 默认 Features

```toml
default = ["common-default"]
common-default = ["fusion-common/with-uuid"]
```

## Re-export 结构

```rust
// 核心（始终可用）
pub use fusion_common as common;
pub use fusion_core as core;
pub use fusion_core_macros as macros;

// 业务错误模型（定义于本 crate 的 error 子模块）
pub mod error;
pub use error::{DataError, DataResult, Result};
pub use fusion_common::codes;

// 条件导出
#[cfg(feature = "ai")]
pub use fusion_ai as ai;

#[cfg(feature = "db")]
pub use fusion_db as db;

#[cfg(feature = "rpc")]
pub use fusion_rpc as rpc;

#[cfg(feature = "security")]
pub use fusion_security as security;

#[cfg(feature = "web")]
pub use fusion_web as web;

#[cfg(feature = "db")]
pub use fusion_sql as sql;

#[cfg(feature = "web")]
pub mod web_utils;
```

`fusion-mq` is not re-exported by `fusions`; import it as `fusion_mq::*`.

## Error 模型

`DataError` 定义在 `fusions::error`，是 fusion 生态唯一的"业务错误模型"。各 fusion-xxx 子库
仅暴露自有的窄错误类型（`CoreError` / `SecurityError` / `WebError` / `SqlError` / `DbxError` /
`AiError`），跨库 `From<X> for DataError` 实现集中在 `fusions::error`。

```rust
use fusions::DataError;
use fusions::Result;        // = Result<T, DataError>
use fusions::codes;          // 错误码常量

DataError::bad_request("Invalid input")
DataError::biz_error("quota.exceeded", "Quota exceeded", Some(json!({"limit": 100})))
DataError::retry_limit("Too many attempts", 5)
```

| 错误源 | feature gate |
| ------ | ------------ |
| `fusion_common::Error` / `CtxError` | always-on |
| `fusion_core::CoreError` / `ComponentError` / `ConfigureError` / `security::Error` | always-on |
| `std::io::Error` / `SystemTimeError` / `AddrParseError` / `serde_json::Error` / `chrono::ParseError` / `uuid::Error` | always-on |
| `tokio::sync::*` / `tokio::task::JoinError` / `mea::mpsc::SendError` / `config::ConfigError` | always-on |
| `connectrpc::ConnectError` 双向 | `rpc` |
| `fusion_sql::SqlError` / `DbxError` / `sqlx::Error` | `db` |
| `fusion_web::WebError` 双向 | `web` |
| `fusion_security::SecurityError` | `security` |
| `fusion_ai::AiError` | `ai` |

映射语义要点（新增转换时对齐）：

- `Unimplemented` ↔ `codes::NOT_IMPLEMENTED`（501，永久失败）双向保留；MUST NOT
  映射成可重试的 503（`SERVICE_UNAVAILABLE`）。
- `SqlError::CtxMissing`（未 `with_ctx` 的装配缺陷）→ 500，不是 401。
- `AiError` 分级：上游 HTTP / Provider 瞬态 → 503；请求构造 / 解析缺陷 → 500。
- 所有 `From` 实现 MUST 用 `with_source` / `internal(.., source)` 保留错误链。

## 快速启动模板

### Web API 服务

```rust
// Cargo.toml: fusions = { version = "0.3", features = ["api"] }

use fusions::{
    core::{Application, application::ApplicationBuilder, plugin::Plugin, async_trait},
    db::TypedDbPlugin,
    web::{Router, WebServerBuilder, WebError, WebResult},
};
use axum::routing::get;
use crate::{AppContext, AppModelManager}; // AppContext: fusions::sql::ModelContext

pub struct ApiPlugin;

#[async_trait]
impl Plugin for ApiPlugin {
    fn dependencies(&self) -> Vec<&str> {
        vec![std::any::type_name::<TypedDbPlugin<AppContext>>()]
    }

    async fn build(&self, app: &mut ApplicationBuilder) {
        let _mm: AppModelManager = app.component();
        let router = Router::new()
            .route("/api/users", get(list_users))
            .route("/api/users/{id}", get(get_user))   // axum 0.8：{id}
            .with_state(app.clone());
        app.add_component(router);
    }
}

#[tokio::main]
async fn main() -> fusions::Result<()> {
    // fusions::Result = Result<(), DataError>。
    // Application::run() 返回 fusion_core::Result = Result<_, CoreError>，
    // 通过 fusions::error 中 `From<CoreError> for DataError` 自动收口。
    let app = Application::builder()
        .add_plugin(TypedDbPlugin::new(AppContext::system))
        .add_plugin(ApiPlugin)
        .run()
        .await?;

    let router: Router = app.component();
    WebServerBuilder::new(router)
        .with_shutdown(app.shutdown_recv().await.expect("shutdown pair taken"))
        .serve()    // 阻塞跑服务循环直到关机；旧名 build() 已 deprecated
        .await?;

    Application::await_shutdown().await;
    Ok(())
}
```

### 微服务（ConnectRPC）

```rust
// Cargo.toml: fusions = { version = "0.3", features = ["microservice"] }

use fusions::{
    core::Application,
    db::TypedDbPlugin,
    rpc::RpcPlugin,
};
use crate::AppContext; // AppContext: fusions::sql::ModelContext

#[tokio::main]
async fn main() -> fusions::Result<()> {
    let app = Application::builder()
        .add_plugin(TypedDbPlugin::new(AppContext::system))
        .add_plugin(RpcPlugin)
        .add_plugin(MyServicePlugin)
        .run()
        .await?;

    Application::await_shutdown().await;
    Ok(())
}
```

### AI 服务

```rust
// Cargo.toml: fusions = { version = "0.3", features = ["ai", "web"] }

use fusions::{
    core::Application,
    ai::{ClientFactory, AgentConfig, graph_flow::*},
    web::{Router, WebServerBuilder},
};
```

## 常用导入汇总

```rust
// 业务错误模型 + Result（顶层）
use fusions::{DataError, Result, codes};

// 核心
use fusions::core::{Application, CoreError};
use fusions::common::ctx::{Ctx, CtxPayload};
use fusions::common::time::{now_offset, OffsetDateTime};

// Web
use fusions::web::{Router, WebError, WebResult, WebServerBuilder, ok_json};
use axum::{Json, Path, routing::{get, post}};

// 数据库（v0.3：无宏、无 BMC、无 Page —— SQL 走 sqlx + DbxPostgres）
use fusions::db::{TypedDbPlugin, DbPlugin};
use fusions::sql::{DbConfig, ModelContext, ModelManager, SqlError};
use fusions::sql::store::{Dbx, DbxPostgres};
use fusions::sql::id::Id;

// RPC (ConnectRPC)
use fusions::rpc::{mount_rpc_services, AuthLayer, AuthConfig, TrustedSubject};

// AI
use fusions::ai::factory::{ClientFactory, AgentConfig};
use fusions::ai::graph_flow::{Graph, FlowRunner};

// 安全
use fusions::security::jwt::token::{make_token, make_token_by_user_id};
use fusions::security::oauth::OAuthClient; // feature: oauth

// MQ（standalone crate, not fusions::mq）
use fusion_mq::{MessageQueuePlugin, EventProducerHandle, PublishEvent};
```

## Best Practices

1. **按需引入**: 只启用需要的 features，减少编译时间和二进制大小
2. **使用组合**: 使用 `api`、`microservice` 等预定义组合
3. **版本一致**: 确保 fusions 与各个子模块版本一致
4. **注意**: 没有独立的 `grpc` feature — 使用 `rpc` (ConnectRPC)

## Examples from Codebase

- `crates/fusions/src/lib.rs` - 聚合包实现
