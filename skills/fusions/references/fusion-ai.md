# fusion-ai

OpenAI 兼容 wire（Responses 默认 / Chat Completions 显式可切）、DashScope 原生流式
STT、graph-flow 执行引擎、usage metering、可选 image / audio / video generation。
0.4.0 起零 rig 依赖（fusion-ai-de-rig.md：类型全部本地化，`providers::openai_compatible`
的 `types` / `errors` 是 fork 自 rig 的本地类型层）。

> Open this file when working on LLM-calling code, agent loops, or anything
> that imports from `fusions::ai::*`.

## Cargo features

| Feature      | Description                                       |
| ------------ | ------------------------------------------------- |
| `with-db`    | `PostgresSessionStorage` for graph-flow sessions  |
| `image`      | Image generation / edit providers（openai_compatible 本地实装） |
| `audio`      | 音频生成（TTS）/ 批量转写（**流式 STT 不受此 gate**，`speech_to_text` 与 `providers` 恒可用） |
| `video`      | Video generation (`video_generation` module)      |

`fusions` re-exports this crate behind the top-level `ai` feature.

## Imports

```rust
use fusions::ai::AiError;
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
```

> **实现本 crate 的 trait 时，依赖也要从这里取**（v0.3 新增 re-export）：
> `pub use {async_trait::async_trait, bytes, futures};`。`SttUplink::Audio(Bytes)`、
> `SttUplinkStream`、`#[async_trait]` 都出现在公共 API 上，下游自带一份不同版本的
> `bytes` / `async-trait` 会产出 `expected Bytes, found Bytes` 这种读起来像编译器
> bug 的报错。注意：这些是原样透传的上游依赖，不受本 crate 的 SemVer 保证。

## Provider 命名口径

`llm::LlmProviderId` 是 provider 命名的唯一真相源（`as_str()` 与
`provider_credentials.provider` 列对齐，注意 Qwen → `"dashscope"`）。
0.4.0 删除了服务 rig factory 路径的 `DefaultProvider` enum（19-provider 薄壳，
零业务消费）与 `factory::ClientFactory` / `AgentConfig` / `EmbeddingConfig` /
`FactoryError`——多 provider 归一化工厂属提前优化，消费方直接用下面的
openai_compatible wire。

## openai_compatible —— OpenAI 兼容 wire（唯一 LLM wire）

DeepSeek / Moonshot / Qwen / OpenAI 四端的统一 wire。模型工厂 API 已**按形态分化**
（`chat_completions_model()` 与 `completions_api()` 已删）：

- `Client::completion_model(model)` → `completion::CompletionModel`（**Chat
  Completions** 形态——通用基线，仅支持 chat 的端点如 Moonshot 直接可用）
- `Client::responses_model(model)` → `responses_api::ResponsesCompletionModel`
  （**Responses** 形态——Qwen 关思考 / 结构化输出等高级面）

```rust
use fusions::ai::providers::openai_compatible::{Client, types as core};
use fusions::ai::providers::openai_compatible::completion::{CompletionModel, CompletionRequest};

let client = Client::builder(&api_key).base_url("https://api.deepseek.com").build();

// Chat Completions（completion_model 即此形态——thinking 关闭等 provider 参数
// 经 additional_params 注入 extra-body；max_tokens 是一等字段，输出硬闸）
let model: CompletionModel = client.completion_model("deepseek-flash");
let request = CompletionRequest::from_history(
    model.model(),                       // 或任意 model 覆盖
    Some("You are a helpful assistant".into()),  // preamble → system 消息打头
    vec![core::Message::user("Hello")],
    vec![],                              // tools（core::ToolDefinition）
    None,                                // tool_choice
    Some(0.7),                           // temperature
    Some(8192),                          // max_tokens（一等字段）
    Some(serde_json::json!({"thinking": {"type": "disabled"}})),  // extra-body
)?;
let response = model.completion(request).await?;
let text = response.text();              // Option<String>，拼接全部 assistant 文本
let usage = response.usage_tokens();     // core::Usage（provider 无关形态）
let calls = response.tool_calls();       // &[ToolCall]

// Responses 形态（Qwen 关思考用 reasoning.effort="none"）
use fusions::ai::providers::openai_compatible::responses_api;
let responses_model = client.responses_model("qwen3.7-plus");
let request = responses_api::CompletionRequest::from_history(
    "qwen3.7-plus", None, vec![core::Message::user("你好")],
    vec![], None, None, Some(131_072),
    Some(serde_json::json!({"reasoning": {"effort": "none"}})),
)?;
let response = responses_model.completion(request).await?;
```

### 流式（SSE 双终态形态）

Chat Completions 流以 `data: [DONE]` 结束；Responses 流没有 `[DONE]`，
终态由 `response.completed / incomplete / failed` 事件携带。两形态事件枚举同名
（`completion::streaming::StreamingChoice` / `responses_api::streaming::StreamingChoice`）：
`Text(delta)` → `ToolCall { id, call_id, name, arguments }` →
`ToolCallDelta { id, content }` → `Reasoning` → `Final(终态 usage)`。

