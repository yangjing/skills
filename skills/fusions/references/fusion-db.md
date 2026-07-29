# fusion-db

数据库抽象层：typed `ModelManager<C>`、`TypedDbPlugin<C>`、默认 `DbPlugin`、PostgreSQL/SQLite 支持。

## Imports

```rust
use fusions::db::{DbPlugin, TypedDbPlugin};
use fusions::sql::{DbConfig, ModelContext, ModelManager, id::Id};
use fusions::sql::store::{Dbx, create_dbx};
```

## TypedDbPlugin

### 在 Application 中使用

```rust
use fusions::common::time::{OffsetDateTime, now_offset};
use fusions::core::{Application, plugin::Plugin};
use fusions::db::TypedDbPlugin;
use fusions::sql::{ModelContext, ModelManager, id::Id};

#[derive(Clone)]
pub struct AppContext {
    audit_actor_id: Id,
    req_time: OffsetDateTime,
}

impl AppContext {
    pub fn system() -> Self {
        Self { audit_actor_id: Id::I64(0), req_time: now_offset() }
    }
}

impl ModelContext for AppContext {
    fn audit_user_id(&self) -> Id { self.audit_actor_id.clone() }
    fn req_time(&self) -> OffsetDateTime { self.req_time.to_owned() }
}

type AppModelManager = ModelManager<AppContext>;

#[tokio::main]
async fn main() -> fusions::core::Result<()> {
    let app = Application::builder()
        .add_plugin(TypedDbPlugin::new(AppContext::system))
        .run()
        .await?;

    let mm: AppModelManager = app.component();
    Ok(())
}
```

> `TypedDbPlugin<C>` 在 `build()` 中：加载 `fusion.db` 配置 → 创建 `fusionsql::ModelManager<C>` → 用 `ctx_factory` 设置初始 context → 注册为 Application 组件。`C` 只需要实现 `ModelContext`，fusions 不知道应用字段。

### 默认 DbPlugin

```rust
use fusions::db::{DbPlugin, ModelManager};

let app = Application::builder()
    .add_plugin(DbPlugin)
    .run()
    .await?;

let mm: ModelManager = app.component(); // ModelManager<fusion_common::ctx::Ctx>
```

> `DbPlugin` 是兼容路径：它注册 `fusions::db::ModelManager`，即 `fusionsql::DefaultModelManager = ModelManager<fusion_common::ctx::Ctx>`。新服务若有自己的请求/审计上下文，应使用 `TypedDbPlugin<C>` 和应用 crate 内的类型别名。

### 配置 (TOML)

```toml
[fusion.db]
enable = true
url = "postgresql://user:pass@localhost:5432/mydb"
max_connections = 10
idle_timeout = "10s"
acquire_timeout = "5s"
schema_search_path = "my_schema"
application_name = "my_app"
```

## DbConfig

`DbConfig` 字段对外只读，通常由 config 系统从 `fusion.db` 加载；手动创建连接时从配置注册表读取 `DbConfig` 后传给 `ModelManager::<C>::new()` 或 `create_dbx()`。

## ModelManager

### 创建

```rust
// 从 Application 获取（推荐）
let mm: AppModelManager = app.component();

// 从配置创建
let mm = ModelManager::<AppContext>::new(&db_config, Some("my_app"))
    .await?
    .with_ctx(AppContext::system());
```

### 设置上下文

```rust
let mm = mm.with_ctx(request_context);  // 上下文自动传递给 BMC 操作
```

### 过滤器拦截器

```rust
let mm = mm.with_filter_interceptor(|bmc_config, ctx, filters| {
    if bmc_config.has_owner_id {
        // 读取应用自定义 ctx，按应用规则补充 owner/scope 过滤条件
    }
    Ok(filters)
});
```

### 事务 API

```rust
// 推荐：闭包式事务（自动 commit/rollback，支持 SAVEPOINT 嵌套）
mm.transaction(|mm| async move {
    UserBmc::create(&mm, user).await?;
    // 嵌套事务使用 SAVEPOINT
    mm.transaction(|mm| async move {
        ProfileBmc::create(&mm, profile).await?;
        Ok::<_, DataError>(())
    }).await?;
    Ok(())
}).await?;

// 只读事务：顶层 Postgres 发 SET TRANSACTION READ ONLY，嵌套时走 SAVEPOINT
mm.read_transaction(|mm| async move {
    let user = UserBmc::get_by_id(&mm, id).await?;
    Ok(user)
}).await?;

// 手动事务
let mm_txn = mm.txn_cloned();
mm_txn.dbx().begin_txn().await?;
UserBmc::create(&mm_txn, user).await?;
mm_txn.dbx().commit_txn().await?;
```

### 获取底层连接

```rust
let dbx = mm.dbx();   // Dbx 抽象
```

## Dbx 抽象

