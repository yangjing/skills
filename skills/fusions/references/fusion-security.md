# fusion-security

Security primitives: JWT (JWE) tokens, password hashing, OAuth2 client,
Aliyun ACS3-HMAC-SHA256 request signing.

> Open this file when working on JWE token issuance/decryption, password
> hashing, OAuth login flows, or anything calling
> `fusions::security::*` / `fusions::core::security::*`.

## Cargo features

| Feature              | Includes                                                         |
| -------------------- | ---------------------------------------------------------------- |
| `with-jwt`           | `josekit` for JWE issuance / decryption                          |
| `with-oauth`         | `with-jwt` + `oauth2` crate (gates `oauth` module)               |
| `with-openid`        | `with-jwt` + `openidconnect` (re-exports `openidconnect`)        |
| `with-aliyun-acs3`   | Aliyun ACS3-HMAC-SHA256 request signing (`reqsign_aliyun_acs3`)  |

The `fusions` aggregate gates these via top-level features: `security`
(implies `with-jwt`), `oauth` (implies `security` + `with-oauth`),
`aliyun-acs3` (implies `security` + `with-aliyun-acs3`).

## Imports

```rust
// JWT token (feature: with-jwt) — note the nested `token` module path
use fusions::security::jwt::token::{make_token, make_token_by_user_id};
use fusions::security::{SecurityError, SecurityResult};

// Token decryption lives in fusion-core (since `SecuritySetting` does too).
use fusions::core::security::SecurityUtils;
use fusions::core::configuration::SecuritySetting;

// Password hashing lives in fusion-security (moved out of
// fusion-core::security::pwd in v0.3 — fusion-core is JWT/HMAC-only now).
use fusions::security::pwd::{generate_pwd, verify_pwd, is_strong_password};

// OAuth (feature: with-oauth)
use fusions::security::oauth::{
    OAuthClient, OAuthConfig, OAuthError, OAuthProvider, OAuthTokenResponse,
};

// Aliyun ACS3 signing (feature: with-aliyun-acs3)
use fusions::security::reqsign_aliyun_acs3::{
    Credential, RequestSigner, StaticCredentialProvider,
};
```

## SecurityError

```rust
pub enum SecurityError {
    TokenGeneration,
    TokenVerification(String),
    TokenExpired,
    InvalidToken,
    OAuth(String),
    FailedToHashPassword,
    InvalidPassword,                    // verify_pwd: hash valid, wrong password
    FailedToVerifyPassword,
    InvalidHashFormat,                  // stored hash is not PHC format
    PasswordWorkerJoinFailed(String),   // spawn_blocking JoinError
    Core(fusion_core::security::Error), // wraps lower-level crypto errors
    Custom(String),
}

pub type SecurityResult<T> = core::result::Result<T, SecurityError>;
```

`SecurityError → DataError` is in `fusions::error` (feature `security`).
`OAuthError` has its own `OAuthResult<T>` and surfaces through
`SecurityError::OAuth` when crossing layers; map at the smallest scope.

## JWT (JWE) tokens

`make_token` uses `SecurityUtils::encrypt_jwt` (JWE direct algorithm) with
`SecuritySetting.pwd.secret_key` as the AES key. Configuration secrets are
wrapped in `ZeroizeOnDrop`.

### Issue

```rust
use fusions::common::ctx::CtxPayload;
use fusions::common::time::now_offset;
use fusions::security::jwt::token::{make_token, make_token_by_user_id};

let mut payload = CtxPayload::default();
payload.set_subject("principal_123");
payload.set_string("scope_id", "scope_abc");
payload.set_expires_at(now_offset() + chrono::Duration::hours(2));

let token = make_token(security_setting, payload)?;

// Convenience: subject-only
let token = make_token_by_user_id(security_setting, "principal_123")?;
```

### Decrypt

```rust
use fusions::core::security::SecurityUtils;

let (payload, _header) = SecurityUtils::decrypt_jwt(security_setting.pwd(), &token)?;
let principal_id = payload.get_subject();
let scope_id     = payload.get_str("scope_id");
```

### Configuration

```toml
[fusion.security.pwd]
secret_key = "0123456789ABCDEF0123456789ABCDEF"   # 32 ASCII chars (AES-256 key)
expires_in = 7200
default_pwd = "changeme"

[fusion.security.token]
secret_key  = "0123456789ABCDEF0123456789ABCDEF"
public_key  = ""
private_key = ""
expires_in  = 3600
```

## Password hashing — `fusion-security::pwd`

