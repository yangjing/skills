# fusion-ai

LLM providers (19+ via rig), graph-flow execution engine, embeddings,
optional image / audio / video generation.

> Open this file when working on LLM-calling code, agent loops, or anything
> that imports from `fusions::ai::*`.

## Cargo features

| Feature      | Description                                       |
| ------------ | ------------------------------------------------- |
| `with-db`    | `PostgresSessionStorage` for graph-flow sessions  |
| `image`      | Image generation providers                        |
| `audio`      | Audio generation / transcription                  |
| `video`      | Video generation (`video_generation` module)      |
| `worker`     | Cloudflare Workers support                        |

`fusions` re-exports this crate behind the top-level `ai` feature.

## Imports

```rust
use fusions::ai::{AiError, DefaultProvider};
use fusions::ai::factory::{
    ClientFactory, AgentConfig, EmbeddingConfig, FactoryError,
};
use fusions::ai::llm::{LlmProviderConfig, LlmProviderId, build_provider};
use fusions::ai::graph_flow::{
    Task, TaskResult, NextAction, Context,
    Graph, GraphBuilder, FlowRunner,
    Session, SessionStorage, InMemorySessionStorage,
    ExecutionResult, ExecutionStatus, FanOutTask,
};
#[cfg(feature = "with-db")]
use fusions::ai::graph_flow::PostgresSessionStorage;

// rig re-export for direct access to its types when needed:
use fusions::ai::rig;
```

## Providers — prefer the `DefaultProvider` enum

`fusion-ai` exposes `DefaultProvider` for the rig factory path. New code
should use the enum rather than ad hoc provider strings.

```rust
use fusions::ai::DefaultProvider;

let provider: &'static str = DefaultProvider::Anthropic.as_str();   // "anthropic"
match name {
    s if s == DefaultProvider::OpenAi.as_str() => /* … */,
    s if s == DefaultProvider::Ollama.as_str() => /* … */,
    _ => return Err(DataError::bad_request("Unknown provider")),
}
```

Enum variants (`#[non_exhaustive]`):
`Anthropic`, `Azure`, `Cohere`, `DeepSeek`, `Galadriel`, `Gemini`,
`Groq`, `HuggingFace`, `Hyperbolic`, `Mira`, `Mistral`, `Moonshot`,
`Ollama`, `OpenAi`, `OpenAiCompatible`, `OpenRouter`, `Perplexity`,
`Together`, `XAi`.

The Gemini method on `ClientFactory` is named `google()` (Google Gemini),
but the provider short name and `DefaultProvider::Gemini.as_str()` are
both `"gemini"`.

## ClientFactory

```rust
use fusions::ai::factory::ClientFactory;

let factory = ClientFactory::new();
let openai     = factory.openai("sk-…")?;
let anthropic  = factory.anthropic("sk-ant-…")?;
let deepseek   = factory.deepseek("sk-…", Some("https://api.deepseek.com"))?;
let gemini     = factory.google("AIza-…")?;          // Google Gemini
let ollama     = factory.ollama("http://localhost:11434")?;

// openai_compatible takes (base_url, api_key) — NOT (api_key, base_url).
let compat = factory.openai_compatible("https://my-endpoint/v1", "sk-…");
```

All client constructors return `http_client::Result<T>`; convert at the
service boundary with `?` (mapped to `AiError`/`DataError` via the
`fusions::error` impls).

### Agent variants

`ClientFactory` also exposes `*_agent` constructors (`openai_agent`,
`anthropic_agent`, `deepseek_agent`, `google_agent`, `ollama_agent`,
`openai_compatible_agent`, …) that wrap a built client with an
`AgentConfig` in one call.

```rust
use fusions::ai::factory::{AgentConfig, ClientFactory};

let factory = ClientFactory::new();
let agent = factory.anthropic_agent(
    &factory.anthropic("sk-ant-…")?,
    AgentConfig::builder()
        .model("claude-3-5-sonnet")
        .system_prompt("You are a careful planner.")
        .temperature(0.2)
        .max_tokens(1024)
        .build()?,
)?;
```

## Embeddings

```rust
use fusions::ai::factory::{ClientFactory, EmbeddingConfig};

let vectors = ClientFactory::new().embeddings(
    &EmbeddingConfig {
        provider: DefaultProvider::OpenAi.as_str().into(),
        model:    "text-embedding-3-small".into(),
        dims:     1536,
        api_key:  Some("sk-…".into()),
        base_url: None,
    },
    vec!["hello".into(), "world".into()],
).await?;
```

## Graph Flow — task DAG with optional persistence

`Graph` is the static description, `Session` the per-run state, and
`FlowRunner` drives the loop. `Context` carries both arbitrary key/value
state (`set` / `get`) and a chat history (`add_user_message`,
`add_assistant_message`, `get_chat_history`).

### Define a Task

```rust
use fusions::ai::graph_flow::{Task, TaskResult, NextAction, Context, GraphError};
use async_trait::async_trait;

pub struct ProcessTask;

#[async_trait]
impl Task for ProcessTask {
    fn id(&self) -> &str { "process_task" }

    async fn run(&self, context: Context) -> Result<TaskResult, GraphError> {
        let input: String = context.get("input").await.unwrap_or_default();
        let output = format!("Processed: {input}");
        context.set("output", output.clone()).await;
        Ok(TaskResult::new(Some(output), NextAction::Continue))
    }
}
```

### NextAction

