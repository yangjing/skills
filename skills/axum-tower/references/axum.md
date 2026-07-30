# Axum Web Framework Patterns（axum 0.8）

基于 [Axum 官方文档](https://docs.rs/axum) 与 [axum 0.8 发布说明](https://tokio.rs/blog/2025-01-01-announcing-axum-0-8-0)。

> **fusions 技术栈注意**：本文的 `State(...)` 注入示例为通用 axum 形态；fusions
> 技术栈的 handler MUST 从请求扩展取请求级 scoped `ModelManager`（见 fusions
> skill），直取 base mm 会绕过 `SET LOCAL` session vars 致 RLS 表静默空结果。

## axum 0.8 迁移要点（旧代码常见坑）

| 0.7 及以前 | 0.8 | 后果 |
|---|---|---|
| `/users/:id`、`/files/*rest` | `/users/{id}`、`/files/{*rest}` | 旧语法**运行时 panic**，不是静默兼容 |
| 路径字面 `{` `}` | `{{` `}}` 转义 | — |
| 自定义 extractor 用 `#[async_trait]` | 直接原生 `async fn`（RPITIT） | 保留宏无法编译 |
| `Option<Json<T>>` 吞解析错误转 `None` | 要求 `T: OptionalFromRequest*`；解析错误仍拒绝 | 语义变更，别再用它兜错 |

## Router

### 基本路由

```rust
use axum::{
    Router,
    routing::{get, post, put, delete},
};

let router = Router::new()
    .route("/users", get(list_users).post(create_user))
    .route("/users/{id}", get(get_user).put(update_user).delete(delete_user));
```

### 嵌套与合并

```rust
let router = Router::new()
    .nest("/api/v1", v1_routes())     // 前缀嵌套
    .merge(health_routes());          // 平级合并

fn v1_routes() -> Router<AppState> {
    Router::new()
        .route("/users", get(list_users))
        .route("/users/{id}", get(get_user))
}
```

## Handlers

### Extractor 顺序硬规则

只有**最后一个**参数可以消费 body（`FromRequest`：`Json` / `Bytes` / `Form` /
`Multipart`）；其余参数必须是 `FromRequestParts`（`State` / `Path` / `Query` /
`HeaderMap` / `Extension`）。顺序错了报的是难读的 trait bound 错误——先加
`#[axum::debug_handler]` 再排查。

```rust
async fn create_user(
    Path(tenant_id): Path<i64>,           // 路径参数
    Query(filter): Query<UserFilter>,     // 查询参数
    State(state): State<AppState>,        // 应用状态
    Json(body): Json<CreateUser>,         // JSON 请求体 —— 必须最后
) -> Result<Json<User>, AppError> {
    let user = state.repo.create_user(tenant_id, body).await?;
    Ok(Json(user))
}
```

### 返回类型

```rust
async fn get_user() -> Json<User> { /* … */ }                       // 简单 JSON
async fn create_user() -> (StatusCode, Json<User>) {                // 带状态码
    (StatusCode::CREATED, Json(user))
}
async fn find_user() -> Result<Json<User>, AppError> { /* … */ }    // 错误处理
async fn delete_user() -> StatusCode { StatusCode::NO_CONTENT }     // 空响应
```

## Extractors

### Path

```rust
Path(id): Path<i64>                       // 单参数
Path((a, b)): Path<(i64, String)>         // 多参数 tuple
#[derive(Deserialize)]
struct UserPath { tenant_id: i64, user_id: i64 }
Path(params): Path<UserPath>              // 结构体（字段名对应 {tenant_id}/{user_id}）
```

### Query / Json

```rust
#[derive(Deserialize)]
struct UserQuery { name: Option<String>, page: Option<u32> }
Query(query): Query<UserQuery>

Json(body): Json<CreateUser>
// 可选 body（0.8：T 需实现 OptionalFromRequest；解析错误仍会被拒绝，不转 None）
body: Option<Json<CreateUser>>
```

### State

```rust
#[derive(Clone)]
struct AppState {
    repo: Arc<UserRepo>,       // 共享字段用 Arc / Pool（其内部已是 Arc）
    config: Arc<AppConfig>,
}

let router = Router::new()
    .route("/users", get(list_users))
    .with_state(state);

// 子状态提取：#[derive(FromRef)] 让 State<Arc<UserRepo>> 从 AppState 派生
State(state): State<AppState>
```

### Extension

```rust
.layer(Extension(request_ctx))            // 中间件注入
Extension(ctx): Extension<RequestCtx>     // handler 提取
```

### 自定义 Extractor（0.8：原生 async fn，无 `#[async_trait]`）

```rust
use axum::{extract::FromRequestParts, http::request::Parts};

struct RequireCtx(RequestCtx);

impl<S> FromRequestParts<S> for RequireCtx
where
    S: Send + Sync,
{
    type Rejection = AppError;

    async fn from_request_parts(parts: &mut Parts, _state: &S) -> Result<Self, Self::Rejection> {
        let ctx = parts.extensions.get::<RequestCtx>()
            .ok_or(AppError::Unauthorized)?;
        Ok(RequireCtx(ctx.clone()))
    }
}
```

## Error Handling

```rust
use axum::response::{IntoResponse, Response};

enum AppError {
    NotFound,
    Unauthorized,
    Internal(anyhow::Error),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, message) = match &self {
            AppError::NotFound => (StatusCode::NOT_FOUND, "not found"),
            AppError::Unauthorized => (StatusCode::UNAUTHORIZED, "unauthorized"),
            AppError::Internal(_) => (StatusCode::INTERNAL_SERVER_ERROR, "internal error"),
        };
        // 5xx 详情只落日志，不回给客户端（避免泄露内部信息）
        (status, Json(json!({ "message": message }))).into_response()
    }
}

// handler 中 `?` 自动转换：为底层错误实现 From<E> for AppError
async fn handler() -> Result<Json<User>, AppError> {
    let user = find_user().await?;
    Ok(Json(user))
}
```

## Middleware

### from_fn

```rust
use axum::middleware::{from_fn, from_fn_with_state};

async fn auth_middleware(
    State(keys): State<AuthKeys>,
    req: Request,
    next: Next,
) -> Result<Response, AppError> {
    // 验证逻辑…
    Ok(next.run(req).await)
}

.layer(from_fn(logging_middleware))                    // 无状态
.layer(from_fn_with_state(keys, auth_middleware))      // 有状态
```

### 常用 Tower Layer

```rust
use axum::http::header::AUTHORIZATION;
use tower_http::{
    trace::TraceLayer,
    cors::{Any, CorsLayer},
    compression::CompressionLayer,
    limit::RequestBodyLimitLayer,
    timeout::TimeoutLayer,
    sensitive_headers::SetSensitiveRequestHeadersLayer,
};

.layer(TraceLayer::new_for_http())
.layer(CorsLayer::new()
    .allow_origin(Any)          // ⚠️ 与 allow_credentials(true) 互斥（运行时 panic）
    .allow_methods(Any)
    .allow_headers(Any))
.layer(CompressionLayer::new()) // ⚠️ SSE/流式响应勿压缩（tower-http 已内置排除 text/event-stream）
.layer(RequestBodyLimitLayer::new(1024 * 1024))
.layer(TimeoutLayer::new(Duration::from_secs(30)))
.layer(SetSensitiveRequestHeadersLayer::new(vec![AUTHORIZATION]))
```

## Best Practices

1. **状态管理**: `AppState: Clone`，内部共享字段用 `Arc`（连接池自身已是 Arc，不再包）
2. **错误处理**: 为统一错误类型实现 `IntoResponse`；5xx 详情只落日志
3. **路由组织**: 使用 `nest` 和 `merge` 组织路由；路径参数一律 `{id}` 语法
4. **中间件顺序**: 链式 `.layer()` 后加的在最外层；`ServiceBuilder` 内自上而下（见 tower.md）
5. **类型安全**: 自定义 Extractor 封装通用逻辑；报错难读先上 `#[axum::debug_handler]`

## References

- [Axum Docs](https://docs.rs/axum)
- [axum 0.8 announcement](https://tokio.rs/blog/2025-01-01-announcing-axum-0-8-0)
- [Tower HTTP Docs](https://docs.rs/tower-http)