Argon2 + random 16-byte salt, executed on `spawn_blocking`. The persisted
format is `#<version>#<argon2-encoded-hash>` (current `version = 1`).
Moved out of `fusion-core::security::pwd` in v0.3 — import from
`fusions::security::pwd`; `fusion-core` no longer depends on argon2.
The old `fusion_core::security::Error::InvalidFormat` variant was renamed
to `SecurityError::InvalidHashFormat` in the move.

```rust
use fusions::security::pwd::{generate_pwd, verify_pwd, is_strong_password};

let hashed: String = generate_pwd("Plain.Password1").await?;    // "#1#$argon2id$..."
let version: u16   = verify_pwd("Plain.Password1", &hashed).await?;

// Pre-flight complexity check (≥8 chars, ASCII letter + digit, allowed
// special chars only). Use BEFORE hashing to reject weak inputs early.
if !is_strong_password(candidate) {
    return Err(DataError::bad_request("Password too weak"));
}
```

`verify_pwd` returns `SecurityError::InvalidPassword` when the stored hash
is valid but the password doesn't match — login-style handlers SHOULD
match it explicitly to surface a distinct "bad credentials" error, and
treat `FailedToHashPassword` / `InvalidHashFormat` /
`PasswordWorkerJoinFailed` as server-side trouble. Note the default
`From<SecurityError> for DataError` (in `fusions::error`) maps
`FailedToVerifyPassword` — a server-side argon2 failure — to
`DataError::unauthorized` alongside `InvalidPassword`, while the other
three pwd variants map to `DataError::server_error`; rely on explicit
matches, not the default conversion, when the distinction matters.

## OAuth2 (feature `oauth`)

Built-in providers: **Gitee** (`OAuthProvider::gitee()`), **GitHub**
(`OAuthProvider::github()`). Other providers (WeChat, Google, …) are NOT
shipped — register them by constructing `OAuthProvider` fields directly if
you need to extend.

```rust
let config = OAuthConfig {
    client_id:     "your_client_id".into(),
    client_secret: "your_client_secret".into(),
    redirect_url:  "https://example.com/callback".into(),
    scopes:        vec!["user:email".into()],
};

let client = OAuthClient::new(OAuthProvider::github(), &config)?;

// Step 1: redirect user to this URL
let auth_url = client.get_authorize_url("opaque_state_token");

// Step 2: handle the callback — `user_id` is your app's principal id, used
// to key the token store for refresh later.
let token: OAuthTokenResponse = client.exchange_code(
    "code_from_query_param",
    "opaque_state_token",
    "your_app_user_id",
).await?;

// Later: fetch user info using cached access_token from the token store
let user_info = client.get_user_info("your_app_user_id").await?;
```

The token store defaults to `MemoryTokenStore`; pass
`OAuthClient::with_token_store(...)` to back it with persistent storage in
production.

## Aliyun ACS3-HMAC-SHA256 signing (feature `aliyun-acs3`)

`fusion-security` implements the v3 multi-header signature spec on top of
opendal-reqsign's `SignRequest` / `ProvideCredential` traits. Use this when
calling Aliyun product APIs that require ACS3 signing (e.g. Dysmsapi).

```rust
use fusions::security::reqsign_aliyun_acs3::{
    Credential, RequestSigner, StaticCredentialProvider,
};
use reqsign_core::{Context, Signer};
use http::Request;
use bytes::Bytes;

let cred = Credential::new("ak", "sk");                          // or `from_env(ak, sk)`
let signer = Signer::new(
    Context::new(),
    StaticCredentialProvider::new(cred),
    RequestSigner::new(),
);

let req = Request::builder()
    .method("POST")
    .uri("https://dysmsapi.aliyuncs.com/")
    .header("x-acs-action",  "SendSms")
    .header("x-acs-version", "2017-05-25")
    .body(Bytes::new())?;
let (mut parts, _body) = req.into_parts();
signer.sign(&mut parts, None).await?;
// parts.headers now carry Authorization / x-acs-date /
// x-acs-signature-nonce / x-acs-content-sha256
```

## Captcha — 进程内图形验证码（无 feature gate）

防自动化刷量前置件：4 位算式（`a + b = ?`，答案 4..=38）渲染为自研 SVG
（无第三方依赖、无行为采集），3 条干扰线。

```rust
use fusions::security::captcha::CaptchaStore;

let store = CaptchaStore::new();          // 默认 TTL 2 分钟
let challenge = store.generate();         // { id, svg } —— svg 直接内嵌前端展示
// … 用户提交 id + 答案 …
let ok: bool = store.verify(&challenge.id, user_answer);  // trim 宽松
```

语义要点：

