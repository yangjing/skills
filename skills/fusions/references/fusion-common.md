# fusion-common

Foundation utilities: `Ctx` / `CtxPayload`, time, UUID/ULID, `codes`
error-code constants, basic `Error` enum, serde helpers, regex patterns.

> Open this file when reading or writing values on `Ctx` / `CtxPayload`,
> shaping timestamps, or wiring response wrappers (`IdI64Result`,
> `IdUuidResult`, `WrapperResult`).

> **`DataError` is NOT in this crate.** As of v0.2 it lives in
> `fusions::error`. `fusion-common` only owns:
> - `fusion_common::Error` — base64 / date / env / key tooling errors
> - `fusion_common::codes` — string constants (`namespace.error_name`)
> - `fusion_common::ctx::CtxError` — `Ctx` parse / authz failures
>
> See [fusions](fusions.md) and [fusion-core](fusion-core.md).

## Imports

```rust
use fusions::common::{
    ctx::{Ctx, CtxPayload, CtxError},
    time::{now_utc, now_offset, now, OffsetDateTime, UtcDateTime, LocalDateTime},
    uuid::Uuid,  // feature: with-uuid
    error::{Error, Result},  // 仅基础工具错误；DataError 在 fusions::error
    codes,                    // 错误码常量集
    model::{WrapperResult, IdResult, IdI64Result, IdUuidResult, IdUlidResult, SensitiveString, UriString},
    serde::{deser_default_true, deser_default_false},
};
use fusions::common::ahash::{HashMap, HashSet};  // 高性能 HashMap
```

## Features

| Feature          | 描述                         |
| ---------------- | ---------------------------- |
| `with-uuid`      | UUID 支持 + utoipa schema   |
| `with-ulid`      | ULID 支持                    |
| `with-openapi`   | utoipa schema 生成           |
| `with-db`        | sqlx（v0.3 起不再含 sea-query）|
| `with-wasm`      | WASM 兼容                    |

> Historical note: v0.1's `with-tokio` / `with-mea` / `with-connect` /
> `with-config` features were dropped in v0.2 — they only existed to gate
> cross-crate `From<XxxError> for DataError` impls, which now all live in
> `fusions::error` and are gated there by the matching feature.
>
> v0.3: `SensitiveString` 不再 impl `sea_query::Value` / `Nullable`（整个
> sea-query 栈随 `fusionsql` → `fusion-sql` 重构一并移除）。`with-db` 下它仍有
> sqlx 的 `Type` / `Decode`（能从 `FromRow` 读出），但**没有 `Encode`** ——
> 写库时 MUST 自己取 `as_str()` / `AsUnderlying::as_underlying()` 再 `bind`。

## Core Types

### `fusion_common::Error` - 基础工具错误

```rust
#[derive(Debug, thiserror::Error)]
pub enum Error {
    FailToB64uDecode(String),
    DateFailParse(String),
    KeyFail,
    PwdNotMatching,
    MissingEnv(String),
    WrongFormat(String),
    FailedToSetEnv(String, String, String),
    FailedToRemoveEnv(String, String),
}

// 内置 From
impl From<chrono::ParseError> for Error { /* DateFailParse */ }

pub type Result<T> = core::result::Result<T, Error>;
```