```rust
pub enum NextAction {
    Continue,               // proceed to next task
    ContinueAndExecute,     // proceed AND immediately execute
    WaitForInput,           // pause until external input arrives
    End,                    // terminate the flow
    GoTo(String),           // jump to a named task
    GoBack,                 // return to previous task
    Wait(NextTaskAndWaitFor),
}
```

### Build a Graph

```rust
use std::sync::Arc;
use fusions::ai::graph_flow::{Graph, GraphBuilder};

let graph: Arc<Graph> = Arc::new(
    GraphBuilder::new("my_workflow")
        .add_task(Arc::new(StartTask))
        .add_task(Arc::new(ProcessTask))
        .add_task(Arc::new(EndTask))
        .set_start_task("start_task")
        .add_edge("start_task", "process_task")
        .add_edge("process_task", "end_task")
        .add_conditional_edge(
            "process_task",
            |ctx| ctx.get_sync::<bool>("success").unwrap_or(false),
            "end_task",
            "start_task",
        )
        .build(),
);
```

### Run with `FlowRunner`

```rust
use std::sync::Arc;
use fusions::ai::graph_flow::{
    FlowRunner, InMemorySessionStorage, Session, SessionStorage,
    ExecutionStatus,
};

let storage: Arc<dyn SessionStorage> = Arc::new(InMemorySessionStorage::new());
let runner = FlowRunner::new(graph.clone(), storage.clone());

let session = Session::new_from_task("session_123".to_string(), "start_task");
session.context.set("input", "Hello").await;
storage.save(session).await?;

let result = runner.run("session_123").await?;
match result.status {
    ExecutionStatus::Completed       => {}
    ExecutionStatus::WaitingForInput => {
        // …gather input, then continue:
        // runner.continue_with_input("session_123", "user reply").await?;
    }
    _ => {}
}
```

### Context — key/value + chat history

```rust
// arbitrary state (serde, async lock under the hood):
ctx.set("key", "value").await;
let value: Option<String> = ctx.get("key").await;

// chat history (rig-compatible):
ctx.add_user_message("Hello!".into()).await;
ctx.add_assistant_message("Hi there!".into()).await;
let last5 = ctx.get_last_messages(5).await;
```

### Session storage

```rust
// In-memory — development / tests
let storage = Arc::new(InMemorySessionStorage::new());

// PostgreSQL — production (feature = "with-db")
#[cfg(feature = "with-db")]
let storage = Arc::new(PostgresSessionStorage::new(pool));
```

### FanOutTask — parallel execution

```rust
use fusions::ai::graph_flow::FanOutTask;

let fan_out = FanOutTask::new(vec![task1, task2, task3]);
// Each inner task runs concurrently; FanOutTask aggregates results.
```

## Errors

```rust
pub enum AiError {
    Custom(String),
    FactoryError(FactoryError),
    CompletionError(rig::completion::CompletionError),
    ImageGenerationError(rig::image_generation::ImageGenerationError),
}

pub enum FactoryError {
    InvalidProvider(String),
    MissingApiKey(String),
    MissingBaseUrl(String),
    HttpClientError(String),
    EmbeddingError(String),
}
```

`AiError -> DataError` is in `fusions::error` (feature `ai`)，映射分级：
上游 HTTP / Provider 瞬态错误 → 503（可重试）、请求构造 / 响应解析 / 工厂装配
缺陷 → 500，均保留 source 错误链。Graph-flow's
own `GraphError` lives in `fusions::ai::graph_flow::GraphError`; map it at
the service boundary (there is no aggregate `GraphError -> DataError` impl).

### 携密类型与 Debug

`AgentConfig` / `EmbeddingConfig` / LLM transport / provider credentials 均为
手写 Debug，`api_key` 打印 `<REDACTED>` —— 新增携密类型 MUST 沿用该约定，
MUST NOT `#[derive(Debug)]`（`tracing::debug!(?config)` 会把明文密钥落日志）。

### LLM wire 层（`llm` 模块，OpenAI 兼容 transport）

- 底层 `reqwest::Client` 首次请求构建后缓存复用（连接池）；`with_timeout`
  变更超时会自动重建。MUST NOT 在调用路径上自建每请求 client。
- `ChatCompletionRequest.timeout` 为单请求覆盖，经 `RequestBuilder::timeout`
  真实生效；`None` 用 transport 默认。
- 流式 SSE 解析对不合规 provider 分块（空 tool_call 等）跳过并 `debug!` 记录，
  不 panic 流任务。

## Best practices

1. **Use the enum, not the strings.** `DefaultProvider::Anthropic` beats
   `"anthropic"` — typos become compile errors instead of runtime `None`s.
2. **Persist sessions in production.** `InMemorySessionStorage` is for
   tests only; long-running workflows need `PostgresSessionStorage`.
3. **Keep Task `id()` stable and unique.** Edges and conditional routing
   reference IDs by string; renaming a task id silently breaks the DAG.
4. **Treat `WaitForInput` like a checkpoint.** The runner stops there and
   only `continue_with_input(...)` advances — your handler is what
   bridges the external prompt back into the flow.

## Code locations

- `crates/fusion-ai/src/lib.rs` — `DefaultProvider` enum and top-level re-exports
- `crates/fusion-ai/src/client.rs` — `ClientFactory`, `AgentConfig`, `EmbeddingConfig`
- `crates/fusion-ai/src/llm/` — self-hosted chat provider trait + `LlmProviderConfig`
- `crates/fusion-ai/src/graph_flow/{graph,runner,task,context,storage}.rs`
- `crates/fusion-ai/src/error.rs` — `AiError`, `FactoryError`
