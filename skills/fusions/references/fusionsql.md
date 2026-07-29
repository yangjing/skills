# fusionsql

SQL/ORM 层：Entity 定义、Fields 宏、FilterNodes、BMC 模式、分页、事务。

## 依赖关系

```
fusionsql-macros (proc-macro: Fields, FilterNodes, SeaFieldValue)
fusionsql-core   (类型: FilterNode, OpVal*, Page, Paged, FieldMask, SIden)
fusionsql        (运行时: ModelManager<C>, ModelContext, Dbx, BmcConfig, DbBmc, CRUD fns, SeaFields)
```

> `fusionsql` 已 `pub use sea_query;`，派生宏生成代码走 `::fusionsql::sea_query::...`
> 绝对路径 —— 下游 crate 无需（也不应）自带一个名字叫 `sea_query` 的直接依赖。

## Imports

```rust
// 核心
use fusionsql::{DbConfig, ModelContext, ModelManager, Fields, FilterNodes};
use fusionsql::base::{self, DbBmc, BmcConfig};
use fusionsql::store::{Dbx, create_dbx};

// 字段和过滤
use fusionsql::field::{HasFields, HasSeaFields, SeaFields, SeaField, FieldMask, SeaFieldValue};
use fusionsql::filter::{FilterNode, FilterGroups, OpValString, OpValInt64, OpValDateTime};

// 分页
use fusionsql::page::{Page, Paged, PageResult, OrderBys, OrderBy};

// ID 类型
use fusionsql::id::Id;
```

## Typed ModelManager

`ModelManager` 是泛型类型：`ModelManager<C: ModelContext = Ctx>`。框架只要求 context 提供审计操作者和请求时间；应用字段和访问规则由应用 crate 自己定义。

```rust
use fusionsql::{ModelContext, ModelManager};
use chrono::{DateTime, FixedOffset};
use fusionsql::common::now_offset;
use fusionsql::id::Id;

type OffsetDateTime = DateTime<FixedOffset>;

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

pub type AppModelManager = ModelManager<AppContext>;
```

默认 `ModelManager` 等价于 `ModelManager<fusion_common::ctx::Ctx>`，即 `DefaultModelManager`；只有明确要使用默认 `Ctx` 时才采用。

> ⚠️ 兼容 impl 的 0 哨兵：`Ctx` 无 user id 时 `audit_user_id()` 返回 `0`，
> `created_by` / `updated_by` 以 user 0 落库表示「system / 未归因」。依赖精确
> 归因的应用 MUST 自定义 `AppContext` 并把 audit actor 设为必填字段。
>
> `ModelManager` / `Application` 均有手写 `Debug`（打印 provider / ctx 类型名 /
> 占位符，不 dump 连接与敏感上下文），下游可放心 `#[derive(Debug)]` 包装。

## Entity 定义

### 使用 Fields 宏

```rust
use fusionsql::Fields;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, Fields)]
#[fusionsql(table = "users", schema = "public")]
pub struct UserEntity {
    pub id: i64,
    pub owner_id: i64,
    pub name: String,
    pub description: String,
    pub updated_at: Option<OffsetDateTime>,
    pub logical_deletion: Option<OffsetDateTime>,
}
```

### Fields 宏生成内容

```rust
// HasFields: field_names(), field_metas(), field_refs()
// HasSeaFields: not_none_sea_fields(), all_sea_fields(), sea_idens(),
//               sea_column_refs(), sea_fields_with_mask()

// 部分更新使用 FieldMask
let user = UserForUpdate { email: Some("new@email.com"), ..Default::default() };
let fields = user.sea_fields_with_mask();  // 只包含非 None 字段
```

### SeaFieldValue 宏

```rust
use fusionsql::field::SeaFieldValue;

// 为简单类型实现 From<T> for sea_query::Value
#[derive(SeaFieldValue)]
pub struct MyType(String);
```

## Filters

### OpVal 操作符

```rust
// 字符串
OpValString::eq("value")           // =
OpValString::contains("sub")       // LIKE '%sub%'
OpValString::starts_with("pre")    // LIKE 'pre%'
OpValString::in_(vec!["a", "b"])   // IN

// 数值 (i64/f64)
OpValInt64::gt(100)                // >
OpValInt64 { gte: Some(0), lte: Some(100), ..Default::default() }

// 时间
OpValDateTime::gte(dt)
OpValDateTime::gte(start).with_lte(end)

// 布尔、数组、UUID、Value 等
```

### FilterNodes 宏

```rust
use fusionsql::FilterNodes;

#[derive(Debug, Default, Deserialize, FilterNodes)]
pub struct UserFilter {
    pub id: Option<OpValInt64>,
    pub username: Option<OpValString>,

    #[fusionsql(rel = "profile", cast_as = "uuid")]
    pub external_id: Option<OpValString>,
}

let filter = UserFilter { id: Some(OpValInt64::gt(100)), ..Default::default() };
let nodes: FilterGroups = filter.into();
```

