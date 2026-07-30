# fusion-ai

LLM providers (19+ via rig), graph-flow execution engine, embeddings,
usage metering, streaming speech-to-text, optional image / audio / video
generation.

> Open this file when working on LLM-calling code, agent loops, or anything
> that imports from `fusions::ai::*`.

## Cargo features

| Feature      | Description                                       |
| ------------ | ------------------------------------------------- |
| `with-db`    | `PostgresSessionStorage` for graph-flow sessions  |
| `image`      | Image generation providers                        |
| `audio`      | rig 的音频生成 / 批量转写（**流式 STT 不受此 gate**，`speech_to_text` 与 `providers` 恒可用） |
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
// 计量装饰器（见 Usage metering）
use fusions::ai::llm::{
    AiUsageCtx, AiUsageEvent, AiUsageSink, MatchedScope, MeteredLlmProvider, NoopUsageSink, Outcome,
};
// 流式 STT（见 Streaming STT）
use fusions::ai::speech_to_text::{
    AudioEncoding, AudioStreamConfig, SpeechToText, SpeechToTextError,
    SttEvent, SttEventStream, SttUplink, SttUplinkStream, TranscriptionResult,
};
use fusions::ai::providers::dashscope::{DashScopeRegion, FunAsrRealtime};
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

> **实现本 crate 的 trait 时，依赖也要从这里取**（v0.3 新增 re-export）：
> `pub use {async_trait::async_trait, bytes, futures};`。`SttUplink::Audio(Bytes)`、
> `SttUplinkStream`、`#[async_trait]` 都出现在公共 API 上，下游自带一份不同版本的
> `bytes` / `async-trait` 会产出 `expected Bytes, found Bytes` 这种读起来像编译器
> bug 的报错。与 `rig` 同样的 SemVer 注意事项：这些是原样透传的上游依赖。

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

## Usage metering（`llm::metered`）

`MeteredLlmProvider` 是 `LlmChatProvider` 的透明装饰器：与 inner 同型，业务侧无感知。
计量上下文 `AiUsageCtx` 在构造时快照（**一次调用一个实例，不要跨调用复用**），
成功调用产出一条 `AiUsageEvent` 交给 `AiUsageSink`（gate 关时装 `NoopUsageSink`，
零行为、无需改业务码）。

```rust
let provider: Arc<dyn LlmChatProvider> =
    Arc::new(MeteredLlmProvider::new(inner, usage_ctx, sink.clone()));
```

`AiUsageCtx` 关键字段：`tenant_id`、`dimensions: BTreeMap<String, String>`
（业务维度快照，空 map = 租户级调用；v0.3 前身是单一的 `facility_id`）、
`feature_code`、`matched_scope`、`provider` / `model`、`credential_id`
（**仅内部成本归集，永不进租户读面投影**）、`session_id`、`request_kind`、
`resolved_region`。

> v0.3 breaking：`AiUsageEvent` 现在是 `#[non_exhaustive]`，**MUST 用两个构造函数**，
> 不能写结构体字面量 —— 每加一个模态否则都是下游破坏性变更。
>
> | 模态 | 构造 | 说明 |
> | ---- | ---- | ---- |
> | chat | `AiUsageEvent::from_ctx_tokens(ctx, &usage, outcome, occurred_at, latency_ms)` | 旧名 `from_ctx_usage` 已删。改名是为了让 STT 路径不会误用它——那会静默丢掉音频时长 |
> | STT  | `AiUsageEvent::from_ctx_audio(ctx, audio_duration_ms, outcome, occurred_at, latency_ms)` | token 三列记 0，表示「本模态不以 token 计量」；一次识别会话记**一行** |
>
> `resolved_region` 是**实际落地**的凭证区域（合规「数据存放地」清单的标注来源），
> MUST 取自调用完成后已知的真实区域，MUST NOT 取路由配置表的自报字段。
> `None` = 该 provider 无区域概念，不是「未校验」。
>
> `audio_duration_ms` 在 `from_ctx_audio` 里是 `i64` 而非 `Option`：provider 没回时长时
> MUST **不记这一行**，而不是记一行空的。

## Streaming STT（`speech_to_text` + `providers::dashscope`）

面向**双向流 / 长连接**的实时识别（WebSocket / gRPC streaming），区别于 rig 的批量
文件转写 `TranscriptionModel`。v0.3 用 `FunAsrRealtime`（DashScope Fun-ASR）替换了
已删除的 `paraformer` 模块。

```rust
#[async_trait]
pub trait SpeechToText: Send + Sync {
    fn provider_name(&self) -> &'static str;     // 审计 / 指标标签，如 "fun_asr_realtime"
    fn model(&self) -> &str;                     // 实际生效模型，持 dyn 的调用方靠它打标签
    fn supports_batch(&self) -> bool { false }   // 做 fallback 用它判断，别 call-and-catch
    async fn transcribe_realtime(&self, uplink: SttUplinkStream, cfg: AudioStreamConfig)
        -> Result<SttEventStream, SpeechToTextError>;
    // …
}
```

**上行是 `SttUplink` 流，不是纯音频流** —— 上下文增强词表可在识别过程中更新，
两者在 provider 侧本就是同一条 WebSocket 上的先后消息，拆成两个入参会把顺序语义
交给调用方自己拼：

