# fusion-core

核心框架：Application 生命周期、Component 依赖注入、Configuration 配置、Plugin 插件系统。

## Imports

```rust
use fusions::core::{
    Application,
    application::{ApplicationBuilder, ShutdownRecv},
    component::{Component, ComponentArc, ComponentInstaller, DynComponentArc},
    configuration::{Configurable, ConfigRegistry, FusionConfigRegistry, FusionSetting, SecuritySetting},
    plugin::Plugin,
    error::{CoreError, CoreResult},
    Result,  // Result<T> = Result<T, fusion_core::CoreError>
};
use fusions::core::async_trait;
use fusions::DataError;  // 业务错误模型，定义在 fusions::error
```

## Application 生命周期

### 完整示例

```rust
use config::{File, FileFormat};
use fusions::core::{Application, application::ApplicationBuilder, plugin::Plugin, async_trait, Result};
use fusions::db::TypedDbPlugin;

// 应用 crate 自己定义：
// - AppContext: fusions::sql::ModelContext
// - AppModelManager = fusions::sql::ModelManager<AppContext>
use crate::{AppContext, AppModelManager};

pub struct MyPlugin {
    config: MyConfig,
}

#[async_trait]
impl Plugin for MyPlugin {
    fn name(&self) -> &str {
        "my_plugin"
    }

    fn dependencies(&self) -> Vec<&str> {
        vec![std::any::type_name::<TypedDbPlugin<AppContext>>()]  // 确保 typed DB 先加载
    }

    fn immediately(&self) -> bool {
        false  // 异步构建
    }

    fn immediately_build(&self, app: &mut ApplicationBuilder) {
        // 同步阶段：添加配置源
        app.add_config_source(File::from_str(CONFIG, FileFormat::Toml));
    }

    async fn build(&self, app: &mut ApplicationBuilder) {
        // 异步阶段：获取配置和组件（注册的应是长期单例，例如 client 池/调度器，
        // 而不是请求级 application service——后者由 handler 内 inline 构造）
        let config: MyConfig = app.get_config()?;
        let mm: AppModelManager = app.component();

        // 创建并注册组件（示例：HTTP/RPC client 池）
        let clients = MyClientPool::new(mm, config);
        app.add_component(clients);
    }
}

#[tokio::main]
async fn main() -> fusions::Result<()> {
    // fusions::Result = Result<(), DataError>
    // Application::run() 返回 fusion_core::Result = Result<_, CoreError>
    // 通过 fusions::error 中的 From<CoreError> for DataError 自动转换
    let app = Application::builder()
        .add_config_source(File::from_str(DEFAULT_CONFIG, FileFormat::Toml))
        .add_plugin(TypedDbPlugin::new(AppContext::system))
        .add_plugin(MyPlugin::default())
        .run()
        .await?;

    // 获取组件
    let clients: MyClientPool = app.component();

    // 全局单例
    let global: &Application = Application::global();

    // 等待关闭信号
    Application::await_shutdown().await;
    Ok(())
}
```

### 构建流程

```
ApplicationBuilder::new()
  → add_plugin() x N
  → build() / run()
    → build_plugins()           # 拓扑排序 + 依赖检测（循环检测）
    → auto_inject_component()   # inventory 收集 → 按依赖分轮解析（最多 10 轮）
    → build_application()       # 设置全局单例 (OnceLock)
    → set_global()
```

### 信号处理

```rust
// 获取 shutdown receiver（返回 Option：shutdown pair 已被取走时为 None）
let shutdown_rx = app.shutdown_recv().await.expect("shutdown pair already taken");

// 在服务器中使用（serve() 阻塞跑服务循环直到关机；旧名 build() 已 deprecated）
WebServerBuilder::new(router)
    .with_shutdown(shutdown_rx)
    .serve()
    .await?;

// 手动触发关闭
Application::shutdown().await;

// 等待关闭完成
let closed = Application::await_shutdown().await;
```

### Shutdown hooks

`ApplicationBuilder::add_shutdown_hook` 注册的钩子在 `Application::await_shutdown`
内、关机信号被所有子系统处理完之后按**注册顺序**执行；单个钩子失败记日志、不阻断
其余钩子。进程不调用 `await_shutdown` 则钩子不会执行。