### FilterGroups

```rust
// AND/OR 组合
let filters: FilterGroups = vec![
    vec![
        ("id", OpValInt64::gt(0)),
        ("status", "active"),
    ],
    vec![
        ("name", OpValString::contains("test")),
    ],
].into();
// SQL: (id > 0 AND status = 'active') OR (name LIKE '%test%')
```

## BMC 模式

### 定义 BMC

```rust
use std::sync::OnceLock;
use fusionsql::base::{DbBmc, BmcConfig};

pub struct UserBmc;

impl DbBmc for UserBmc {
    // 前导下划线 = protected 约定：实现方提供、仅供 base::* 框架函数读取，
    // 业务代码不要直接调用它做逻辑判断。
    fn _bmc_config() -> &'static BmcConfig {
        static CONFIG: OnceLock<BmcConfig> = OnceLock::new();
        CONFIG.get_or_init(|| {
            BmcConfig::new_table("users")
                .with_column_id("id")
                .with_id_generated_by_db(true)
                .with_audit_columns()
                .with_use_logical_deletion(true)
                .with_has_owner_id(true)           // owner/scope 字段
                .with_has_optimistic_lock(true)    // 乐观锁
                // 可选：显式覆盖排序名单（默认已按实体列集合校验，见下方「分页」）
                .with_order_by_allowlist(&["id", "created_at"])
        })
    }
}
```

### BmcConfig 选项

| 方法                      | 描述                     |
| ------------------------- | ------------------------ |
| `new(name, schema)`       | 表名 + 可选 schema       |
| `new_table(name)`         | 表名                     |
| `with_column_id(col)`     | 主键列名（默认 "id"）    |
| `with_id_generated_by_db` | ID 由数据库生成          |
| `with_audit_columns`      | 一键启用 created/updated 审计列 |
| `with_has_created_by/at`  | 审计字段                 |
| `with_has_updated_by/at`  | 审计字段                 |
| `with_use_logical_deletion` | 逻辑删除（soft delete） |
| `with_has_owner_id`       | owner/scope 字段         |
| `with_has_optimistic_lock` | 乐观锁                  |
| `with_order_bys`          | 服务端默认排序（受信配置，不经名单校验，可用 join / 计算列） |
| `with_order_by_allowlist` | 排序列**显式**白名单，覆盖实体列默认名单（收紧敏感列，或放开 join / 计算列） |

### CRUD 函数

```rust
use fusionsql::base;
use fusionsql::id::Id;

// 创建
base::create::<AppContext, UserBmc, _>(&mm, user).await?;

// 查询
base::pg_get_by_id::<AppContext, UserBmc, UserEntity>(&mm, Id::I64(id)).await?;

// 分页
base::pg_page::<AppContext, UserBmc, UserEntity, _>(&mm, filter, page).await?;

// 更新
base::update_by_id::<AppContext, UserBmc, _>(&mm, Id::I64(id), user_update).await?;

// 删除（逻辑删除或物理删除）
base::delete_by_id::<AppContext, UserBmc>(&mm, Id::I64(id)).await?;

// 批量
base::create_many::<AppContext, UserBmc, _>(&mm, vec![user1, user2]).await?;
base::delete_by_ids::<AppContext, UserBmc>(&mm, vec![Id::I64(1), Id::I64(2)]).await?;

// 计数
base::count::<AppContext, UserBmc, _>(&mm, filter).await?;
```

如果使用 `generate_pg_bmc_common!` / `generate_pg_bmc_filter!` 生成便捷方法，调用端不需要写出 context 泛型：

```rust
UserBmc::create(&mm, user).await?;
UserBmc::get_by_id(&mm, Id::I64(id)).await?;
UserBmc::page(&mm, filter, page).await?;
```

## 分页

```rust
use fusionsql::page::{Page, Paged, PageResult, OrderBys};

let page = Page::new_with_page(1, 20);
let page = Page { order_bys: Some(OrderBys::from(vec!["!created_at", "id"])), ..page };

let first_page = Page::new_with_limit(20);
let offset_page = Page::new_with_offset_limit(40, 20);
let all_rows = None::<Page>; // pg_find_many/sqlite_find_many 的无分页参数

// 结果：构造时显式给 has_more，避免 new() 默认 false 的「加载更多永不出现」陷阱
let result = PageResult::new_with_has_more(total, has_more, rows);
pub struct PageResult<T> {
    pub page: Paged,      // { total: u64, has_more: bool }
    pub result: Vec<T>,
}
```

### ORDER BY 列名校验（opt-out 安全默认）

客户端提交的 `Page.order_bys` 是不可信输入，分页 / 列表路径统一校验：

