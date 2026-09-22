---
name: fusions
description: >
  Use this skill when working on Rust backend code or docs for the Fusion
  stack (v0.3): `fusions`, `fusion-common`, `fusion-core`, `fusion-db`,
  `fusion-web`, `fusion-rpc`, `fusion-security`, `fusion-ai`, standalone
  `fusion-sql`, `fusion-mq`, `fusion-weixin`, `fusion-storage`, `hetuflow`.
  Covers DI + typed `ModelManager` over sqlx via `DbxPostgres`, Axum
  (`WebError`/`WebServerBuilder`, per-IP `RateLimiter`), ConnectRPC
  (`AuthLayer` JWE or opaque-token `AuthTokenResolver` mode,
  `TrustedSubject`, self-healing east-west transport),
  JWT/OAuth/ACS3/captcha, MQ plugins, WeChat login orchestration (three
  credential surfaces, anchoring policy, xpay/push), object storage
  (opendal operator + presigned URLs), durable workflow, AI
  openai_compatible wire (Chat/Responses factory split)/graph_flow/STT/
  TTS/voiceprint/usage-batch metering, RLS/session-var transactions, and
  migrating off the v0.2 `fusionsql` / sea-query / BMC API. Do not use for
  frontend code.
---

# fusions Framework (v0.3)

`fusions` is an **application-agnostic** Rust framework: `Application` + DI
(`Component`, `Plugin`), typed `ModelManager<C>` over `fusion-sql`, Axum via
`fusion-web`, ConnectRPC via `fusion-rpc`, JWT via `fusion-security`, plus
standalone MQ / WeChat login / object storage / durable workflow crates
(`fusion-mq` / `fusion-weixin` / `fusion-storage` / `hetuflow`). It knows
nothing about tenants, scopes, claims, or RLS policies — those come from the
**application crate** via an `AppContext: ModelContext` impl and config
structs (`AuthConfig`, `ContextValidationConfig`, `MqConfig`); keep business
semantics out of fusion crates.

## v0.3 breaking changes (read before touching DB code)

| Area | Change |
| ---- | ------ |
| SQL crates | `fusionsql` → **`fusion-sql`**, `fusionsql-core` → **`fusion-sql-core`**, `fusionsql-macros` **deleted** |
| ORM surface | The whole sea-query stack is **gone**: `Fields` / `FilterNodes` / `SeaFieldValue` macros, `OpVal*`, `FilterGroups`, `DbBmc` / `BmcConfig` / `base::*` CRUD, `page::{Page, Paged, PageResult, OrderBys}`, `with_filter_interceptor`. Write SQL with sqlx against `DbxPostgres`. |
| Auth | `fusion-rpc` adds `TrustedSubject` + `AuthConfig::trusted_subject_rpcs` (**`AuthConfig` gained a field** — literal constructions MUST add it) |
| Password | `fusion_core::security::pwd` moved to **`fusion-security`** (`fusions::security::pwd`); `SecurityError` gained 5 pwd variants (`InvalidHashFormat` = old `Error::InvalidFormat`, renamed), `fusion_core::security::Error` is JWT/HMAC-only now |
| AI metering | `AiUsageEvent::from_ctx_usage` → **`from_ctx_tokens`**; new `from_ctx_audio` for STT; `AiUsageEvent` is now `#[non_exhaustive]` (construct via those two fns only) |
| AI model factory | `Client::completion_model()` now returns the **Chat Completions** form; the Responses form moved to the new **`Client::responses_model()`**; `chat_completions_model()` and `completions_api()` are **deleted** |
| AI STT | `paraformer` module **deleted** → `dashscope::FunAsrRealtime`; `AudioStreamConfig::hotwords` → `vocabulary_ids` + `context_items`; `AudioEncoding::as_provider_str` removed |
| Misc | `SensitiveString` lost its `sea_query::Value` / `Nullable` impls; `fusion-core` dropped the unused `fusionsql` feature |

Full migration table (old symbol → replacement) at the top of [fusion-sql](references/fusion-sql.md).

## Module Map

