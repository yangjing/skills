# fusion-web

Axum-based HTTP layer: Router, middleware, extractors, `WebError`,
`WebServerBuilder`.

> Open this file when writing or modifying Axum handlers, mounting routers,
> wiring `WebAuth`, or shaping HTTP responses.

## Imports

```rust
use fusions::web::{
    Router, WebError, WebResult, WebServerBuilder,
    config::WebConfig,
    extract::JsonOrForm,
    middleware::WebAuth,
    ok_json,                                // macro (re-exported at crate root)
};
use fusions::web::{ok_id, ok_uuid};         // helper functions
#[cfg(feature = "with-ulid")]
use fusions::web::ok_ulid;
use axum::{
    Json,
    extract::{Path, Query},
    routing::{get, post, put, delete},
};
```

## State pattern — use `Application`, not a custom struct

Use `Application` directly as the Axum state. Inject services via
`FromRequestParts` so a request-scoped `mm` from a Tower layer can take
priority over the base singleton.

```rust
use fusions::core::Application;

let router = Router::new()
    .route("/api/users/{id}", get(get_user))   // axum 0.8 语法：{id}，旧 :id 会 panic
    .with_state(app);  // app: Application
```

### `FromRequestParts` for services

```rust
use axum::extract::FromRequestParts;
use axum::http::request::Parts;
use fusions::core::Application;
use crate::AppModelManager; // ModelManager<AppContext>

impl FromRequestParts<Application> for UserSvc {
    type Rejection = WebError;

    async fn from_request_parts(
        parts: &mut Parts,
        state: &Application,
    ) -> Result<Self, Self::Rejection> {
        Ok(Self::new(model_manager_from_parts(parts, state)?))
    }
}

// Helper: scoped mm from request extensions wins; otherwise fall back to
// the base singleton stored on `Application`.
fn model_manager_from_parts(
    parts: &Parts,
    state: &Application,
) -> Result<AppModelManager, WebError> {
    if let Some(mm) = parts.extensions.get::<AppModelManager>() {
        return Ok(mm.clone());
    }
    Ok(state.component::<AppModelManager>())
}
```

> `fusions::web_utils::extract_model_manager()` is the compatibility helper
> that returns the default `ModelManager<Ctx>`. For typed `AppContext`,
> write the helper above inside the application crate.

## Router

```rust
let router = Router::new()
    .route("/api/users",        get(list_users).post(create_user))
    .route("/api/users/{id}",   get(get_user))    // axum 0.8：{id} / {*rest}，非 :id / *rest
    .with_state(app);
```

### OpenAPI (`utoipa-axum`)

```rust
use utoipa_axum::router::OpenApiRouter;

pub fn routes() -> OpenApiRouter<Application> {
    OpenApiRouter::new()
        .routes(utoipa_axum::routes!(list_users))
        .routes(utoipa_axum::routes!(create_user))
}

#[utoipa::path(get, path = "/item", tag = "Users")]
async fn list_users(user_svc: UserSvc) -> WebResult<PageResult<User>> {
    let users = user_svc.list(None, None).await?;
    ok_json!(users)
}
```

## Handler shapes

```rust
use fusions::web::{WebResult, WebError, ok_json};
use axum::Json;

async fn get_user(Path(id): Path<i64>, user_svc: UserSvc) -> WebResult<User> {
    let user = user_svc.get(id).await?
        .ok_or_else(|| WebError::not_found("User not found"))?;
    ok_json!(user)
}

async fn create_user(
    user_svc: UserSvc,
    Json(req): Json<UserForCreate>,
) -> WebResult<IdI64Result> {
    let id = user_svc.create(req).await?;
    Ok(ok_id(id)?)               // ok_id is a function, returns WebResult<IdI64Result>
}

async fn search_users(
    Query(filter): Query<UserFilter>,
    Query(page): Query<Page>,
    user_svc: UserSvc,
) -> WebResult<PageResult<User>> {
    ok_json!(user_svc.search(filter, page).await?)
}
```

> Naming nit: `ok_json!` is a `macro_export` macro (`Ok(Json(v))`);
> `ok_id` / `ok_uuid` / `ok_ulid` are **functions** that construct
> `IdI64Result` / `IdUuidResult` / `IdUlidResult` and wrap in `Ok(Json(_))`.
> `ok_ulid` is gated by `with-ulid`.

## Middleware

### `WebAuth` — JWE token gate

`WebAuth` extracts the token from `Authorization: Bearer …`, an
`access_token` cookie, or an `access_token` query parameter, decrypts the
JWE, and inserts the decoded `Ctx` into request extensions.

```rust
use fusions::web::middleware::WebAuth;

let auth = WebAuth::default()
    .with_includes(vec!["/api".into()])                       // protect these prefixes
    .with_excludes(vec!["/api/public".into(), "/api/health".into()])
    .with_api_base_url("https://auth.example.com")            // remote validation (optional)
    .into_layer();
```

### `Ctx` from request extensions

