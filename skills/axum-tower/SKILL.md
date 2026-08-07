---
name: axum-tower
description: 在 Rust 项目中编写或评审 HTTP Web 服务代码时使用：axum 0.8 handler / extractor / Router 路由、tower 中间件栈（Layer / Service / ServiceBuilder）、hyper 层调优，以及超时 / 限流 / CORS / 压缩 / 错误传播等横切能力——即使用户只说「加个 HTTP 接口 / API 端点 / 中间件」而未点名 axum。不适用于：ConnectRPC 服务装配与 fusions 技术栈的 handler 状态注入（以 fusions skill 为准）、纯前端代码。
globs:
  - "**/*.rs"
---

# Axum + Tower Patterns

## Skill 执行协议

1. Trigger：编写 / 评审 axum、tower、hyper Web 代码时使用本 skill。
2. Load：先读本文 Quick Reference 与 Core Patterns；按需加载 references/。
3. Apply：本文示例为**通用 axum 形态**；使用 fusions 技术栈的项目 MUST 优先遵 [fusions skill](../fusions/SKILL.md) 的覆盖约定——handler 状态从请求扩展取请求级 scoped `ModelManager`，MUST NOT 用 `State` 直取 base mm（绕过 `SET LOCAL` session vars，RLS 表静默空结果）、MUST NOT 自建 `struct AppState`。
4. Conflict：本文与 fusions skill 冲突时，fusions 技术栈项目以 fusions 为准。
5. MUST NOT：把本文的通用 State 注入示例照搬进 fusions 技术栈业务 handler。

## Quick Reference

| Category | Pattern     | Usage                                              |
| -------- | ----------- | -------------------------------------------------- |
| Axum 0.8 | 路由参数    | `/users/{id}`、`/files/{*rest}`（旧 `/:id` / `/*rest` 直接 panic） |
| Axum     | Handler     | `async fn handler(Extractors) -> Result<Response>` |
| Tower    | Middleware  | `.layer(ServiceBuilder::new().layer(...))`         |
| Error    | Propagation | `?` operator with `From<T> for AppError`           |

## Core Patterns

### Axum Handler（通用形态）

```rust
use axum::{
    extract::{Path, State, Json, Query},
    response::{IntoResponse, Response},
    http::StatusCode,
};

// 通用 axum 形态示例；fusions 技术栈不适用（见执行协议第 3 条）
async fn get_user(
    Path(id): Path<i64>,
    State(state): State<AppState>,       // AppState: Clone（内部字段用 Arc / Pool）
) -> Result<Json<User>, AppError> {
    let user = state.repo.find_user(id).await?
        .ok_or(AppError::NotFound)?;
    Ok(Json(user))
}
```

Extractor 硬规则（axum 0.8）：

- 只有**最后一个**参数可以消费 body（`Json` / `Bytes` / `Multipart` 等
  `FromRequest`）；前面参数只能是 `FromRequestParts`（`State` / `Path` /
  `Query` / `HeaderMap`）。
- 自定义 extractor 直接实现 `FromRequestParts` / `FromRequest`（原生 async fn，
  0.8 起不再用 `#[async_trait]`）。
- `Option<Json<T>>` 等的语义是「T 实现 `Optional*` trait」，不再吞掉解析错误
  转 `None`。
- handler 不满足 trait 的天书报错 → 给 handler 加 `#[axum::debug_handler]`。

### Tower Middleware Stack

```rust
use std::time::Duration;
use tower::ServiceBuilder;
use tower_http::{
    trace::TraceLayer,
    cors::{Any, CorsLayer},
    compression::CompressionLayer,
    limit::RequestBodyLimitLayer,
    timeout::TimeoutLayer,
};

let router = Router::new()
    .route("/api/users", get(list_users))
    .layer(
        ServiceBuilder::new()
            .layer(TraceLayer::new_for_http())
            .layer(CorsLayer::new().allow_origin(Any))
            .layer(CompressionLayer::new())
            .layer(RequestBodyLimitLayer::new(1024 * 1024))  // 1MB
            .layer(TimeoutLayer::new(Duration::from_secs(30)))
    );
```

顺序语义（易错）：

- `ServiceBuilder` 内按**声明顺序自上而下**处理请求（上例请求先过 Trace）。
- 直接链式 `Router::layer(a).layer(b)` 则**后加的在最外层**（请求先过 b）——
  与 ServiceBuilder 相反。混用时以此为准推导执行顺序。
- `Router::layer` 只包裹**已注册**的路由；CORS 要覆盖 404/405 预检时必须加在
  整个 Router（含 fallback）最外层。

## Common Mistakes

| Mistake                       | Correct                                    |
| ----------------------------- | ------------------------------------------ |
| 路由写 `/:id` / `/*rest`      | axum 0.8 用 `/{id}` / `/{*rest}`，旧语法 panic |
| `Rc<T>` in State              | Use `Arc<T>`                               |
| Blocking in async             | `spawn_blocking`（注意：已开跑的 blocking 任务不可 abort） |
| `unwrap()` in handlers        | Use `?` with error conversion              |
| `allow_credentials(true)` + wildcard origin | 运行时 panic；credentials 必须配显式 origin 列表 |
| 对 SSE / 长流式响应套 CompressionLayer / TimeoutLayer | 压缩会缓冲破坏流式；超时按整响应计。用 `NotForContentType` 排除或单独挂路由 |
| 每请求新建 `reqwest::Client`  | Client 内部已是 Arc + 连接池，进程级复用单例；单请求超时用 `RequestBuilder::timeout` |
| 裸 `JoinHandle` 持连接被 drop | drop 只 detach 不取消；用 `tokio_util::task::AbortOnDropHandle` 保证取消即释放 |

## References (按需加载)

- 需要 handler 签名、extractor 组合、Router 嵌套、SSE / WebSocket / 文件上传等具体形态时 → 读 [references/axum.md](references/axum.md)
- 需要自定义 Layer / Service 实现、middleware 执行顺序、tower-http 组件配置细节时 → 读 [references/tower.md](references/tower.md)

## Related Skills

- [`fusions`](../fusions/SKILL.md)：Fusion 栈核心库模式（fusions 技术栈项目以其为准）
- [`rust-best-practices`](../rust-best-practices/SKILL.md)：通用 Rust 惯用法
