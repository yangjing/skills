# hetuflow

Durable workflow 框架（聚合 crate + 四个子 crate）。业务系统依赖 `hetuflow`
聚合包经 features 选择性引入，不直接依赖子 crate。

> Open this file when working on workflow 定义校验 / 推进决策 / 事务内编排 /
> outbox·timer worker。本仓（hetu-xueji）当前**未接线** hetuflow——需要时参照
> hetuos 补 path deps。

## Import Boundary

Standalone workspace crate 家族（聚合 `fusions` 不 re-export、无 `DataError`
转换，错误面是自有 `FlowError`）。feature 分层（含依赖闭包）：

| Feature | 引入 | 内容 |
| ------- | ---- | ---- |
| `core` | `hetuflow-core` | 领域类型 + 纯 helper（零依赖：不依赖 fusions / ConnectRPC / Axum / sqlx） |
| `runtime`（default） | `+ hetuflow-runtime` | 图校验 + 推进决策（纯计算） |
| `sqlx` | `+ hetuflow-sqlx` | Postgres 存储（接 caller 的 `DbxPostgres` 事务） |
| `service` / `full` | `+ hetuflow-service` | 事务内编排 + outbox / timer worker 骨架 |

```rust
use hetuflow::prelude::*;   // 按启用 feature 条件导出全部常用符号
```

宿主绑定层用 `features = ["service"]`，经 adapter 做 proto↔core 映射 +
scope / 审计 / 通知绑定；只做设计态校验的消费者（如 IR 编译器）用默认
`runtime`（依赖闭包内无 store、无编排）。**框架不知道宿主是谁**。

## 四层职责

```rust
// core —— 领域类型
WorkflowDefinition / WorkflowNode / WorkflowTransition / WorkflowInstance
OutboxRecord / TimerRecord / NodeKind / ActivityStatus / FlowError …

// runtime —— 纯计算（无 IO）
validate_definition(&nodes, &transitions)?;     // 图结构校验
validate_domain_driven(&nodes)?;                // 领域驱动约束校验
lint_definition(&nodes, &transitions);          // 软提示（LintFinding）
decide_start(&nodes);                           // 起点决策
decide_advance(...);                            // 推进决策（下一步转移）
find_next_transition(...);

// sqlx —— 存储（PG-only）
WorkflowStore / PgWorkflowStore                  // 跑在 caller 的 DbxPostgres 事务里

// service —— 编排 + worker 骨架
WorkflowService::{start, signal, resubmit, fire_timer, on_notification_delivered, …}
  // 方法签名一律收 &DbxPostgres——事务边界归调用方（TxnRunner port）
CallbackRegistry::new().register(Arc<dyn BusinessCallbackHandler>)?
OutboxDispatcher::new(runner, dispatcher, config).run_forever()   // 或 run_once
TimerPoller::new(runner, service, config).run_forever()
```

要点：

- **事务边界归调用方**。`WorkflowService` 的方法收 `&DbxPostgres`，宿主把
  编排放进自己的事务里；worker 经 `TxnRunner` port 取事务，不自己开池。
- **通知 / 回调走 outbox**：业务回调经 `CallbackRegistry` 注册，投递由
  `OutboxDispatcher` worker 驱动；`NotificationDispatcher` 是宿主实现的 port。
- core 层持久枚举全量字符串→SMALLINT（wire number）——DB 侧存 smallint。

## Code locations

- `crates/hetuflow/src/lib.rs` — 聚合 re-export + `prelude`
- `crates/hetuflow-core/src/lib.rs` — 领域类型 / `FlowError`
- `crates/hetuflow-runtime/src/lib.rs` — 校验 / 决策 / lint
- `crates/hetuflow-sqlx/src/` — `PgWorkflowStore` / `WorkflowStore`
- `crates/hetuflow-service/src/{service,command,ports,worker}.rs` — 编排 / 命令 / port / worker 骨架