> 业务错误模型 `DataError` 见 [fusions reference](fusions.md#error-模型)。
> `From<fusion_common::Error> for DataError` 在 `fusions::error` 实现。

### `fusion_common::codes` - 错误码常量

```rust
use fusions::common::codes;

codes::BAD_REQUEST          // "validation.bad_request"
codes::UNAUTHORIZED         // "auth.unauthorized"
codes::PERMISSION_DENIED    // "auth.permission_denied"
codes::NOT_FOUND            // "resource.not_found"
codes::CONFLICT             // "resource.conflict"
codes::INTERNAL_ERROR       // "system.internal_error"
codes::SERVICE_UNAVAILABLE  // "system.service_unavailable"（503，可重试）
codes::NOT_IMPLEMENTED      // "system.not_implemented"（501，永久失败，勿混用 503）
codes::RATE_LIMITED         // "rate_limit.exceeded"
codes::CHANNEL_ERROR        // "channel.error"
codes::RPC_ERROR            // "rpc.error"
// ... 完整列表见 fusion-common/src/error.rs::codes
```

**错误码命名空间**: `validation.*`, `auth.*`, `resource.*`, `system.*`, `rate_limit.*`, `channel.*`, `rpc.*`

### Ctx - 请求上下文

```rust
pub struct Ctx(Arc<CtxInner>);  // clone 成本很低
pub struct CtxPayload(Map<String, Value>);
```

`Ctx` 是 fusions 默认上下文，也是 `DefaultModelManager = ModelManager<Ctx>` 的 context 类型。需要应用专属字段时，不要把字段加进 fusions；在应用 crate 定义自己的 `AppContext: fusions::sql::ModelContext`，并使用 `ModelManager<AppContext>`。

**Build a Ctx:**

```rust
use fusions::common::ctx::{Ctx, CtxPayload};
use fusions::common::time::now_offset;

let mut payload = CtxPayload::default();
payload.set_subject("principal_123");          // sub
payload.set_tenant_id("tenant_42");            // tid (convenience for the common multi-tenant claim)
payload.set_string("scope_id", "scope_abc");   // any other custom string claim
payload.set_i64("level", 3);                   // any other custom int claim
payload.set_expires_at(expire_time);           // sets `exp` from UTC datetime

let ctx = Ctx::try_new(payload, Some(now_offset()), None /* trace_id */)?;

// Convenience builders for system code:
let ctx = Ctx::new_root();          // a "root" actor (no real principal)
let ctx = Ctx::new_super_admin();   // an audit-friendly admin actor
```

**Read from a Ctx:**

```rust
let principal: Option<&str>             = ctx.payload().get_subject();
let scope_id:  Option<&str>             = ctx.payload().get_str("scope_id");
let tenant:    Option<&str>             = ctx.get_tenant_id();
let req_time:  &DateTime<FixedOffset>   = ctx.req_time();
let req_id:    &str                     = ctx.req_id();
```

> The default `Ctx` is `Arc`-wrapped — `clone()` is cheap. For typed
> contexts (with application-specific fields), define your own
> `AppContext: ModelContext` instead of stuffing claims into `Ctx`.

### Time - 时间处理

```rust
use fusions::common::time::*;

let utc_now: UtcDateTime = now_utc();
let offset_now: OffsetDateTime = now_offset();
let local_now: OffsetDateTime = now();     // now_offset() 别名

let millis: i64 = now_epoch_millis();
let seconds: i64 = now_epoch_seconds();

// 类型别名
pub type OffsetDateTime = DateTime<FixedOffset>;
pub type UtcDateTime = DateTime<Utc>;
pub type LocalDateTime = DateTime<Local>;
```

### Result Types - 响应包装

```rust
pub struct WrapperResult<T> { pub data: T; }
pub struct IdI64Result { pub id: i64; }
pub struct IdUuidResult { pub id: uuid::Uuid; }      // feature: with-uuid
pub struct IdUlidResult { pub id: ulid::Ulid; }       // feature: with-ulid

// 使用
ok_json!(IdI64Result::from(id))
ok_json!(WrapperResult { data: users })
```

### SensitiveString - 敏感数据

```rust
use fusions::common::model::SensitiveString;

let secret = SensitiveString::new("password123");
println!("{}", secret);  // 输出: [REDACTED]
```

## Other Modules

| 模块      | 功能                                |
| --------- | ----------------------------------- |
| `uuid`    | UUID base64 编码/解析               |
| `digest`  | HMAC/SHA 哈希                       |
| `env`     | 环境变量工具                        |
| `helper`  | serde 默认值函数                    |
| `regex`   | Regex 模式                          |
| `runtime` | WASM vs native 检测                 |
| `process` | 进程信息                            |
| `meta`    | `VERSION` / `NAME` 静态常量         |

## Best Practices

1. **Context 传递**: 默认路径通过 `mm.with_ctx(ctx)` 传递 `Ctx`；typed 路径传递应用自己的 `ModelContext`
2. **时间处理**: 使用 `now_offset()` 获取本地时区时间用于显示，`now_utc()` 用于存储
3. **HashMap**: 使用 `ahash::HashMap` 替代 `std::collections::HashMap`
4. **敏感数据**: 使用 `SensitiveString` 包装密码等敏感信息

## Examples from Codebase

- `crates/fusion-common/src/ctx/mod.rs` - Ctx 实现
- `crates/fusion-common/src/time/mod.rs` - 时间工具
- `crates/fusion-common/src/error.rs` - 基础 `Error` enum + `codes` 常量
- `crates/fusions/src/error.rs` - 业务 `DataError` 实体 + 跨库 From 实现