```rust
use futures::StreamExt;
use fusions::ai::providers::openai_compatible::completion::streaming::StreamingChoice;

let mut stream = model.stream(request).await?;   // stream:true + include_usage 由实现注入
while let Some(choice) = stream.next().await {
    match choice? {
        StreamingChoice::Text(delta) => { /* 逐 token */ }
        StreamingChoice::Final(final_response) => {
            // final_response.usage: prompt/completion/total tokens
        }
        _ => {}
    }
}
```

### 多模态面（本地实装，reqwest multipart）

- `client.embedding_model_with_ndims(model, ndims)` → `embed_texts` → `Vec<Embedding { document, vec }>`
- `client.transcription_model("whisper-1")` → `transcription(TranscriptionRequest::new(data, filename)…)` → `.text`
- `client.image_generation_model("dall-e-3")` → `image_generation(ImageGenerationRequest::new(prompt).with_size(w, h))` → `.image`（bytes）
- `client.image_edit_model("dall-e-2")` → `image_edit(ImageEditRequest::new_single(…))` → `.image`
- `client.audio_generation_model("tts-1")` → `audio_generation(AudioGenerationRequest::new(text, voice))` → `.audio`
- `client.verify()` → 凭证探测（401 → `Http { 401 }`，5xx → 瞬态）

行为基线：`crates/fusion-ai/tests/`（wiremock fixture 按端点方言组织——OpenAI 官方 /
DashScope / DeepSeek / Kimi 各一，后续加端点先加方言样例）。

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

// chat history（openai_compatible 内部消息格式，可直接喂 CompletionRequest::from_history）:
ctx.add_user_message("Hello!".into()).await;
ctx.add_assistant_message("Hi there!".into()).await;
let history = ctx.get_messages().await;          // Vec<openai_compatible::types::Message>
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

### `llm::usage_batch` —— 计量事件批量落库管道

`metered` 只定捕获缝（`AiUsageSink` trait + `NoopUsageSink`）；`usage_batch` 补上
「批量、有界重试、best-effort durability」的通用管道——**DB 写函数由消费方注入**
（闭包内自行持有 DB 句柄），本模块不依赖任何数据库面：

```rust
use fusions::ai::llm::usage_batch::spawn_usage_batch_writer;

let pipeline = spawn_usage_batch_writer(1024, move |batch: Vec<AiUsageEvent>| async move {
    usage_repo::insert_batch(&dbx, &batch).await        // Err(String) = 本批失败 → 重试
});
let provider = Arc::new(MeteredLlmProvider::new(inner, usage_ctx, pipeline.sink.clone()));
// … 关机：drop 全部 sink clone 之后 await writer
drop(provider);
pipeline.writer.await?;
```

行为参数：单批上限 **64**（收一条后贪婪补满）；写重试 **3 次**（退避 50ms →
200ms），耗尽 log + drop（**不重入队**——持续失败的写目标不能让队列无界增长）；
批写 panic 被 `catch_unwind` 恢复（loop 存活、receiver 不丢）；通道满 `try_send`
非阻塞丢弃并计数。

**durability 是 best-effort，MUST NOT 描述为可计费级精确**：通道满 / 重试耗尽 /
panic 三类丢失点有进程内计数（`UsageMetrics::{dropped, write_failed,
worker_restart}`）；进程被 kill 时队列内容不可观测地丢失。零丢失需要事务化
outbox，不属本模块。优雅关机协议 = drop 全部 `AiUsageSink` clone 之后 await
writer `JoinHandle`（通道关闭即排空退出）。

## Streaming STT（`speech_to_text` + `providers::dashscope`）

面向**双向流 / 长连接**的实时识别（WebSocket / gRPC streaming），区别于
openai_compatible 的批量文件转写 `TranscriptionModel`。v0.3 用 `FunAsrRealtime`
（DashScope Fun-ASR）替换了已删除的 `paraformer` 模块。

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

## TTS / 声纹（`providers::{dashscope, minimax, volcengine}`）

语音合成与声音复刻的独立 provider 面（不属 openai_compatible wire；与流式
STT 一样恒可用，不受 `audio` feature gate——那只门控 openai_compatible 的
`audio_generation` / `transcription` 模块）。三家各有协议方言，公共底座在
`providers::speech`（`SseDataParser` SSE 解析、`AudioContainer` 容器判定、
`SpeechError` 错误面——MiniMax T2A 流式音频块是 **hex** 编码、豆包是 base64，
别按同一套解码写）。

