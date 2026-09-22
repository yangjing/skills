# fusion-weixin

微信登录编排 crate：多凭据面 + 锚定策略 + xpay 虚拟支付 / 消息推送原语。

> Open this file when working on WeChat login (App / Web / MiniProgram)、
> xpay 支付签名 / 对账、或微信推送回调验签解析。

## Import Boundary

聚合面经 `fusions` 的 `weixin` feature（`full` 组合已含）：
`fusions::weixin::*`；或直接依赖 `fusion_weixin`。`WeixinError` 在聚合
`fusions::error` 有 `From` 转换（`weixin` feature gate）：
`Invalid` → `unauthorized` 401 · `Unavailable` → `unavailable` 503（瞬态）·
`MissingUnionid` → `server_error`。

分层（owner 技术要求）：**认证原语**（HTTP 换码 + errcode 映射）在
`fusion-security::wechat`（feature `with-wechat`，见
[fusion-security reference](fusion-security.md)）；本 crate 只做**多凭据面
编排 + 锚定策略**，不含业务语义。

## 三凭据面与锚定策略（通道分化裁决）

| 凭据面 | 换码入口 | 产出 | 锚定 |
| ------ | -------- | ---- | ---- |
| App（移动应用，RN-iOS / OHOS SDK 流） | `exchange(WeixinChannel::App, code)` | `WeixinToken { unionid, openid }` | **unionid 强锚**：响应缺 unionid → `WeixinError::MissingUnionid` fail-closed，MUST NOT 回退 openid（应用未绑定开放平台是配置缺陷，不降级为弱锚定） |
| Web（网站应用，扫码 / 快速登录流） | `exchange(WeixinChannel::Web, code)` | 同上 | 同上 |
| MiniProgram（`wx.login` code） | `exchange_mp(js_code)` | `MpToken { openid, unionid: Option }` | **锚 openid**、unionid 可选随附——小程序可独立于开放平台存在，未绑定时 unionid 结构性缺失是合法常态，不是 `MissingUnionid` 故障 |

```rust
use fusions::weixin::{WeixinLoginClient, WeixinCredentials};

// 双面（既有形态，签名不变）；三面用 new_with_mp；仅小程序用 mp_only
let client = WeixinLoginClient::new_with_mp(
    WeixinCredentials::new(app_appid, app_secret),
    WeixinCredentials::new(web_appid, web_secret),
    Some(WeixinCredentials::new(mp_appid, mp_secret)),  // None = mp 面未启用
    "",                       // endpoint_base 空 = 官方端点
    Duration::from_secs(10),  // reqwest 请求级 + tokio future 级双层超时
);

let token = client.exchange(WeixinChannel::Web, &code).await?;   // unionid 锚定
let mp = client.exchange_mp(&js_code).await?;                    // openid 锚定
```

- **入口自检**：`exchange` / `exchange_mp` 对未配置通道直接 `Unavailable`——
  防空凭据出站被微信 40013 误映射成 `Invalid`（凭据错误与通道未启用是两类故障）。
- `WeixinCredentials` 携密纪律：手写脱敏 `Debug`（secret 恒 `<REDACTED>`，appid
  是前端可见公开标识保留）；全空（未启用）或全配（可用）才合法，**半配由消费方
  启动期断言拒**（`is_configured` / `is_configured` 分面判定）。

## session_key 纪律（隐私红线）

jscode2session 的 `session_key` 在 `fusion-security::wechat` 原语层**解析即弃**
——`MpSession` / 日志 / 错误面均不出现该字段。唯一例外是显式原语
`exchange_mp_with_session_key` → `MpSigningSession { openid, session_key }`
（xpay 双签名消费面，透出须经隐私评审）：

- `SessionKey` 是 `Zeroize + ZeroizeOnDrop` 新类型，`Debug` 恒
  `SessionKey(<REDACTED>)`；物理保证 = Drop 清零宿主内存。
- `expose_for_signing()` 返回**借用**——签名处即用即弃；经它复制出的副本不在
  清零纪律内，须调用方自持约束（本 crate 消费路径均为瞬时生命周期入参）。
- MUST NOT 落库 / 落日志。

## xpay 虚拟支付原语（`xpay` 模块）

双签名体系（`app_key` 签 API 侧、`session_key` 签用户态）+ 对账面：

```rust
use fusions::weixin::xpay::*;

// 签名件（纯函数）
build_sign_data(&SignDataParams {
    offer_id, env, product_id, goods_price_cents,
    out_trade_no, buy_quantity, attach,   // attach 必填，发货时原样透传
});                                       // → 键名字典序 JSON 串
pay_sig_for_client(&app_key, &sign_data);            // 客户端拉起支付的 pay_sig
pay_sig_for_api(&app_key, uri, post_body);           // 服务端 API 调用签名
signature_with_session_key(&session_key, &sign_data); // 用户态签名（xpay 要求双签）

// stable_token（access_token 换取与缓存）
let tokens = StableTokenManager::new(endpoint_base, appid, secret, timeout);
let token = tokens.token().await?;

// 对账（openid + env 是必参）
let xpay = XpayClient::new(endpoint_base, app_key, timeout);
let order: Option<QueriedOrder> = xpay
    .query_order(&token, &openid, env, OrderRef::OutTradeNo(no)).await?;
let order = order.ok_or(...)?;
order.is_paid();      // status 2..=4（支付成功面）
order.is_refunded();  // status 5 | 8 或 order_type 8（苹果退款）
order.is_closed();    // status 6
```

## push 推送原语（`push` 模块）

微信服务器推送回调的验签 / 解密 / 解析 / 应答：

```rust
use fusions::weixin::push::*;

verify_sha1_signature(&token, timestamp, nonce, &signature);            // GET 校验
verify_sha1_msg_signature(&token, timestamp, nonce, &encrypt, &msg_sig); // 消息体签名
let plaintext = decrypt_aes_message(&encoding_aes_key, &ciphertext_b64, &expected_appid)?;

let format = sniff_format(content_type, &body);   // Xml | Json
let event: XpayEvent = parse_event(format, &body)?; // XML 亦支持（Other 留痕面）
let reply = success_reply(format);                // "success" / {"errcode":0}
```

`XpayEvent` 三变体：`GoodsDeliverNotify`（发货）、`RefundNotify`（退款，Apple
IAP 退款亦推）、`Other { event, fields }`（投诉等人工面——XML 格式下顶层字段
平铺进 `fields`、CDATA 剥除，未分类事件不丢留痕）。

## Code locations

- `crates/fusion-weixin/src/lib.rs` — `WeixinLoginClient` / 凭据面 / `SessionKey` / `MpSigningSession`
- `crates/fusion-weixin/src/xpay.rs` — 签名件 / `StableTokenManager` / `XpayClient::query_order`
- `crates/fusion-weixin/src/push.rs` — 验签 / AES 解密 / `XpayEvent` 解析 / 应答
- 认证原语在 `crates/fusion-security/src/wechat.rs`（`WechatAuthClient`）
- 聚合 `From`：`repos/fusions/crates/fusions/src/error.rs`（`weixin` feature）