```rust
Application::builder()
    .add_shutdown_hook(|app| Box::new(async move {
        // flush 缓冲 / 关闭池 / 注销服务发现
        Ok("flush-metrics".to_string())
    }))
    .run()
    .await?;
```

## Component 依赖注入

> ⚠️ **适用范围**：`Component` 仅用于长期持有的有状态单例（连接池、RPC client 池、消息队列、调度器、`ModelManager` base 等）。**需要承载请求级上下文的 application service 不应 derive `Component`**——见下文 §「Application service：不使用 Component」。

### 使用 derive 宏（仅限长期单例）

```rust
use fusions_core_macros::Component;
use crate::AppModelManager;

// ✅ 例子：网关 RPC client 池——进程级单例，无 per-request ctx
#[derive(Clone, Component)]
pub struct GatewayClients {
    #[component]                      // 自动从 Application 组件注册表注入
    mm: AppModelManager,              // base mm，仅用于 client 初始化

    #[config]                         // 自动从配置系统注入（实现 Configurable 的类型）
    config: Arc<GatewayConfig>,

    http_client: reqwest::Client,     // 非注入字段，使用 Default::default()
}
```

> `#[derive(Component)]` 自动生成 `ComponentInstaller` 并通过 `inventory::submit!` 提交，无需手动注册。

### ComponentArc / ConfigArc

```rust
#[derive(Clone, Component)]
pub struct MyInfraSingleton {
    #[component]               // typed ModelManager 直接注入
    mm: AppModelManager,

    // 如需 Arc 引用：
    // other: ComponentArc<OtherSingleton>,  // app.try_component_arc::<T>()
    // config: ConfigArc<MyConfig>,           // 配置包装注入
}
```

> 生成代码默认引用 `::fusions::core`（伞 crate）。只直依 `fusion-core` 而不带
> `fusions` 的消费方，在 derive 项上加 `#[fusions(crate = "::fusion_core")]` 覆盖
> 生成路径（`Component` / `Configuration` 两个 derive 都支持）。

### Application service：不使用 Component

业务 service 一律改用「持有 mm 的轻量结构体 + `pub fn new(mm)` + handler 内 inline 构造」：

```rust
#[derive(Clone)]
pub struct UserService {
    mm: AppModelManager,
}

impl UserService {
    pub fn new(mm: AppModelManager) -> Self { Self { mm } }
    pub async fn get(&self, id: Id) -> Result<User, DataError> { /* ... */ }
}
```

handler 通过 Tower 中间件注入的请求级 mm 取用：

```rust
async fn get_user(ctx: Context, req: ...) -> Result<(User, Context), ConnectError> {
    let svc = UserService::new(mm_from_ctx(&ctx)?.clone());
    let user = svc.get(req.id).await?;
    Ok((user, ctx))
}
```

理由：
- service 持有 ctx-scoped mm，启动期注入的 base mm 不带认证上下文，会让 RLS / `SET LOCAL` session vars 失效。
- 单 `Application::global()` 单例无法承载 per-request ctx；在 handler 入口注入是唯一干净的方式。
- mm 内部是 `Arc`，每请求 `clone() + new(...)` 等价于 `Arc::clone`，零开销。

### 手动注册组件（适用于长期单例）

```rust
use fusions::core::component::{ComponentInstaller, submit};

pub struct GatewayClientsInstaller;

impl ComponentInstaller for GatewayClientsInstaller {
    fn dependencies(&self) -> Vec<&str> { vec![] }
    fn install_component(&self, app: &mut ApplicationBuilder) -> Result<()> {
        let mm: AppModelManager = app.try_component()?;
        let clients = GatewayClients::new(mm);
        app.add_component(clients);
        Ok(())
    }
}

submit! {
    &GatewayClientsInstaller as &dyn ComponentInstaller
}
```

### 获取组件（仅基础设施单例）

命名约定：panic 版短名（`component` / `component_arc`，`#[track_caller]`，用于启动期装配
——缺组件即编程错误）+ fallible 版 `try_` 前缀（`try_component` / `try_component_arc` /
`try_component_arc_by_name`）。旧 `get_component*` 名已 `#[deprecated]`。