| Module     | Import                  | Key Types                                                   |
| ---------- | ----------------------- | ----------------------------------------------------------- |
| Top-level  | `fusions::*`            | `DataError`, `DataResult`, `Result`, `codes`                |
| Common     | `fusions::common::*`    | `Ctx`, `CtxPayload`, `Error`, `OffsetDateTime`              |
| Core       | `fusions::core::*`      | `Application`, `Plugin`, `Component`, `CoreError`           |
| DB         | `fusions::db::*`        | `TypedDbPlugin`, `DbPlugin`, `DefaultModelManager`          |
| Web        | `fusions::web::*`       | `Router`, `WebError`, `WebResult`, `WebServerBuilder`       |
| RPC        | `fusions::rpc::*`       | `AuthLayer`, `ContextValidationLayer`, `TrustedSubject`, `mount_rpc_services`, `build_connect_transport`, `ConnectTransport` |
| SQL        | `fusions::sql::*`       | `ModelManager<C>`, `ModelContext`, `store::DbxPostgres`, `id::Id`, `DbConfig`, `SqlError` |
| Security   | `fusions::security::*`  | `SecurityError`, `pwd::{generate_pwd, verify_pwd, is_strong_password}`, `jwt::token::make_token`, `oauth::OAuthClient`, `captcha::CaptchaStore`, `wechat::WechatAuthClient` (feature `with-wechat`) |
| AI         | `fusions::ai::*`        | `providers::openai_compatible::*` (`completion_model`=Chat / `responses_model`=Responses), `graph_flow::*`, `llm::MeteredLlmProvider`, `llm::usage_batch::spawn_usage_batch_writer`, `speech_to_text::SpeechToText`, `providers::{dashscope, minimax, volcengine}` (STT/TTS/声纹), `AiError` |
| MQ         | `fusion_mq::*`          | `MessageQueuePlugin`, `EventProducerHandle`, `EventConsumerHandle`, `PublishEvent`, `RetryDecision` |
| Weixin     | `fusions::weixin::*` (feature `weixin`) | `WeixinLoginClient`, `WeixinCredentials`, `WeixinChannel`, `WeixinToken` / `MpToken` / `MpSigningSession`, `xpay::*`, `push::*` |
| Storage    | `fusion_storage::*`     | `build_operator`, `StorageConfig`, `generate_signed_download_url` / `generate_signed_upload_url`, `FsPresignRoutes`, `sign_read` / `sign_upload` / `verify_hmac` / `verify_upload_hmac` |
| Workflow   | `hetuflow::*`           | `prelude`（`WorkflowService` / `PgWorkflowStore` / `decide_advance` / `validate_definition` / outbox·timer workers） |

> The aggregate `fusions` re-exports each sub-crate behind a feature gate
> (`weixin` included); **`fusion-mq`, `fusion-storage`, `hetuflow*` are
> standalone** — no re-export, no `fusions::error` conversion (exception:
> `WeixinError` has an aggregate `From` under `weixin`), so map their errors
> at the application boundary. Import aggregate modules as `fusions::xxx::*`;
> MQ / storage / workflow as `fusion_mq::*` / `fusion_storage::*` /
> `hetuflow::*`; new `From` impls go in `fusions::error`, feature-gated.

## Decision tree (read first)

When designing a service or handler, place each piece into exactly one slot:

1. **Long-lived process singleton with no per-request state** — connection
   pools, RPC client pools, schedulers, message-queue producers, the base
   `ModelManager<C>` registered by `TypedDbPlugin<C>`. Use
   `#[derive(Component)]` and register in a `Plugin::build`.
2. **Application service** (per-request DB work that needs the caller's
   identity / scope) — plain `pub fn new(mm: AppModelManager) -> Self`,
   **no `#[derive(Component)]`**; construct inline per handler with a
   request-scoped `mm`. Cross-service calls share the same `mm` via
   `OtherService::new(self.mm.clone())`.
3. **Public / exempt endpoint** — the application supplies an app-defined
   helper that builds a base `mm` with a "system" `AppContext`. fusions
   never decides which endpoints are exempt.

The application crate (not fusions) wires requests through (2) vs (3).

## Gotchas (fusions-specific)

Read these once; they trip people up because they diverge from default Rust / Axum / sqlx conventions.

- **No custom `AppState`.** Use `Application` as Axum state and inject
  services via `FromRequestParts` or a Tower middleware that populates
  `request.extensions`. Never write `struct AppState { db, … }`.
- **`DataError` lives in `fusions::error`, NOT in any sub-crate.** Each
  sub-crate owns only its narrow error type (`CoreError`, `SecurityError`,
  `WebError`, `SqlError`, `DbxError`, `AiError`). Every cross-crate
  `From<X> for DataError` impl is centralised in `fusions::error`, gated by
  features — wire a new error source there, **not** in the sub-crate.
