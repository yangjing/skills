# fusion-sql

SQL 层：`ModelManager<C>` 类型化上下文、`Dbx` 连接/事务封装、`SqlError`。
**不是 ORM** —— v0.3 起没有查询构造器、没有实体宏、没有 BMC，SQL 由应用侧用 sqlx 写。

## ⚠️ v0.3 破坏性变更（从 v0.2 迁移必读）

crate 改名，且整个 sea-query 栈被删除（commit `bbe2bbb`）：

| v0.2                                  | v0.3                                        |
| ------------------------------------- | ------------------------------------------- |
| crate `fusionsql`                     | crate `fusion-sql`（`use fusion_sql::…`）   |
| crate `fusionsql-core`                | crate `fusion-sql-core`                     |
| crate `fusionsql-macros`              | **已删除**（无替代）                        |
| `fusionsql::sea_query` re-export      | **已删除**（sea-query / sea-query-binder / pgvector 依赖整体移除） |
| `#[derive(Fields)]` / `#[fusionsql(table = …)]` | **已删除** → 用 `#[derive(sqlx::FromRow)]` |
| `#[derive(FilterNodes)]` / `OpVal*` / `FilterGroups` | **已删除** → 应用侧手写 `WHERE` + `bind` |
| `#[derive(SeaFieldValue)]` / `SeaFields` / `HasSeaFields` / `FieldMask` | **已删除** |
| `DbBmc` / `BmcConfig` / `fusionsql::base::*` CRUD / `generate_pg_bmc_*!` | **已删除** → repo 函数直接持 `DbxPostgres` |
| `fusionsql::page::{Page, Paged, PageResult, OrderBys}` | **已删除** → 分页 DTO 由应用 / proto 契约定义 |
| `mm.with_filter_interceptor(…)`       | **已删除** → scope 过滤靠 RLS session vars 或显式 SQL 条件 |
| `SqlError::{IntoSeaError, SeaQueryError}` | **已删除**                              |
| `fusion-common` 的 `SensitiveString` impl `sea_query::Value` / `Nullable` | **已删除** |
| `fusion-core` feature `fusionsql`     | **已删除**（此前已无用）                    |

`fusions::sql`（aggregate 的 `db` feature）仍是这一层的入口，现指向 `fusion-sql`。

**随之消失的安全默认**：v0.2 里客户端 `order_bys` 由 BMC 按实体列集合自动校验。
v0.3 没有任何框架层校验 —— 凡是把客户端字符串拼进 `ORDER BY` 的地方，应用 MUST
自己维护列白名单（sqlx 不能 `bind` 标识符），否则就是 ORDER BY 注入 / schema 探测面。

## 依赖关系

```
fusion-sql-core  (类型: Id)
fusion-sql       (运行时: ModelManager<C>, ModelContext, Dbx, DbxPostgres, DbConfig, SqlError)
```

## Imports

```rust
use fusion_sql::{DbConfig, ModelContext, ModelManager, DefaultModelManager, SqlError};
use fusion_sql::store::{Dbx, DbxPostgres, DbxSqlite, DbxError, create_dbx};  // store 只导出这几个
use fusion_sql::id::Id;
use fusion_sql::common::{now_offset, UriString};

// 应用侧一般经 aggregate 引入，保持 feature 一致：
use fusions::sql::{ModelContext, ModelManager, store::DbxPostgres, id::Id};
```

Features：`with-postgres`（default）、`with-sqlite`、`with-uuid`（开启后
`Id::Uuid` 变体存在；`#[serde(untagged)]` 下 `Uuid` 声明在 `String` 之前，
合法 UUID 字符串优先解析为 `Id::Uuid`）。

## Typed ModelManager

`ModelManager<C: ModelContext = Ctx>`。框架只要求 context 提供审计操作者与请求时间；
应用字段（tenant / scope / claims）与访问规则由应用 crate 自定义。