```rust
// 在 Plugin 中
let clients: GatewayClients = app.component();      // panic on missing

// 在 Application 中
let clients: GatewayClients = app.component();

// 安全获取
let clients: ComponentResult<GatewayClients> = app.try_component();

// Arc 引用（panic 版：component_arc）
let service: ComponentResult<ComponentArc<MySingleton>> = app.try_component_arc();
```

## Configuration 配置系统

### 使用 derive 宏

```rust
use fusions_core_macros::Configuration;

#[derive(Clone, Serialize, Deserialize, Configuration)]
#[config_prefix = "myapp.database"]
pub struct DatabaseConfig {
    pub url: String,
    pub max_connections: u32,
    #[serde(default = "default_idle_timeout")]
    pub idle_timeout: Duration,
}
```

### 手动实现 Configurable

```rust
use fusions::core::configuration::Configurable;

impl Configurable for DatabaseConfig {
    fn config_prefix() -> &'static str {
        "myapp.database"
    }
}
```

### 配置源

```rust
use fusions::core::configuration::{File, FileFormat};

// TOML 文件（panic 版；fallible 版为 try_add_config_source / try_prepend_config_source）
app.add_config_source(File::from_path("config.toml", FileFormat::Toml)?);

// 嵌入式配置（推荐：include_str! 搭配 default.toml）
app.add_config_source(File::from_str(DEFAULT_CONFIG, FileFormat::Toml));

// 环境变量（自动支持）
// MYAPP__DATABASE__URL=postgres://...
```

### 获取配置

```rust
// 使用 config_prefix
let config: DatabaseConfig = app.get_config()?;

// 指定路径
let config: DatabaseConfig = app.get_config_by_path("myapp.database")?;

// 内置配置
let settings: FusionSetting = app.fusion_setting();
let security: &SecuritySetting = settings.security();
```

### FusionSetting

```rust
pub struct FusionSetting {
    pub app: AppSetting,       // run_mode, name, time_offset
    pub security: SecuritySetting,  // 密钥配置（ZeroizeOnDrop 保护）
    pub log: LogSetting,
}

pub struct SecuritySetting {
    pub pwd: PwdConf,          // secret_key, expires_in, default_pwd
    pub token: TokenConf,      // secret_key, public_key, private_key (ZeroizeOnDrop)
}
```

### 配置格式 (TOML)

```toml
[myapp.database]
url = "postgresql://user:pass@localhost:5432/mydb"
max_connections = 10
idle_timeout = "10s"

[fusion.web]
enable = true
server_addr = "0.0.0.0:9500"

[fusion.rpc]
enable = false
path_prefix = "/"
```

## Plugin 插件系统

### Plugin Trait

```rust
#[async_trait]
pub trait Plugin: Any + Send + Sync {
    fn name(&self) -> &str { std::any::type_name::<Self>() }
    fn dependencies(&self) -> Vec<&str> { vec![] }
    fn immediately(&self) -> bool { false }
    fn immediately_build(&self, _app: &mut ApplicationBuilder) {}
    async fn build(&self, _app: &mut ApplicationBuilder) {}
}
```

### 插件顺序

```rust
// 依赖会自动拓扑排序，循环依赖会 panic
Application::builder()
    .add_plugin(MyPlugin)      // 声明依赖 TypedDbPlugin<AppContext>
    .add_plugin(TypedDbPlugin::new(AppContext::system))
    .run()
    .await?;
```

### 内置 Plugin

| Plugin     | Crate      | 功能                           |
| ---------- | ---------- | ------------------------------ |
| `TypedDbPlugin<C>` | fusion-db  | 初始化 `ModelManager<C>`，注册 typed 组件 |
| `DbPlugin` | fusion-db  | 初始化默认 `ModelManager<Ctx>`，用于兼容路径 |
| `RpcPlugin`| fusion-rpc | 添加 RPC 默认配置源            |

## CoreError —— fusion-core 自有错误

```rust
use fusions::core::error::{CoreError, CoreResult};

#[derive(Debug, thiserror::Error)]
pub enum CoreError {
    Component(#[from] ComponentError),
    Configure(#[from] ConfigureError),
    Security(#[from] fusion_core::security::Error),
    Io(#[from] std::io::Error),
    TaskJoin(#[from] tokio::task::JoinError),
    Tracing(String),
    Timer(String),
    Custom(String),
}

// 便捷构造
CoreError::custom("init failed")
CoreError::tracing("subscriber init failed")
CoreError::timer("shutdown failed")
```