| Provider | 能力 | 协议要点 |
| -------- | ---- | -------- |
| `dashscope::QwenTts` | Qwen TTS 合成 | DashScope 凭证 + `DashScopeRegion`；`QwenTtsRequest::{with_model, with_language_type}` |
| `dashscope::QwenVoiceEnrollment` | Qwen 声纹注册（说话人音色建档） | 凭证同上；`CreateVoiceRequest` / `EnrolledVoice` / `VoiceList` |
| `minimax::MinimaxTts` | T2A V2 合成 + 声音复刻 | `POST /v1/t2a_v2?GroupId=…`（`stream=true` SSE，`data.audio` hex 块，末块 `extra_info`）；复刻两步：files/upload(purpose=voice_clone) → voice_clone（voice_id 调用方自定义）；**业务错误模式 = HTTP 200 + `base_resp.status_code != 0`**（1002 限流 / 1008 余额不足） |
| `volcengine::DoubaoSpeech` | 豆包 V3 复刻 + 单向流式合成 | 单凭证 `X-Api-Key`；复刻 `POST /api/v3/tts/voice_clone`（base64 样本 + 调用方自定义 `custom_speaker_id`，试听走响应 `demo_audio`）；合成 `POST /api/v3/tts/unidirectional`（HTTP chunked **JSON 行流**，`data` base64，`code=20000000` 成功结束行）；复刻音色（ICL）须 `req_params.model` 显式指定 tts 系枚举 |

错误面 `SpeechError` 与 STT 共用底座；构造形态统一 `new(credentials) →
with_region/with_model/with_base_url` builder 链（`parse_dashscope_region`
单点解析区域）。

## Errors

```rust
pub enum AiError {
    Custom(String),
    OpenAiCompat(#[from] OpenAiCompatError),
}

pub enum OpenAiCompatError {
    Http { status: u16, message: String },  // provider 非 2xx
    Transport(String),                      // 连接层（reqwest send 失败）
    ResponseParse(String),                  // 反序列化 / SSE 帧非法
    RequestBuild(String),                   // 请求构造
    Stream(String),                         // 流中途错误
}
// OpenAiCompatError::is_upstream_transient()：Transport / Http(5xx|429) → true
```

`AiError -> DataError` is in `fusions::error` (feature `ai`)，映射分级判据的唯一
真相源是 `AiError::is_upstream_transient()`：上游瞬态 → 503（可重试）、本地缺陷 → 500，
均保留 source 错误链。Graph-flow's
own `GraphError` lives in `fusions::ai::graph_flow::GraphError`; map it at
the service boundary (there is no aggregate `GraphError -> DataError` impl).

### 携密类型与 Debug

`openai_compatible::Client`（api_key）/ LLM transport / provider credentials 均为
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

1. **用 `LlmProviderId`，不用裸字符串。** `LlmProviderId::DeepSeek` beats
   `"deepseek"` — typos become compile errors instead of runtime `None`s.
2. **Persist sessions in production.** `InMemorySessionStorage` is for
   tests only; long-running workflows need `PostgresSessionStorage`.
3. **Keep Task `id()` stable and unique.** Edges and conditional routing
   reference IDs by string; renaming a task id silently breaks the DAG.
4. **Treat `WaitForInput` like a checkpoint.** The runner stops there and
   only `continue_with_input(...)` advances — your handler is what
   bridges the external prompt back into the flow.
5. **模型工厂按形态选方法**：`completion_model` = Chat Completions（Moonshot
   等 chat-only 端点直接可用）；Responses 面用 `responses_model`——Qwen 关思考
   `reasoning.effort="none"`，DeepSeek 留 Chat Completions
   （`thinking:{type:disabled}`；Responses 形态无完全关闭档，fusion-ai-de-rig.md §P5b）。

## Code locations

- `crates/fusion-ai/src/lib.rs` — `async_trait` / `bytes` / `futures` re-export
- `crates/fusion-ai/src/providers/openai_compatible/` — OpenAI 兼容 wire（`types.rs` 本地类型层 / `errors.rs` 错误模型 / `completion/` chat / `responses_api/` / 多模态面）
- `crates/fusion-ai/tests/` — wiremock 行为基线 fixture（端点方言样例）
- `crates/fusion-ai/src/llm/` — self-hosted chat provider trait + `LlmProviderConfig`
- `crates/fusion-ai/src/llm/metered.rs` — `MeteredLlmProvider`, `AiUsageCtx/Event/Sink`
- `crates/fusion-ai/src/llm/usage_batch.rs` — `spawn_usage_batch_writer`, `UsageMetrics`, `BatchSink`
- `crates/fusion-ai/src/speech_to_text/mod.rs` — `SpeechToText` trait、`SttUplink`、`AudioStreamConfig`
- `crates/fusion-ai/src/providers/dashscope/fun_asr.rs` — Fun-ASR 实时 STT 实装
- `crates/fusion-ai/src/providers/{dashscope,minimax,volcengine}/` — TTS / 声纹注册（`qwen_tts.rs` / `voice_enrollment.rs` / `minimax/tts.rs` / `volcengine/speech.rs`）
- `crates/fusion-ai/src/providers/speech/mod.rs` — 语音公共底座（`SseDataParser` / `AudioContainer` / `SpeechError`）
- `crates/fusion-ai/src/graph_flow/{graph,runner,task,context,storage}.rs`
- `crates/fusion-ai/src/error.rs` — `AiError`（收敛形态，§Errors）