```rust
use fusion_sql::{ModelContext, ModelManager, id::Id, common::now_offset};
use chrono::{DateTime, FixedOffset};

#[derive(Clone)]
pub struct AppContext {
    audit_actor_id: Id,
    req_time: DateTime<FixedOffset>,
}

impl ModelContext for AppContext {
    fn audit_user_id(&self) -> Id { self.audit_actor_id.clone() }
    fn req_time(&self) -> DateTime<FixedOffset> { self.req_time.to_owned() }

    // 可选：每事务发的 `SET LOCAL`（RLS GUC 等）。key 是 &'static str。
    fn db_session_vars(&self) -> Vec<(&'static str, String)> { vec![] }
}

pub type AppModelManager = ModelManager<AppContext>;
```

默认 `DefaultModelManager = ModelManager<fusion_common::ctx::Ctx>`，仅在确实使用默认
`Ctx` 时采用。

> ⚠️ 兼容 impl 的 0 哨兵：`Ctx` 无 user id 时 `audit_user_id()` 返回 `0`，审计列以
> user 0 落库表示「system / 未归因」。依赖精确归因的应用 MUST 自定义 `AppContext`
> 并把 audit actor 设为必填字段。
>
> `ModelManager` 有手写 `Debug`（只打印 provider / is_txn / ctx 类型名），下游可放心
> `#[derive(Debug)]` 包装。

主要方法：

| 方法                       | 说明                                                    |
| -------------------------- | ------------------------------------------------------- |
| `new(&DbConfig, app_name)` | 建池                                                    |
| `with_ctx(ctx)`            | 附加 context，**并把 `db_session_vars()` 挂到 dbx 上**   |
| `dbx()`                    | `&Dbx` —— 数据访问入口                                  |
| `ctx_ref()`                | `Result<&C>`，未 `with_ctx` 时 `SqlError::CtxMissing`    |
| `txn_cloned()`             | 强制开新事务克隆                                        |
| `get_txn_clone()`          | 已在事务内则克隆自身，否则新事务                        |
| `transaction(f)` / `read_transaction(f)` | 闭包式事务（见下）                        |

## 数据访问 —— `DbxPostgres` + sqlx

没有 BMC 了：repo 层直接持 `DbxPostgres`，SQL 手写，参数一律 `bind`。

```rust
use fusions::sql::store::DbxPostgres;

#[derive(sqlx::FromRow)]
pub struct UserRow {
    pub id: i64,
    pub name: String,
    pub created_at: chrono::DateTime<chrono::FixedOffset>,
}

pub async fn find_by_id(dbx: &DbxPostgres, id: i64) -> Result<Option<UserRow>, SqlError> {
    let row = dbx
        .fetch_optional(
            sqlx::query_as::<_, UserRow>("SELECT id, name, created_at FROM users WHERE id = $1").bind(id),
        )
        .await?;
    Ok(row)
}

pub async fn rename(dbx: &DbxPostgres, id: i64, name: &str) -> Result<u64, SqlError> {
    // execute 返回 u64（rows affected），不是 PgQueryResult ——
    // 对返回值调 .rows_affected() 是编译错误。
    let n = dbx
        .execute(sqlx::query("UPDATE users SET name = $2 WHERE id = $1").bind(id).bind(name))
        .await?;
    Ok(n)
}
```

| 方法                                                    | 返回                                          |
| ------------------------------------------------------- | --------------------------------------------- |
| `fetch_one` / `fetch_optional` / `fetch_all`（收 `query_as`） | `O` / `Option<O>` / `Vec<O>`             |
| `fetch_one_scalar` / `fetch_optional_scalar` / `fetch_all_scalar`（收 `query_scalar`） | 标量        |
| `execute`（收 `query`）                                 | `u64` 行数                                    |
| `db()`                                                  | `&PgPool` —— **绕过事务与 session vars**，仅限迁移 / 建库等无租户语境 |

审计列（`created_by` / `updated_at` …）在 v0.3 没有框架自动填充：SQL 里显式写，
值取自 `mm.ctx_ref()?.audit_user_id()` / `req_time()`。

## 事务

`SET LOCAL` 是事务作用域的。只要 `db_session_vars()` 非空（RLS），**读和写都必须在事务里** ——
裸 `dbx.fetch_*` 从池里临时借连接、没有 session vars，FORCE RLS 表按 fallback policy
返回空集，未启用 RLS 的表则跨租户泄漏。`DbxPostgres` 内建
`assert_no_orphan_session_vars()` 在非事务路径上带着 session vars 时会告警。