- **Application services don't derive `Component`.** Components are wired
  once at startup with the *base* `ModelManager` and never carry the
  current caller's context. A request-scoped service needs a request-scoped
  `mm`, which only exists after the application middleware calls
  `with_ctx(...)`. If you find yourself wanting a `Component` that "knows
  the current user's tenant", stop — it's an application service.
- **Default `ModelManager` is the compatibility path.**
  `fusions::db::ModelManager` is `DefaultModelManager = ModelManager<Ctx>`.
  New services SHOULD declare an `AppContext: ModelContext` and use
  `TypedDbPlugin::new(AppContext::system)` + `type AppModelManager = ModelManager<AppContext>`.
- **`ModelContext` is what fusions sees.** It exposes `audit_user_id()`,
  `req_time()`, and (optionally) `db_session_vars()`. Headers, JWT claims,
  scope rules, custom context fields all belong in the application crate.
  Do NOT extend `fusion_common::Ctx` with application semantics.
- **`SET LOCAL` is transaction-scoped.** If `ModelContext::db_session_vars()`
  returns vars (e.g. for PostgreSQL RLS), then **every read AND write MUST
  run inside a transaction** — a bare `dbx.fetch_*(dbx.db())` borrows a
  connection without session vars set, so RLS-protected tables silently
  return empty and unprotected ones leak. Wrap reads with
  `begin_txn_read_only()` and writes with `begin_txn`, or
  `mm.transaction(|mm| async move { ... })`. Caveat: the closure forms are
  a bare `BEGIN; …; COMMIT;` (no `set_config(...)`) — an RLS application
  MUST go through its own helper that layers the session vars on top
  (here: `hetu_core::db::with_read_txn` / `with_write_txn`).