1. BMC 配了 `with_order_by_allowlist` → 按显式名单；
2. 否则按**实体列集合**（`HasFields::field_names()`）——最多只能按实体自身的列
   排序，非法列返回 `SqlError::InvalidArgument`（不触达数据库）。

服务端默认排序（`with_order_bys`）是受信配置，不经校验。防的是：按响应中不存在
的敏感列排序的 ORDER BY oracle、schema 探测、无索引隐藏列慢排序。

### wire 契约

`Page` / `Paged` / `PageResult` / `OrderBy(s)` 序列化统一 **camelCase**
（`orderBys` / `hasMore`）；`Page` 反序列化兼容旧 `order_bys`（serde alias）。

## 事务

```rust
// 闭包式事务（推荐，自动 commit/rollback，嵌套使用 SAVEPOINT）
mm.transaction(|mm| async move {
    UserBmc::create(&mm, user).await?;

    // 嵌套 = SAVEPOINT
    mm.transaction(|mm| async move {
        ProfileBmc::create(&mm, profile).await?;
        Ok(())
    }).await?;

    Ok(())
}).await?;

// 只读事务（顶层 Postgres 会 SET TRANSACTION READ ONLY）
mm.read_transaction(|mm| async move {
    let user = UserBmc::get_by_id(&mm, Id::I64(id)).await?;
    Ok(user)
}).await?;

// 手动事务
let mm_txn = mm.txn_cloned();
mm_txn.dbx().begin_txn().await?;
UserBmc::create(&mm_txn, user).await?;
mm_txn.dbx().commit_txn().await?;
```

## 作用域过滤

```rust
// 使用过滤器拦截器
let mm = mm.with_filter_interceptor(|bmc_config, ctx, filters| {
    if bmc_config.has_owner_id {
        // 按应用自定义 context 自动补充 owner/scope 过滤
    }
    Ok(filters)
});
```

## 错误处理

```rust
use fusionsql::SqlError;
use fusionsql::store::DbxError;
use sqlx::Error as SqlxError;

pub enum SqlError {
    Unauthorized(String),
    CtxMissing,        // ModelManager 未 with_ctx 就做上下文相关操作（装配缺陷 → 500，非 401）
    ExecuteError { table: String, message: String },
    EntityNotFound { schema, entity, id },
    UniqueViolation { table: String, constraint: String },  // 自动将 PG 23505 转为具体字段冲突
    ListLimitOverMax { max, actual },
    InvalidArgument { message },   // 含 ORDER BY 列名校验失败
    DbxError(#[from] DbxError),
    Sqlx(#[from] SqlxError),
    // ...
}
```

**`SqlError` / `DbxError` / `sqlx::Error` → `DataError` 转换全部在 `fusions::error`（feature = `db`）**：

```rust
use fusions::DataError;
use fusionsql::SqlError;

// service / repo 层用 ? 自动转换
let user: User = UserBmc::get_by_id(&mm, id).await?;   // SqlError → DataError
```

`DbxError` 转换会优先用 SQLSTATE 精确匹配（23505 → conflicted、23503 → bad_request、其余 → server_error）。

## 推荐文件布局（应用层约定，非框架强制）

fusionsql 本身不要求任何特定文件结构 —— BMC / model / service 都可以放在
同一个文件里。但在多模块的应用 crate 里，下面这种 4-file 拆分能让契约面
（model / entity）与实现（bmc / svc）分得开，便于 review 与 IDE 跳转：

| 文件                 | 内容                                       |
| -------------------- | ------------------------------------------ |
| `{entity}_entity.rs` | DB 实体 + `Fields` derive                  |
| `{entity}_model.rs`  | 过滤器（`FilterNodes`）、请求/响应 DTO     |
| `{entity}_bmc.rs`    | `DbBmc` impl + CRUD wrapper                |
| `{entity}_svc.rs`    | 业务编排（事务、跨模块调用、领域规则）     |

是否采用由应用 crate 自决。

## Best Practices

1. **使用 BMC**: 所有数据库操作都通过 BMC 层，保持一致性
2. **事务**: 使用闭包式事务自动管理提交/回滚
3. **作用域过滤**: 使用 `with_filter_interceptor` 按应用规则补充 owner/scope 条件；fusions 不内置应用字段语义
4. **分页**: 始终使用 `Page` 和 `PageResult` 标准化分页
5. **逻辑删除**: 使用 `logical_deletion` 字段而非物理删除
6. **乐观锁**: 对并发更新敏感的表启用 `with_has_optimistic_lock`

## Examples from Codebase

- `crates/fusionsql/src/model_manager.rs` - ModelManager 实现
- `crates/fusionsql-macros/src/` - Fields / FilterNodes 宏实现
- `crates/fusionsql/src/base/` - BMC CRUD 实现