```rust
use fusions::web::extensions_2_ctx;          // re-exported via fusions::web::*

async fn me(parts: Parts) -> WebResult<UserInfo> {
    let ctx = extensions_2_ctx(&parts)?;     // borrows &Ctx out of extensions
    // …
}
```

Other helpers in `fusions::web`:

- `extract_token(parts) -> Result<String, WebError>` — pulls a Bearer
  token from headers / cookie / query.
- `extract_ctx(parts, security_setting) -> Result<Ctx, WebError>` —
  full one-shot: token → JWE decrypt → `Ctx`.
- `opt_to_web_result(opt)` — `Option<T>` → `WebResult<T>` (404 on `None`).

### Common Tower layers

```rust
use tower_http::{
    trace::TraceLayer,
    cors::CorsLayer,
    compression::CompressionLayer,
    sensitive_headers::SetSensitiveRequestHeadersLayer,
};
use axum::http::header::AUTHORIZATION;

let router = router
    .layer(TraceLayer::new_for_http())
    .layer(CorsLayer::permissive())
    .layer(SetSensitiveRequestHeadersLayer::new(vec![AUTHORIZATION]))
    .layer(CompressionLayer::new());
```

> Layer ordering: `.layer()` wraps; the **last** layer applied runs **first**
> on the request. Place `AuthLayer` last (innermost), application validation
> outer.

## Extractors

### `JsonOrForm` — accept JSON or form-encoded body

```rust
use fusions::web::extract::JsonOrForm;

async fn create_user(JsonOrForm(user): JsonOrForm<UserForCreate>) -> WebResult<User> {
    // …
}
```

## `WebError`

```rust
WebError::bad_request("…")             // 400
WebError::unauthorized("…")            // 401
WebError::forbidden("…")               // 403
WebError::not_found("…")               // 404
WebError::conflict("…")                // 409
WebError::unprocessable_entity("…")    // 422
WebError::too_many_requests("…")       // 429
WebError::server_error("…")            // 500
WebError::not_implemented("…")         // 501
WebError::bad_gateway("…")             // 502
WebError::service_unavailable("…")     // 503
WebError::gateway_timeout("…")         // 504

WebError::new(code, message)
    .with_request_id(req_id)
    .with_details(json!({"field": "email"}))
```

### Error conversion

`DataError ↔ WebError` **bidirectional `From`** impls live in
`fusions::error` (feature `web`). `fusion-web` itself depends on a few
infra errors only: `From<std::io::Error>`, `From<ConfigureError>`,
`From<hyper::Error>`, `From<serde_json::Error>`.

```rust
async fn get_user(Path(id): Path<i64>, user_svc: UserSvc) -> WebResult<User> {
    // Service throws DataError; `?` converts to WebError via fusions::error.
    let user = user_svc.get(id).await?
        .ok_or_else(|| DataError::not_found("User not found"))?;
    ok_json!(user)
}
```

> `WebServerBuilder::serve()` returns `Result<(), WebError>` (not
> `DataError`). When `main` returns `fusions::Result<()>`,
> `From<WebError> for DataError` (in `fusions::error`) collapses it.

## `WebServerBuilder`

`WebServerBuilder` only knows two things: the router and an optional
shutdown receiver. The bind address comes from `fusion.web.server_addr`
in TOML — there is **no `with_addr` setter**.

```rust
use fusions::web::WebServerBuilder;

// Minimal — serve() 阻塞跑服务循环直到关机，不是「构建后返回」
WebServerBuilder::new(router).serve().await?;

// Graceful shutdown（shutdown_recv 返回 Option）
WebServerBuilder::new(router)
    .with_shutdown(app.shutdown_recv().await.expect("shutdown pair taken"))
    .serve()
    .await?;
```

`serve()`（旧名 `build()` 已 `#[deprecated]`）要求全局 `Application` 已初始化
（先 `Application::builder()...run()`），读取 `[fusion.web]` 配置；`enable_remote_addr`
adds `ConnectInfo<SocketAddr>` to handlers via `into_make_service_with_connect_info`.

## Configuration

```toml
[fusion.web]
enable             = true
server_addr        = "0.0.0.0:9500"
enable_remote_addr = true
```

## Best practices

1. **Use `Application` as state.** No custom `AppState` struct.
2. **Build services lazily.** `FromRequestParts` lets you swap base mm
   for a request-scoped mm injected by an outer Tower layer.
3. **Reach for `WebError::*` first.** Hand-rolling status codes loses the
   `code`/`message`/`request_id`/`details` envelope automatically.
4. **Auth innermost, validation outermost.** With Tower's outer-wraps-inner
   semantics, `.layer(auth)` last means auth runs first per request.

## Code locations

- `crates/fusion-web/src/server.rs` — `WebServerBuilder`
- `crates/fusion-web/src/middleware/web_auth.rs` — `WebAuth`
- `crates/fusion-web/src/util.rs` — `ok_json!` macro, `ok_id`/`ok_uuid`/`ok_ulid`, `extract_ctx`, `extensions_2_ctx`
- `crates/fusion-web/src/error.rs` — `WebError`
- `crates/fusion-web/src/extract.rs` — `JsonOrForm`