```rust
// 闭包式（推荐）：自动 commit / rollback，嵌套自动降为 SAVEPOINT
mm.transaction(|mm| async move {
    let dbx = mm.dbx().db_postgres()?;
    dbx.execute(sqlx::query("INSERT INTO users(name) VALUES ($1)").bind(name)).await?;
    Ok(())
}).await?;

// 只读事务：顶层发 SET TRANSACTION READ ONLY，闭包内任何写被 PG 拒绝
mm.read_transaction(|mm| async move { /* … */ }).await?;

// 手动式
let mm_txn = mm.get_txn_clone();
let dbx = mm_txn.dbx().db_postgres()?;
dbx.begin_txn().await?;
dbx.execute(sqlx::query("UPDATE …").bind(x)).await?;
dbx.commit_txn().await?;
```

> ⚠️ `ModelManager::transaction` / `read_transaction` **只做 `BEGIN; …; COMMIT;`，
> 不注入 session vars**。RLS 应用必须用叠加了 `set_config(...)` 的应用层 helper
> （本仓即 `hylx_core::db::with_read_txn` / `with_write_txn` / `with_*_txn_pg`），
> 直接用框架方法跑 RLS 表 = 跨租户读放大。

嵌套 `read_transaction` 不会把外层写事务降级为只读（SAVEPOINT 继承外层读写模式）。

## 分页与过滤（应用侧责任）

`Page` / `PageResult` / `OpVal*` 都没了。做法：分页 DTO 由 proto 契约定义，repo 层接受
已校验的参数，SQL 里写 `LIMIT $n OFFSET $m` 或游标条件；排序字段先经应用侧白名单
映射成静态列名再拼进 `ORDER BY`。

## 错误

```rust
pub enum SqlError {
    Unauthorized(String),
    CtxMissing,                       // 未 with_ctx 就做上下文相关操作 → 装配缺陷（500，非 401）
    ExecuteError { table, message },
    ExecuteFail { schema, table },
    CountFail { schema, table },
    InvalidDatabase(&'static str),
    InvalidArgument { message },
    EntityNotFound { schema, entity, id },
    NotFound { schema, table, sql },
    ListLimitOverMax { max, actual },
    ListLimitUnderMin { min, actual },
    ListPageUnderMin { min, actual },
    UserAlreadyExists { key, value },
    UniqueViolation { table, constraint },
    CantCreateModelManagerProvider(String),
    Custom(String),
    JsonError(#[from] serde_json::Error),
    DbxError(#[from] DbxError),
    Sqlx(#[from] sqlx::Error),
}
```

`SqlError::resolve_unique_violation(resolver)` 把 PG `23505` 提升为
`UniqueViolation { table, constraint }`（可传 resolver 定制成更具体的业务错误）。

`SqlError` / `DbxError` / `sqlx::Error` → `DataError` 的转换全在 **`fusions::error`**
（feature = `db`）；`DbxError` 优先按 SQLSTATE 精确匹配（23505 → conflicted、
23503 → bad_request、其余 → server_error）。service / repo 层用 `?` 即可。

## 推荐文件布局（应用层约定，非框架强制）

| 文件                 | 内容                                   |
| -------------------- | -------------------------------------- |
| `{entity}_entity.rs` | `sqlx::FromRow` 行结构                 |
| `{entity}_model.rs`  | 请求 / 响应 DTO、查询参数              |
| `{entity}_repo.rs`   | 持 `DbxPostgres` 的 SQL 函数           |
| `{entity}_svc.rs`    | 业务编排（事务、跨模块调用、领域规则） |

## Code locations

- `crates/fusion-sql/src/model_manager.rs` — `ModelManager` / `ModelContext`
- `crates/fusion-sql/src/store/dbx/dbx_postgres.rs` — `DbxPostgres`、事务与 session vars
- `crates/fusion-sql/src/error.rs` — `SqlError`
- `crates/fusion-sql-core/src/id.rs` — `Id`