```rust
use fusionsql::store::{Dbx, DbxPostgres, DbxSqlite, create_dbx};

pub enum Dbx {
    Postgres(DbxPostgres),
    Sqlite(DbxSqlite),
}

pub enum DbxProvider { Postgres, Sqlite }

let dbx = create_dbx(&db_config, Some("my_app")).await?;
```

## DbxPostgres 手动事务

> 当闭包式事务不适用时（如跨模块调用、需在 application 层控制事务边界），使用 `DbxPostgres` 手动事务。

### API

```rust
use fusions::sql::store::DbxPostgres;

let dbx = mm.dbx().db_postgres().map_err(map_db_error)?;
dbx.begin_txn().await.map_err(map_db_error)?;
// 读路径可用 dbx.begin_txn_read_only().await?，顶层事务会 SET TRANSACTION READ ONLY。
// ... dbx.execute() / dbx.fetch_one() / dbx.fetch_optional() / dbx.fetch_all() / dbx.fetch_one_scalar() / dbx.fetch_optional_scalar() ...
dbx.commit_txn().await.map_err(map_db_error)?;
// 或回滚：
dbx.rollback_txn().await.map_err(map_db_error)?;
```

### 规则（强制）

1. **禁止** `dbx.db().begin()` 或 `pool.begin()` 创建 `sqlx::Transaction`
2. 事务内查询必须通过 `dbx.execute()` / `dbx.fetch_one()` / `dbx.fetch_optional()` / `dbx.fetch_all()` / `dbx.fetch_one_scalar()` / `dbx.fetch_optional_scalar()`，**禁止** `&mut *tx` 模式
3. 跨模块事务函数签名统一为 `dbx: &fusions::sql::store::DbxPostgres`（不要用 `&mut sqlx::Transaction`）
4. `dbx.execute()` 返回 `u64`（受影响行数），不是 `PgQueryResult`——**不要** `.rows_affected()`
5. 事务生命周期 `begin_txn()` → 操作 → `commit_txn()` / `rollback_txn()` 必须在同一个 `DbxPostgres` 实例上

### 正反示例

```rust
// ✅ 正确：DbxPostgres 手动事务
// `DbxError` → `DataError` 的 From 实现在 fusions::error（feature = "db"），可直接用 ?
use fusions::DataError;
use fusions::sql::store::DbxError;

let dbx = mm.dbx().db_postgres()?;          // DbxError → DataError
dbx.begin_txn().await?;
dbx.execute(sqlx::query("INSERT INTO ...").bind(val)).await?;
dbx.commit_txn().await?;

// ❌ 禁止：裸 sqlx::Transaction
let mut tx = dbx.db().begin().await?;  // 禁止
sqlx::query("INSERT INTO ...").execute(&mut *tx).await?;  // 禁止
tx.commit().await?;

// ❌ 禁止：对 dbx.execute() 结果调 .rows_affected()
let affected = dbx.execute(sqlx::query("DELETE ...")).await?;
if affected.rows_affected() == 0 { ... }  // 编译错误：affected 是 u64
// ✅ 正确：
if affected == 0 { ... }
```

### 跨模块函数签名

```rust
// ✅ 正确：接受 &DbxPostgres
pub async fn create_with_dbx(dbx: &fusions::sql::store::DbxPostgres, data: &CreateData) -> Result<()> {
    dbx.execute(sqlx::query("INSERT ...").bind(&data.name)).await?;
    Ok(())
}

// ❌ 禁止：接受 &mut Transaction
pub async fn create_with_tx(tx: &mut sqlx::Transaction<'_, sqlx::Postgres>, data: &CreateData) -> Result<()> { ... }
```

## Best Practices

1. **优先使用 TypedDbPlugin**: 应用定义 `AppContext: ModelContext`，并注册 `TypedDbPlugin::new(AppContext::system)`
2. **保持框架无应用语义**: fusions 只要求 `audit_user_id()` 和 `req_time()`；应用字段、header、claim、scope 规则放在应用 crate
3. **传递 typed context**: 每个请求或后台任务使用 `mm.with_ctx(ctx)` 设置当前 `AppContext`
4. **事务优先闭包式**: 使用 `mm.transaction()` / `mm.read_transaction()` 自动管理提交/回滚，支持 SAVEPOINT 嵌套
5. **手动事务守规则**: 需要手动事务时，严格遵守 [DbxPostgres 手动事务](#dbxpostgres-手动事务) 规则
6. **作用域过滤**: 使用 `with_filter_interceptor` 按应用规则补充 owner/scope 过滤，不在 fusions 写应用规则
7. **连接池**: 合理配置 `max_connections` 和 `idle_timeout`

## Examples from Codebase

- `crates/fusion-db/src/lib.rs` - DbPlugin / TypedDbPlugin 实现
- `crates/fusionsql/src/model_manager.rs` - ModelManager 实现