`fusion_core::Result<T> = Result<T, CoreError>`。`Component::build`、`ComponentInstaller::install_component`、
`Plugin::immediately_build`、`Application::run/build` 等公开 API 全部以 `CoreError` 为错误类型。

> ⚠️ 写 `Component::build` 时，错误必须构造 `CoreError`（不要 `DataError::internal(...)?`，那是反方向）。
> 例：`Self::from_addrs(&addrs).map_err(|e| fusions::core::CoreError::custom(format!("init: {e}")))`

## DataError 错误处理

> `DataError` 定义在 `fusions::error`（**不在** `fusion-common`）。各 fusion-xxx Error → DataError 的 From 实现集中在 fusions。

```rust
use fusions::DataError;
use fusions::Result;             // Result<T> = Result<T, DataError>

// HTTP 对应
DataError::bad_request("Invalid input")      // 400
DataError::unauthorized("Token expired")     // 401
DataError::forbidden("Access denied")        // 403
DataError::not_found("User not found")       // 404
DataError::conflicted("Resource exists")     // 409
DataError::server_error("Internal error")    // 500

DataError::not_implemented("Not implemented") // 501 → system.not_implemented（永久失败，勿映射 503）
DataError::failed_precondition("Not ready")  // FailedPrecondition → validation.failed_precondition

// 应用错误（code 为字符串，遵循 namespace.error_name 规范）
DataError::biz_error("quota.exceeded", "Quota exceeded", Some(json!({"limit": 100})))

// 限流
DataError::retry_limit("Too many attempts", 5)

// 通用
DataError::internal(code, message, source)
```

### 错误码命名空间

| 命名空间          | 用途         |
| ----------------- | ------------ |
| `validation.*`    | 输入校验     |
| `auth.*`          | 认证授权     |
| `resource.*`      | 资源操作     |
| `system.*`        | 系统错误     |
| `rate_limit.*`    | 限流         |
| `channel.*`       | 通道错误     |
| `rpc.*`           | RPC 错误     |

### 跨 crate 错误自动转换（全部在 `fusions::error`）

```rust
// fusion-common
// fusion_common::Error              → DataError
// fusion_common::ctx::CtxError      → DataError

// fusion-core
// fusion_core::CoreError            → DataError
// fusion_core::ComponentError       → DataError
// fusion_core::ConfigureError       → DataError
// fusion_core::security::Error      → DataError

// 第三方（始终启用）
// std::io::Error / SystemTimeError / AddrParseError / serde_json::Error
// chrono::ParseError / uuid::Error
// tokio::sync::mpsc/oneshot/task::JoinError
// mea::mpsc::SendError / config::ConfigError

// feature gated
// connectrpc::ConnectError ↔ DataError      (feature = "rpc")
// fusionsql::SqlError                → DataError (feature = "db")
// fusionsql::store::DbxError         → DataError (feature = "db")
// sqlx::Error                        → DataError (feature = "db")
// fusion_web::WebError ↔ DataError           (feature = "web")
// fusion_security::SecurityError     → DataError (feature = "security")
// fusion_ai::AiError                 → DataError (feature = "ai")
```

## Best Practices

1. **Plugin 顺序**: 使用 `dependencies()` 声明依赖，确保加载顺序正确
2. **Component 注入**: 使用 `#[derive(Component)]` 简化依赖注入，用 `#[config]` 注入配置
3. **配置分层**: TOML 默认配置 (include_str!) + 环境变量覆盖
4. **错误转换**: 为自定义错误实现 `From<DataError>` 以使用 `?`
5. **优雅关闭**: 使用 `shutdown_recv()` 实现优雅关闭

## Examples from Codebase

- `crates/fusion-core/src/application.rs` - Application 实现
- `crates/fusion-core/src/component/mod.rs` - Component 系统
- `crates/fusion-db/src/lib.rs` - DbPlugin / TypedDbPlugin 示例
- `crates/fusion-rpc/src/lib.rs` - RpcPlugin 示例