| 调用方手上的形状             | 用                                     |
| ---------------------------- | -------------------------------------- |
| 只有音频帧 `Stream<Bytes>`   | `SttUplink::from_audio(frames)`        |
| 音频 + 控制两条独立流        | `SttUplink::merge(audio, control)`     |
| 已保序的混合流（网关常见）   | `SttUplink::from_stream(items)`        |

事件流 `SttEvent`：`Started` → `Partial` / `SegmentFinal`* → `TaskFinished`
（收到 `TaskFinished` 后流 MUST 结束）。注意上行流在调用 `transcribe_realtime`
时就已交给实现，**调用方无法「等 `Started` 再推音频」** —— 实现负责在 session
建立前不丢弃上行项。返回的事件流 MUST 在 Tokio runtime 内 poll（实现内部用
`tokio::spawn` / `tokio::time`），在 `futures::executor::block_on` 上 poll 会 panic。

配置要点（`AudioStreamConfig`）：

- **无 `#[non_exhaustive]` 是刻意的**（那会禁掉 `..base` 更新语法）。构造 SHOULD 写成
  `AudioStreamConfig { channels: 2, ..AudioStreamConfig::pcm_s16le_16k_mono_40ms() }`，
  否则每次字段增补都要改代码。默认构造还预置了 `language_hints = ["zh", "en"]`。
- `hotwords` 在 v0.3 拆成两个正交字段：`vocabulary_ids`（**provider 侧已注册词表的 ID**，
  填词条本身不会生效）与 `context_items`（会话级上下文增强词，每条须含待识别原词）。
  条数 / 长度上限由 provider 定（Fun-ASR：≤5 条、每条 ≤400 字符），超限在**建连前**
  以 `ConfigInvalid` 拒绝 —— 静默裁剪会让上下文增强变成玄学。
- `context_items` 会离开本进程送到 provider，MUST NOT 放真实姓名 / 床号全集。
- `frame_duration_ms` 仅供自查审计：既不下发也不重新切帧，真实分帧取决于你往上行流推什么。
- `AudioEncoding::as_provider_str` 已删除。`PcmF32Le` 与 `PcmS16Le`、`WebmOpus` 与
  `Opus` **不可互换**，由各 provider 的可预检函数（`fun_asr::provider_audio_format`）
  fail-closed 拒绝，而不是静默直通产出「链路通但转写是噪声」。

错误分诊 —— `SpeechToTextError` 上两个**正交**的判定函数，别用其一推另一：

| 函数 | 回答 | 用途 |
| ---- | ---- | ---- |
| `is_retryable()` | 对侧的暂时状态？ | 决定是否换 provider 重放。**仅对未产出 `TaskFinished` 的会话有意义** —— 重放一段已成功的音频会产生重复业务记录 |
| `is_caller_fault()` | 是调用方的请求有问题？ | 网关报 `invalid_argument` 还是 `internal`。缺了它，provider 回的 `InvalidParameter` 会变成 500，运维当服务缺陷立单而实际要改的是租户配置 |

没有 `Cancelled` 变体是刻意的：取消 = 消费者 drop 事件流，流就此结束，没有终态错误。

> **PHI 纪律**：音频字节与转写文本是受保护健康信息。本模块公共类型一律手写 `Debug`，
> 只暴露形状与长度（`<N bytes redacted>` / `<N chars redacted>`）。新增类型 MUST 沿用；
> 下游一句 `tracing::debug!(?x)` 或一次 panic payload 打印就是最难追回的那类泄漏。

区域驻留：`DashScopeRegion::{Beijing, Singapore}` 决定 WebSocket endpoint，
`validate_model_for_region(model, region)` 在建连前校验模型与地域匹配。

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
- `LlmProviderConfig::Qwen` v0.3 新增 `base_url_override: Option<String>`
  （**结构体字面量必须补这个字段**）。它与 `DeepSeek { endpoint }` 性质不同：
  那些 vendor 本就支持自建 / 代理端点，endpoint 是凭证的一部分；dashscope 的端点由
  `region` 决定，而 `region` 又是驻留档的判据。所以本字段 MUST NOT 由凭证或租户配置
  填充（等于让被判定方自报判据），只承载**部署形态**注入（如集成测试对着本地假服务端跑）。
  空串 / 全空白等同 `None`。

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

- `crates/fusion-ai/src/lib.rs` — `DefaultProvider` enum、`rig` / `async_trait` / `bytes` / `futures` re-export
- `crates/fusion-ai/src/client.rs` — `ClientFactory`, `AgentConfig`, `EmbeddingConfig`
- `crates/fusion-ai/src/llm/` — self-hosted chat provider trait + `LlmProviderConfig`
- `crates/fusion-ai/src/llm/metered.rs` — `MeteredLlmProvider`, `AiUsageCtx/Event/Sink`
- `crates/fusion-ai/src/speech_to_text/mod.rs` — `SpeechToText` trait、`SttUplink`、`AudioStreamConfig`
- `crates/fusion-ai/src/providers/dashscope/fun_asr.rs` — Fun-ASR 实时 STT 实装
- `crates/fusion-ai/src/graph_flow/{graph,runner,task,context,storage}.rs`
- `crates/fusion-ai/src/error.rs` — `AiError`, `FactoryError`
