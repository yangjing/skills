# fusion-storage

对象存储**机制层** crate：opendal `Operator` 工厂 + 预签名 URL。只收机制不收
业务——storage key 约定、公开访问 base 的 env 语义、路由挂载、HMAC 密钥装配
与默认密钥、默认 root、TTL 策略**全部留在消费方**。

> Open this file when working on object storage upload/download endpoints、
> presigned URL 生成与校验、或 `fusion_storage` 后端 feature 选择。

## Import Boundary

Standalone workspace crate（同 `fusion-mq`，聚合 `fusions` 不 re-export、
`fusions::error` 无转换——错误是 `Result<_, String>` / 应用侧映射）：

```rust
use fusion_storage::{build_operator, StorageConfig};
```

后端 feature 透传（每个 feature 映射 opendal 的 `services-*`）：

| Feature | 后端 |
| ------- | ---- |
| `fs`（default） | 本地文件系统 |
| `oss` | 阿里云 OSS |
| `s3` | AWS S3 兼容 |
| `obs` | 华为云 OBS |

未启用的后端在 `build_operator` 返回指向 feature 的错误（fail-closed，不是
panic）。云后端一律显式启用；`fs` 收进 default 使最小接入与单测可用。

## Operator 工厂

```rust
let config = StorageConfig::new("oss");   // backend 名；其余字段按消费方配置填
let operator: opendal::Operator = build_operator(&config).map_err(|e| ...)?;
```

## 预签名 URL（两形态自动分流）

- **云后端**：走 opendal **native presign**（capability gate 自动分流）——
  fs → 云切换零代码改动。
- **fs 后端**：走 **HMAC 签名的本地路由 URL**——URL 组装机制在 crate，路径
  字面量（挂载点）由消费方经 `FsPresignRoutes { authority, scheme, read,
  write }` 注入（`read` / `write` 必须与消费方实际挂载的本地路由一致）。

```rust
use fusion_storage::{
    generate_signed_download_url, generate_signed_upload_url,
    sign_read, sign_upload, verify_hmac, verify_upload_hmac,
    content_disposition_attachment, FsPresignRoutes,
};

let routes = FsPresignRoutes {
    authority: "files.example.test", scheme: "https",
    read: "/storage", write: "/storage-upload",
};

// 生成（云 = native presign；fs = HMAC 本地路由）。签名绑定 creator_id。
let url = generate_signed_download_url(
    &operator, &key, &creator_id, ttl_secs,
    Some("report.pdf"),          // 下载文件名（Content-Disposition），可 None
    &routes, &hmac_secret,
).await?;
let url = generate_signed_upload_url(
    &operator, &key, &creator_id, ttl_secs, &routes, &hmac_secret,
).await?;

// fs 路由的校验侧（挂载点 handler 里）
let sig = sign_read(&key, expires, &creator_id, &hmac_secret);
let ok = verify_hmac(&key, expires, &token, &creator_id, &hmac_secret);
let ok = verify_upload_hmac(&key, expires, &token, &creator_id, &hmac_secret);

// 下载响应的附件语义
let cd = content_disposition_attachment("report.pdf");
```

fs HMAC 行为细节：

- **expires 按 ttl 桶对齐**（`(now/ttl + 2) * ttl`）：同一桶内同
  `(key, creator_id)` 签名完全一致——列表接口现签 URL 时轮询方不会每次都
  判「数据变了」（如视频 src 更新 → 重载）；桶内最短剩余有效期 ≥ ttl。
- **`hmac_secret` MUST 进程不变**——签名缓存按此假设工作，进程内轮换会复用
  旧密钥的缓存 URL。
- opendal 0.55+ 的 `presign_write` 丢弃 content_type——upload confirm 步骤
  MUST 调 `op.stat` 重新校验 size / content_type / prefix。

## Code locations

- `crates/fusion-storage/src/operator.rs` — `build_operator`（四后端分支）
- `crates/fusion-storage/src/presign.rs` — native presign / fs HMAC 分流、`FsPresignRoutes`
- `crates/fusion-storage/src/hmac.rs` — `sign_read` / `sign_upload` / `verify_hmac` / `verify_upload_hmac`
- `crates/fusion-storage/src/config.rs` — `StorageConfig`