- **一次性**：`verify` 取出即删，**成败皆作废**；过期同样作废。
- **单机口径**：状态在进程内存，重启即失效；`Clone` = 共享同一存储，适合随
  服务状态分发。多实例部署各自独立（与 `RateLimiter` 同假设）。
- **内存上界**：在途条目硬上限 65,536；触达（正常流量远不可达 = 刷量信号）
  整体清空——在途验证码集体失效可接受，2 分钟 TTL 使真实用户重取成本低。
- **手写 `Default`**：`CaptchaStore::default()` 与 `new()` 同语义（默认
  TTL）——derive 的 `Default` 会把 TTL 置零使所有挑战立即过期，故手写。
  自定义 TTL（测试）走 `with_ttl`。
- SVG 字符集固定（数字/加号/等号/问号），无用户输入进 SVG，无注入面。

## WeChat 认证原语（feature `with-wechat`）

HTTP 换码 + errcode 映射的**原语层**；多凭据面编排与 unionid 锚定策略在
`fusion-weixin` crate（见 [fusion-weixin reference](fusion-weixin.md)）。

```rust
use fusions::security::wechat::WechatAuthClient;

let auth = WechatAuthClient::new("https://api.weixin.qq.com", Duration::from_secs(10));

// oauth2 面（App / Web 通道）：code → WechatCodeSession
// { access_token, openid, unionid: Option, expires_in: Option }
// （unionid 缺省 = 应用未绑定开放平台；锚定断言在 fusion-weixin 层）
auth.code_to_session(&appid, &secret, &code).await?;

// 小程序面：js_code → MpSession { openid, unionid: Option }——与 oauth2 面
// 分立的响应结构，MUST NOT 复用混构
auth.jscode_to_session(&appid, &secret, &js_code).await?;

// 显式例外原语：携 session_key（MpSessionWithKey）——仅虚拟支付签名等
// 消费面用；session_key 在本层解析即弃，除此入口外不出现在任何返回值
auth.jscode_to_session_with_key(&appid, &secret, &js_code).await?;
```

错误面 `WechatAuthError` 两分类（换码消费方按此分流）：
`Invalid { code, message }`（请求侧错误——code 无效 / 凭据无效）与
`Unavailable { message }`（出站侧——网络 / 超时 / 微信系统忙；**errcode 45011
分钟配额也算瞬态 Unavailable**）。

## Middleware integration

Token issuance is `fusion-security`'s job; token-on-the-wire enforcement
lives in the transport layers:

- HTTP / Axum → use `fusions::web::middleware::WebAuth` (see
  [fusion-web reference](fusion-web.md#middleware)).
- ConnectRPC → use `fusions::rpc::AuthLayer` (see
  [fusion-rpc reference](fusion-rpc.md#authlayer--认证中间件)).

Both decrypt the JWE token, then either inject `Ctx` into
`request.extensions` (WebAuth) or rewrite the request with trusted headers
according to `claim_mappings` (AuthLayer). The application crate is
responsible for the next hop — building `AppContext` from those headers.

## Best practices

1. **Never hardcode secrets.** Pass `SecuritySetting` via the config system
   (`[fusion.security.pwd]` / `[fusion.security.token]`); production keys
   SHOULD come from a secret manager or env var indirection.
2. **JWE, not JWS.** Tokens are encrypted (confidentiality + integrity), so
   you can put any short-lived claims in `CtxPayload` without leaking them.
3. **Always `is_strong_password` before `generate_pwd`.** It's the only
   built-in complexity gate and runs synchronously — cheap to call.
4. **Persist OAuth tokens.** Swap out `MemoryTokenStore` for a Postgres /
   Redis-backed `TokenStore` impl in production so refresh tokens survive
   restarts.

## Code locations

- `crates/fusion-security/src/jwt/token.rs` — `make_token` / `make_token_by_user_id`
- `crates/fusion-core/src/security/security_utils.rs` — `SecurityUtils::{encrypt_jwt, decrypt_jwt}`
- `crates/fusion-security/src/pwd.rs` — `generate_pwd` / `verify_pwd` / `is_strong_password`
- `crates/fusion-security/src/captcha.rs` — `CaptchaStore::{generate, verify}`
- `crates/fusion-security/src/wechat.rs` — `WechatAuthClient::{code_to_session, jscode_to_session, jscode_to_session_with_key}`
- `crates/fusion-security/src/oauth/mod.rs` — `OAuthProvider` / `OAuthClient` / `MemoryTokenStore`
- `crates/fusion-security/src/reqsign_aliyun_acs3/` — ACS3 v3 signing