- **`DbxPostgres` manual transactions, never raw `sqlx::Transaction`.**
  Cross-module signatures take `dbx: &DbxPostgres`. `dbx.execute()` returns
  `u64` (rows affected) — `.rows_affected()` on it is a compile error.
  Details: [fusion-db reference](references/fusion-db.md#dbxpostgres-手动事务).
- **DB access is hand-written sqlx through `DbxPostgres` — there is no BMC.**
  v0.3 deleted the whole BMC / query-builder layer. Repo functions run
  `dbx.fetch_*(sqlx::query_as(...).bind(..))` / `dbx.execute(sqlx::query(...))`.
  `dbx.db()` (the bare `&PgPool`) is the one thing to avoid: it bypasses the
  transaction and its `SET LOCAL` session vars. Audit columns are no longer
  auto-filled — write them explicitly from `mm.ctx_ref()?`.
- **Client-supplied `ORDER BY` has no framework validation any more.** The BMC
  allowlist died with the sea-query stack, and sqlx cannot `bind` an
  identifier — every client sort/filter column MUST pass through an
  application-side allowlist to a static column name before it reaches the
  SQL string. `Page` / `PageResult` no longer exist either; the DTO is the
  application's (here: the proto contract).
- **`AuthLayer` / `ContextValidationLayer` are application-agnostic.** All
  specifics — exempt paths/RPCs, claim mappings, error codes — come from
  the config struct passed at construction. Nothing application-specific
  gets hardcoded inside the layers.
- **`TrustedSubject` is a request *extension*, never a header** (v0.3). It
  lets an application-owned **outer** layer vouch for a non-user principal
  (a sibling bin's background job with no user token) — a client can forge
  any header but cannot set an extension. Fail-closed on two axes: the
  subject only reaches RPCs listed in `AuthConfig::trusted_subject_rpcs`,
  and that list does **not** make an RPC anonymous (no token + no subject
  → 401); a non-ASCII identity value rejects the request. `AuthConfig`
  gained this field — struct-literal configs MUST add it.
- **Feature is `rpc`, not `grpc`.** Crate `fusion-rpc` (ConnectRPC); the
  convenience bundle `microservice = web + db + security + rpc`.
- **`fusion-mq` is standalone, not `fusions::mq`.** Register
  `fusion_mq::MessageQueuePlugin::new()` when `[fusion.mq].enable = true`,
  then inject the handles as long-lived components. MQ uses its own
  Postgres pool — no `ModelManager`, no `SET LOCAL`, no `fusions::error`.
- **East-west client transport is self-healing — use the factory.** Build
  every `*ServiceClient<ConnectTransport>` via `build_connect_transport(uri)`
  (or `_with(uri, &TransportConfig)`): kernel-layer TCP probing over
  connectrpc's built-in `Reconnect` detects half-open / black-holed
  connections within ~30s and reconnects — no process restart. MUST be
  called inside a tokio runtime (`.shared()` spawns a worker). Never
  hand-roll bare `Http2Connection::lazy_plaintext` or
  `HttpClient::plaintext()` — both bypass self-heal. Details:
  [fusion-rpc reference](references/fusion-rpc.md#东西向客户端-transport自愈).
- **`#[component]` vs `#[config]`.** `#[component]` injects from the
  component registry; `#[config]` injects a `Configurable` value from the
  config system. Fields with neither get `Default::default()`.
- **Component accessors: `component`/`component_arc` panic, `try_*` are
  fallible.** Old `get_component*` names are `#[deprecated]` — never use a
  `get_` prefix for `Result`-returning accessors in new code.
- **`WebServerBuilder::serve()` runs the server loop until shutdown** (the
  old name `build()` is deprecated — it never "built and returned").
- **`AuthLayer` has two token modes: JWE and opaque (self-managed session).**
  `AuthLayer::new` decrypts a JWE and maps claims per `claim_mappings`;
  `AuthLayer::with_token_resolver(config, resolver)` hands the bearer token
  to an app-supplied `AuthTokenResolver` (e.g. server-side session lookup
  with revocation) which owns validation and returns the identity headers —
  no JWE decryption. Both modes keep the anti-forgery guarantees (returned
  header names stripped from the inbound request, unparseable values fail
  closed); the resolver error type is deliberately `()` — every failure
  maps to the same 401, the resolver logs what it can distinguish.
- **Outbound system-mode tokens are minted with `[fusion.security.pwd]`
  `secret_key`.** When a bin calls a sibling bin's RPC as a system
  principal (no user token), it mints a JWE via
  `jwt::token::make_token_by_user_id(sc, …)`; the callee's `AuthLayer`
  decrypts with its own `SecuritySetting` — **both bins MUST carry the
  same `secret_key` value**. A missing/mismatched key mints a JWE the
  callee cannot decrypt, so every call 401s: that is an outbound mint
  problem, not an `AuthLayer` config problem — don't tune the callee first.
- **`captcha` and `RateLimiter` are single-node, in-process primitives.**
  State lives in process memory: restart clears it, multi-instance counts
  per instance (divide thresholds by instance count or move to external
  storage). Captcha challenges are one-shot (`verify` deletes on hit or
  miss); `RateLimiter` rejects with 429 + `Retry-After`.
- **fusion-weixin `session_key` never persists or logs.** Dropped at the
  `fusion-security::wechat` primitive layer; the only escape is the
  explicit `exchange_mp_with_session_key` → `MpSigningSession` primitive
  (xpay dual-signing) — `SessionKey` is `ZeroizeOnDrop` with redacted
  Debug, and copies out of `expose_for_signing()` are the caller's
  discipline.
- **`llm::usage_batch` is best-effort, not billing-grade.** Drops are
  counted in `UsageMetrics`, but a killed process loses the queue.
  Shutdown = drop all `AiUsageSink` clones, then await the writer
  `JoinHandle`.
- **Secret-carrying types never derive `Debug`.** Anything holding an
  `api_key` / credential gets a hand-written impl printing `<REDACTED>` —
  `tracing::debug!(?config)` MUST NOT leak keys. `fusion-ai`'s STT types
  extend the same rule to **PHI**: audio bytes and transcript text print as
  `<N bytes/chars redacted>`.

## Core templates

These are the smallest viable shapes. Adapt names; do not invent new ones.

### Define `AppContext` + register `TypedDbPlugin`

```rust
use fusions::common::time::{OffsetDateTime, now_offset};
use fusions::core::{Application, plugin::Plugin, application::ApplicationBuilder, async_trait};
use fusions::db::TypedDbPlugin;
use fusions::sql::{ModelContext, ModelManager, id::Id};

#[derive(Clone)]
pub struct AppContext {
    audit_actor_id: Id,
    req_time: OffsetDateTime,
    // Add application-specific fields (tenant_id, scope, claims, …) here.
}

impl AppContext {
    pub fn system() -> Self {
        Self { audit_actor_id: Id::I64(0), req_time: now_offset() }
    }
}

impl ModelContext for AppContext {
    fn audit_user_id(&self) -> Id { self.audit_actor_id.clone() }
    fn req_time(&self) -> OffsetDateTime { self.req_time.to_owned() }

    // Optional: emit `SET LOCAL` vars per transaction (for RLS, audit, …)
    fn db_session_vars(&self) -> Vec<(&'static str, String)> { vec![] }
}

pub type AppModelManager = ModelManager<AppContext>;

#[tokio::main]
async fn main() -> fusions::Result<()> {
    let _app = Application::builder()
        .add_plugin(TypedDbPlugin::new(AppContext::system))
        .add_plugin(MyInfraPlugin)
        .run().await?;
    Application::await_shutdown().await;
    Ok(())
}
```

### Application service (no `Component`)

```rust
#[derive(Clone)]
pub struct UserService { mm: AppModelManager }

impl UserService {
    pub fn new(mm: AppModelManager) -> Self { Self { mm } }

    // Sibling calls share the same mm so ctx propagates without rewiring.
    fn profile_service(&self) -> ProfileService {
        ProfileService::new(self.mm.clone())
    }

    pub async fn create(&self, params: CreateParams) -> fusions::Result<User> {
        self.mm.transaction(|mm| async move {
            let user = user_repo::insert(mm.dbx().db_postgres()?, &params).await?;
            self.profile_service().init_for(user.id).await?;  // SAVEPOINT
            Ok(user)
        }).await
    }
}
```

`mm.clone()` is `Arc::clone` — per-request `Service::new(mm.clone())` is free.

### Per-request `mm` injection (app-side wiring)

fusions does NOT ship a context-injection middleware: the mapping
"trusted header → `AppContext` field" and the list of exempt RPCs are
application-specific. Every fusion application implements the same shape:

1. A Tower `Layer` placed **after `AuthLayer`** reads the injected trusted
   headers, builds an `AppContext`, clones the base `AppModelManager`,
   `with_ctx(...)`, and inserts both into `request.extensions`.
2. Handlers pull the scoped `mm` from `Context::extensions` (ConnectRPC)
   or `Parts::extensions` (Axum) via a thin app helper, then construct
   the application service inline.
3. For exempt endpoints (Login / RefreshToken / health), an app helper
   builds a base `mm` with a "system" `AppContext` so the handler call
   shape is symmetric — names like `AppCtxLayer` / `mm_from_ctx` /
   `system_mm` are yours to invent.

```rust
// Tower stack — last applied runs first:
//   cors → AuthLayer → AppCtxLayer → validation → handler
axum_router
    .layer(validation_layer)
    .layer(app_ctx_layer)        // app-defined: trusted headers → ctx + scoped mm
    .layer(auth_layer)           // fusions::rpc::AuthLayer
    .layer(cors)

async fn get_user(ctx: Context, req: GetUserRequest)
    -> Result<(GetUserResponse, Context), ConnectError>
{
    let svc = UserService::new(mm_from_ctx(&ctx)?.clone());
    let user = svc.get(req.id).await?;
    Ok((user.into(), ctx))
}
```

### Component (long-lived singleton only)

```rust
use fusions::macros::Component;

#[derive(Clone, Component)]
pub struct GatewayClients {
    #[component] mm: AppModelManager,        // base mm, seeds clients
    #[config]    config: Arc<GatewayConfig>, // from config system
    http_client: reqwest::Client,            // Default::default()
}
```

### `AuthLayer` + `ContextValidationLayer`

```rust
let auth_layer = fusions::rpc::AuthLayer::new(security_setting, fusions::rpc::AuthConfig {
    exclude_paths: &["/health"],
    preserve_identity_headers_for_paths: &[],
    exclude_rpcs: &[("myapp.auth.v1.AuthService", "Login")],
    // v0.3: RPCs a verified TrustedSubject extension may reach. Not an
    // exemption — callers with neither token nor subject still get 401.
    trusted_subject_rpcs: &[("myapp.permission.v1.PermissionService", "ListUsersByPermission")],
    claim_mappings: &[
        fusions::rpc::ClaimMapping {
            header: "x-principal-id",
            source: fusions::rpc::ClaimSource::Subject,
        },
        fusions::rpc::ClaimMapping {
            header: "x-scope-id",
            source: fusions::rpc::ClaimSource::String("scope_id"),
        },
    ],
    cookie_token_name: "access_token",
    error_code: "unauthenticated",
    error_message: "Invalid token",
}).into_middleware();

// ContextValidationLayer follows the same config-struct pattern
// (ContextValidationConfig { context_header, trigger_value, require_header, … }) —
// full shape in the fusion-rpc reference (§ ContextValidationLayer — 上下文校验).

// .layer(): last applied runs first; full stack = router.layer(validation).layer(auth_layer)
router.layer(auth_layer)
```

### Transactions (closure form preferred)

```rust
mm.transaction(|mm| async move {
    let dbx = mm.dbx().db_postgres()?;
    user_repo::insert(dbx, &user).await?;
    mm.transaction(|mm| async move {           // → SAVEPOINT
        profile_repo::insert(mm.dbx().db_postgres()?, &profile).await
    }).await
}).await?;

// Manual form — when the closure shape doesn't fit.
let mm_txn = mm.txn_cloned();
let dbx = mm_txn.dbx().db_postgres()?;
dbx.begin_txn().await?;
dbx.execute(sqlx::query("UPDATE …").bind(x)).await?;   // returns u64
dbx.commit_txn().await?;
```

RLS applications MUST NOT call `mm.transaction` directly — it is a bare
`BEGIN; …; COMMIT;` with no `set_config(...)`. Use the application helper that
layers the session vars on top (in this repo: `hetu_core::db::with_read_txn` /
`with_write_txn` and their `_pg` variants).

### Repo function (replaces BMC)

```rust
use fusions::sql::store::DbxPostgres;

#[derive(sqlx::FromRow)]
pub struct UserRow { pub id: i64, pub name: String }

// dbx methods return Result<_, DbxError>; `?` lifts into SqlError (or the app's own error).
pub async fn find_by_id(dbx: &DbxPostgres, id: i64) -> Result<Option<UserRow>, SqlError> {
    let row = dbx.fetch_optional(
        sqlx::query_as::<_, UserRow>("SELECT id, name FROM users WHERE id = $1").bind(id),
    ).await?;
    Ok(row)
}

pub async fn rename(dbx: &DbxPostgres, id: i64, name: &str) -> Result<u64, SqlError> {
    // execute returns u64 (rows affected) — .rows_affected() on it is a compile error.
    let n = dbx.execute(
        sqlx::query("UPDATE users SET name = $2 WHERE id = $1").bind(id).bind(name),
    ).await?;
    Ok(n)
}
```

## Feature flags

| Feature        | Includes                       |
| -------------- | ------------------------------ |
| `full`         | web + db + security + ai + rpc + weixin |
| `api`          | web + db + security            |
| `web-server`   | web + db                       |
| `microservice` | web + db + security + rpc      |
| `oauth`        | security + OAuth2              |

Individual: `web`, `db`, `db-sqlite`, `security`, `ai`, `rpc`, `weixin`,
`aliyun-acs3`, `openapi`, `logforth`, `tracing`, `ulid`.

Standalone workspace crates (not in the aggregate feature matrix):
`fusion-mq` (`with-postgres`); `fusion-storage` (default `fs`; backends
`fs`/`oss`/`s3`/`obs` map to opendal `services-*`, an unselected backend
errors in `build_operator`); `hetuflow` (default `runtime`; layers
`core` → `runtime` → `sqlx` → `service`).

## Error handling

> Precedence: in fusions workspaces the `DataError` pipeline below is authoritative — binaries return `fusions::Result<()>` from `main`; the generic "thiserror for libraries / anyhow for binaries" advice (e.g. rust-best-practices skill) does not apply here.

```rust
use fusions::{DataError, Result, codes};

DataError::bad_request("msg")        // 400 → validation.bad_request
DataError::unauthorized("msg")       // 401 → auth.unauthorized
DataError::forbidden("msg")          // 403 → auth.permission_denied
DataError::not_found("msg")          // 404 → resource.not_found
DataError::conflicted("msg")         // 409 → resource.conflict
DataError::failed_precondition("msg")// FailedPrecondition → validation.failed_precondition
DataError::server_error("msg")       // 500 → system.internal_error
DataError::not_implemented("msg")    // 501 → system.not_implemented（永久失败，勿映射 503）
DataError::biz_error(code, "msg", Some(json!({...})))
DataError::retry_limit("msg", retry_limit)
```

Cross-crate `From<X> for DataError` impls (all in `fusions::error`):

| Sub-crate           | Error type(s)                                   | Feature gate |
| ------------------- | ----------------------------------------------- | ------------ |
| `fusion-common`     | `Error`, `ctx::CtxError`                        | always-on    |
| `fusion-core`       | `CoreError` (聚合 Component/Configure/Security/Io/Task/Tracing/Timer) | always-on |
| `fusion-security`   | `SecurityError`                                 | `security`   |
| `fusion-web`        | `WebError` ↔ `DataError` 双向                    | `web`        |
| `fusion-rpc`        | `connectrpc::ConnectError` ↔ `DataError` 双向    | `rpc`        |
| `fusion-db`/sql     | `SqlError`, `DbxError`, `sqlx::Error`           | `db`         |
| `fusion-ai`         | `AiError`                                       | `ai`         |
| `fusion-weixin`     | `WeixinError`（Invalid→401 · Unavailable→503 · MissingUnionid→500） | `weixin` |

Plus always-on: `std::io::Error`, `serde_json::Error`, `uuid::Error`,
`chrono::ParseError`, `std::net::AddrParseError`, `std::time::SystemTimeError`,
`tokio::sync::{mpsc,oneshot}`, `tokio::task::JoinError`, `mea::mpsc::SendError`,
`config::ConfigError`.

Map at the smallest scope (repo → service → handler boundary). Application
`main` returning `fusions::Result<()>` automatically converts
`Application::run().await?`'s `CoreError` via `From<CoreError> for DataError`.

## References — load on demand

Keep this `SKILL.md` in context; open a reference file only when actively
touching that module — they are detailed and would crowd context.

| Open when working on …                                          | Reference                                                             |
| --------------------------------------------------------------- | --------------------------------------------------------------------- |
| `Ctx` / `CtxPayload` fields, time helpers, `codes` constants    | [fusion-common](references/fusion-common.md)                          |
| `Application` lifecycle, `Plugin` ordering, `Configurable`, `Component` rules, `CoreError` | [fusion-core](references/fusion-core.md)        |
| `TypedDbPlugin` / `DbPlugin`, `Dbx`/`DbxPostgres` manual txn rules | [fusion-db](references/fusion-db.md)                                |
| Axum handler shape, `WebError`, `WebServerBuilder`, `WebAuth`, `RateLimiter` | [fusion-web](references/fusion-web.md)                     |
| ConnectRPC mount, `AuthLayer` (JWE / `AuthTokenResolver` opaque mode), `ContextValidationLayer` config, `TrustedSubject` non-user principals, ConnectError mapping, east-west client transport (`build_connect_transport` + self-heal) | [fusion-rpc](references/fusion-rpc.md) |
| JWT token make/decrypt, password hashing, OAuth2 / Aliyun ACS3, `captcha`, `wechat` 原语 | [fusion-security](references/fusion-security.md)                      |
| MQ producer/consumer plugin, `fusion.mq` config, zombie reaping | [fusion-mq](references/fusion-mq.md)                                  |
| WeChat 登录编排（三凭据面 / 锚定策略 / session_key 纪律）、xpay 虚拟支付、push 回调验签解析 | [fusion-weixin](references/fusion-weixin.md)                        |
| 对象存储 Operator 工厂、预签名 URL（云 native / fs HMAC）、后端 feature 映射 | [fusion-storage](references/fusion-storage.md)                    |
| Durable workflow：定义校验 / 推进决策 / `WorkflowService` / outbox·timer workers | [hetuflow](references/hetuflow.md)                                  |
| `ModelManager<C>` / `ModelContext`, `DbxPostgres` + sqlx repo shape, transactions, `SqlError`, **v0.2 → v0.3 migration table** | [fusion-sql](references/fusion-sql.md)      |
| OpenAI-compatible LLM wire (Chat Completions / Responses 工厂分化), graph-flow Task/Graph/Session, usage metering + `usage_batch` 批量落库, streaming STT, TTS/声纹 providers | [fusion-ai](references/fusion-ai.md) |
| Feature flag combinations, top-level re-exports, quick-start    | [fusions](references/fusions.md)                                      |
