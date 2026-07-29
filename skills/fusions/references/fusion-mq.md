# fusion-mq

Standalone message-queue abstraction: producer/consumer traits,
`MessageQueuePlugin`, and the built-in Postgres `event_queue` provider.

> Open this file when working on event enqueue/polling code, `[fusion.mq]`
> config, `MessageQueuePlugin`, or anything importing `fusion_mq::*`.

## Import Boundary

`fusion-mq` is a workspace `fusion-*` crate, but the aggregate `fusions`
crate does **not** re-export it. Import it directly:

```rust
use fusion_mq::{
    MessageQueuePlugin, EventProducerHandle, EventConsumerHandle,
    PublishEvent, EventConsumer, EventProducer, RetryDecision,
};
```

The crate default feature is `with-postgres`. There is no `fusions::mq`
module and no `fusions::error` conversion for `MqError`; map MQ failures at
the application boundary.

## Plugin

Register the plugin once at application startup. It reads `[fusion.mq]` and,
when enabled, registers `EventProducerHandle` and `EventConsumerHandle` as
long-lived components.

```rust
use fusion_mq::MessageQueuePlugin;
use fusions::core::Application;

let app = Application::builder()
    .add_plugin(MessageQueuePlugin::new())
    .run()
    .await?;
```

`enable = false` makes the plugin skip provider construction. If
`provider = "postgres"` while `with-postgres` is disabled, startup panics.

## Config

```toml
[fusion.mq]
enable = true
provider = "postgres"

[fusion.mq.postgres]
url = "postgres://user:pass@localhost:5432/myapp_mq"
max_connections = 10
min_connections = 1
acquire_timeout_seconds = 10
idle_timeout_seconds = 600
table_name = "event_queue"
```

`table_name` is interpolated into SQL and is validated to `[a-zA-Z0-9_]`.
The Postgres provider owns an independent `sqlx::PgPool`; it intentionally
does not use `fusion-db`, `ModelManager`, RLS session vars, or `SET LOCAL`.

## Producer

Use `EventProducerHandle` from the component registry and publish
`PublishEvent`. The event payload is application-defined JSON; include
tenant/scope context in the payload when consumers need it.

```rust
use fusion_mq::{EventProducerHandle, PublishEvent};
use fusions::core::application::Application;
use serde_json::json;

let producer = Application::global().try_component::<EventProducerHandle>()?;
producer
    .publish(
        PublishEvent::new(
            "task.completed",
            "service-a",
            "service-b",
            json!({ "task_id": task_id, "tenant_id": tenant_id }),
        )
        .with_max_retries(3),
    )
    .await?;
```

Postgres defaults `max_retries` to 3 when `PublishEvent.max_retries` is
`None`.

## Consumer

Consumers claim pending events by target service. Postgres uses
`FOR UPDATE SKIP LOCKED`, so multiple consumers can poll concurrently
without duplicate claims.

```rust
use fusion_mq::{EventConsumerHandle, RetryDecision};
use std::time::Duration;

let events = consumer.claim_pending("service-b", 20).await?;
for event in events {
    match handle_event(&event).await {
        Ok(()) => consumer.mark_processed(event.id).await?,
        Err(err) => {
            let decision = if event.retry_count + 1 >= event.max_retries {
                RetryDecision::Dead
            } else {
                RetryDecision::Retry
            };
            consumer.mark_failed(event.id, &err.to_string(), decision).await?;
        }
    }
}

consumer.reap_zombie("service-b", Duration::from_secs(300)).await?;
```

`reap_zombie` is required. If a worker crashes after `claim_pending` but
before `mark_processed` / `mark_failed`, the row stays `processing`; a
background task must periodically reset stale rows or they are silently
stuck.

## Best Practices

1. **Do not use MQ for request-scoped DB work.** MQ has its own pool and no
   `ModelContext`; put required identity/scope facts into the payload.
2. **Map `MqError` explicitly.** The aggregate `fusions` crate does not depend
   on `fusion-mq`, so there is no automatic `MqError -> DataError`.
3. **Always run a zombie reaper.** Pick `stuck_after` well below the business
   SLA and run it from the consumer process.
4. **Keep event schemas versioned by convention.** `fusion-mq` treats payloads
   as opaque JSON; producer/consumer schema compatibility is application
   responsibility.

## Code Locations

- `crates/fusion-mq/src/lib.rs` — crate boundary and direct exports
- `crates/fusion-mq/src/plugin.rs` — `MessageQueuePlugin`
- `crates/fusion-mq/src/config.rs` — `MqConfig` / `PostgresMqConfig`
- `crates/fusion-mq/src/producer.rs` — `EventProducerHandle`
- `crates/fusion-mq/src/consumer.rs` — `EventConsumerHandle` / `RetryDecision`
- `crates/fusion-mq/src/postgres/` — Postgres provider
