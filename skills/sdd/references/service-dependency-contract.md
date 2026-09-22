---
status: active
version: v2  # 2026-07-26
---

# 服务依赖契约

> **适用范围**：微服务 / 领域服务之间的依赖治理，尤其是「事实服务（SoR）→ 决策服务」这类强契约场景
> **规范语言**：BCP 14（RFC 2119/8174）—— MUST、MUST NOT、SHOULD、SHOULD NOT、MAY
> **定位**：服务依赖与通信协议领域的规范性来源（[SPECIFICATION §1.3](./SPECIFICATION.md#13-优先级与规范性来源)）
> **目标**：在保持边界清晰的前提下降低跨服务耦合与一致性成本，使系统可拆分、可演进、可审计
> **本文不重述**：SoR / Read Model / Producer / Consumer 等共享术语 → [SPECIFICATION §2](./SPECIFICATION.md#2-术语最小集合)

## 0. Agent 执行协议

1. **Trigger**：设计跨服务依赖、选择通信协议、决定数据复制边界、确定或变更边界信任模型（§4.6）、或需要申报协议例外时，MUST 加载本文。
2. **Load**：只读命中章节；共享术语读 [SPECIFICATION §2](./SPECIFICATION.md#2-术语最小集合)；例外通道的登记表、信任模型声明与 ADR 编号读项目文档。
3. **Apply**：本文定依赖方向、协议选型与例外判据；具体框架、transport 实现、契约目录，以及所采用的信任模型以项目 ADR / overlay 为准。
4. **Conflict / Stop**：需要新增偏离默认协议的通道（WebSocket / MQTT / SSE / REST / 自定义帧）、或需要切换边界信任模型（§4.6）时 MUST 停止，先落项目 ADR 再实现；MUST NOT 先实现后补记。
5. **Output**：涉及跨服务依赖的交付说明 MUST 点名依赖方向、在线 / 离线形态、降级策略，以及（如涉及）例外或信任模型的 ADR 编号。
6. **MUST NOT**：MUST NOT 让 Consumer 写入 Producer 归属的数据；MUST NOT 用本文的例外条款证明一条未经 ADR 的新通道成立；MUST NOT 在未更新 ADR 的情况下让边界组件开始或停止注入身份 header。

## 1. 依赖形态术语

本文独有的形态术语（其余共享术语见 [SPECIFICATION §2](./SPECIFICATION.md#2-术语最小集合)）：

- **在线依赖**：请求路径上必须同步调用对方服务才能完成处理
- **离线依赖**：通过复制 / 事件 / 定时同步获取对方数据，处理路径不依赖对方的在线可用性

---

## 2. 依赖方向与边界原则

### 2.1 单向依赖（默认强制）

- MUST 只允许 Consumer 依赖 Producer 的事实输出；Producer MUST NOT 依赖 Consumer（避免环依赖）
- Consumer MUST NOT 写入 Producer 归属的数据（包括「方便起见的补字段 / 状态位」）；写入权 MUST 唯一

> 设计根据：单向依赖本质是信息隐藏边界 —— Producer schema 演进 MUST NOT 通过 Consumer 反向窥探（如读复制表回填字段）来「补救」，那是信息泄漏反模式（[design-philosophy.md §4](./design-philosophy.md#4-信息隐藏与泄漏)）。

### 2.2 数据所有权（Data Ownership）

- 每张表 / 每个实体 MUST 有明确归属（唯一 SoR）
- 「同库共享」与「跨库复制」均不改变所有权：只有归属服务 MUST 负责写入与语义演进

### 2.3 依赖分层

- **运行时强依赖**：SHOULD NOT 出现在核心决策链路中；若必须存在，MUST 有明确的降级策略与超时边界
- **事实输入依赖**：SHOULD 优先采用离线依赖（复制 / 投影），以提升可用性与稳定性
- **治理依赖**：审计、存证、合规校验等 MAY 异步 / 补偿执行，但 MUST 可追溯、可复现

---

## 3. 模式 A：独立数据库 + PostgreSQL 逻辑复制（推荐基线）

适用目标：Producer（SoR）与 Consumer（决策/查询）各自独立数据库，Consumer 通过逻辑复制获得 Producer 的最小必要事实，形成本地 Read Model。

### 3.1 数据面：发布表与订阅表

- Producer 侧 MUST 提供「对外发布表（Published Tables）」用于对下游稳定输出
  - SHOULD 放在独立 schema（如 `public_export.*`）
  - 输出 MUST 最小化：只含下游决策 / 查询必需字段，避免敏感明文扩散
- Consumer 侧 MUST 订阅到独立的「复制表（Replicated Tables）」
  - SHOULD 放在独立 schema（如 `replica_<producer>.*`）
  - 复制表 MUST 只读；业务写入 MUST NOT 发生

### 3.2 复制边界（最小必要）

- MUST 只复制「事实索引级数据」
  - 主体标识与类型、状态、组织隶属、成员 / 管理员关系、关系生效时间窗等
- MUST NOT 复制「高敏要素明文」
  - 证件号 / 手机号 / 生物特征等 SHOULD 改用引用、哈希或外部凭证引用

> 设计根据：「最小必要」 是复杂度下沉的强制落地（[design-philosophy.md §5](./design-philosophy.md#5-复杂度下沉author-pain--caller-pain)）—— Consumer 多用一个字段 = Producer 永久负担。Producer 作者多设计一次发布表，所有 Consumer 零成本复用。

### 3.3 DDL / 迁移与兼容窗口（强制）

- 逻辑复制默认不处理 DDL：两侧 MUST 通过迁移流程维护结构一致
- 变更顺序 SHOULD 遵守下列次序——颠倒会导致复制中断或下游字段缺失：
  - **新增字段**：先在 Consumer 侧加字段并保持可空 / 默认兼容，再在 Producer 侧开始写入并发布
  - **删除字段**：先停止 Consumer 依赖并发布兼容版本，再在 Producer 侧停写并最终删除（保留兼容窗口）
- 被复制表 MUST 有主键或明确的 Replica Identity，否则更新 / 删除不可靠

### 3.4 一致性与可用性约束

- Consumer MUST 显式接受「最终一致」
  - MUST 定义最大允许滞后（Max Staleness）与超阈处理策略（拒绝 / 降级 / 只读允许）
- MUST 监控复制延迟与错误
  - 复制 lag、订阅断连、表缺失 / 结构不一致、冲突与重放失败等 MUST 触发告警

---

## 4. 在线调用：ConnectRPC（Protobuf）契约

适用目标：在需要同步交互的流程中（例如审批、签名确认、授权写入、审计回执），以强约束接口契约减少跨语言成本并提升性能。

### 4.1 ConnectRPC 适用边界

- MUST 用于在线流程与命令型交互（Command）
  - 例如：创建 / 撤销授权、提交审批、触发签名、查询决策解释等
- MUST NOT 用于高频事实读取
  - 高频查询 SHOULD 走本地 Read Model，避免把 Producer 变成在线瓶颈
- 前后端交互与后端服务间交互的默认实现 MUST 是 ConnectRPC；文件上传 / 下载与流媒体传输 MAY 走专项协议，但 MUST 在接入边界显式登记

### 4.2 Protobuf 作为共享类型定义（推荐）

- Protobuf SHOULD 作为跨服务契约的单一真实源
  - 覆盖 Service 定义 + Request / Response message + 公共基础类型
- Protobuf SHOULD NOT 用于统一「服务内领域模型 / 数据库实体」
  - 领域模型 SHOULD 允许各服务独立演进；契约层 SHOULD 保持稳定与最小化

> 设计根据：浅契约 + 深实现是深模块原则的服务级投射（[design-philosophy.md §3](./design-philosophy.md#3-模块深度深-vs-浅)）。Proto 暴露窄接口，服务内部领域模型独立演进 = 复杂度藏在实现而非 API。

### 4.3 版本与兼容规则（强制）

- 契约包 MUST 按 Bounded Context 划分并携带版本号（如 `identity.v1`、`access_control.v1`）
- 字段级演进规则（只新增、不重用编号、删除用 `reserved`、语义变化升 v2）以 [SPECIFICATION §7.3](./SPECIFICATION.md#73-protobuf-演进规则proto-字段变更强制) 为准，本节不重述
- 未发布 1.0 的项目 MAY 在项目 overlay 中声明更宽松的兼容策略；对外契约一旦进入兼容窗口，MUST 回到上述规则

### 4.4 东西向通信协议（强制）

服务间（东西向）通信 MUST 使用 **ConnectRPC over HTTP/2**（三协议族：gRPC / Connect / gRPC-Web），契约源自项目 overlay 声明的 proto 契约目录。

**强制约束**：

| 维度 | 规则 |
|------|------|
| 传输协议 | 内网服务间调用 MUST 走 HTTP/2 cleartext（h2c）；启用 TLS 时走 ALPN `h2` |
| 服务端承载 | 服务端 MUST 端到端支持 HTTP/2，并在项目 overlay 中声明框架配置与 h1 / h2 兼容策略 |
| 客户端构造 | 客户端 MUST 使用支持 HTTP/2 的 ConnectRPC transport；MUST NOT 用仅支持 HTTP/1.1 的 client 调用其它服务 |
| 客户端韧性（自愈） | 东西向 transport MUST 自愈：上游重启 / 网络分区恢复后 MUST 自动重连，无需重启调用方进程。半开连接（含**在途未确认写数据**的半开）MUST 在有界时间内被探测——SHOULD 用**内核层** TCP 探活（不依赖应用 CPU 调度、不误杀健康长流）而非应用层心跳；重连 dial MUST 有 connect-timeout 上界。MUST NOT 让在途请求因半开卡在 TCP 重传数分钟（「必须重启调用方进程才恢复」即违例） |
| 契约定义 | 所有 service / message MUST 在项目契约目录声明；MUST 用项目锁定的工具生成服务端接口与 client |
| 调用方式 | MUST 用生成的 typed client + 契约类型；MUST NOT 用通用 HTTP client 手拼 JSON body 调用 |
| 流式场景 | 实时流（音频帧 / 事件推送 / 长查询结果）MUST 用 proto `stream` 关键字声明 server-streaming / client-streaming / bidi-streaming RPC |
| 错误链 | 错误 MUST 经「领域错误 → 模块错误 → 传输层错误」逐层收口 |

**禁止清单（MUST NOT）**：

- MUST NOT 用裸 WebSocket 承载东西向调用（含 reverse proxy 把 WS 帧透传到上游服务）
- MUST NOT 用通用 HTTP client 直拼 HTTP/1.1 JSON 调用其它服务
- MUST NOT 跳过契约层、以自定义二进制帧格式互通
- MUST NOT 把仅支持 HTTP/1.1 的 plaintext client 用作服务间 transport
- MUST NOT 新增绕过 ConnectRPC 的服务间 REST / HTTP-JSON / WS 专用通道；文件上传 / 下载与流媒体例外 MUST 先落项目 ADR 或专项设计记录

**例外申报**：只有下列三类情形 MAY 偏离默认协议，且 MUST 走项目 ADR 或专项设计流程申报，说明触发条件、风险、替代方案与退出条件：

| # | 情形 | 附加要求 |
|---|------|---------|
| ① | 跨语言互操作必须使用其它协议 | 说明目标语言栈与不可用原因 |
| ② | 性能基准证明 ConnectRPC 双向流不满足 SLA | 附基准数据与 SLA 口径 |
| ③ | **只读运维诊断探测**：纯健康 / 存活诊断，无业务语义、无契约面的服务间 HTTP 探测（如聚合各服务的健康端点） | MUST 满足下列全部限定条款 |

③ 类的限定条款（MUST 全部满足）：

- 探测目标 MUST 来自静态配置；MUST NOT 运行时发现
- MUST 只请求健康检查路径；MUST NOT 跟随重定向
- MUST 设响应大小上限；MUST NOT 重试
- MUST 设 per-target 超时上界，并满足**超时预算不变式**：被探测方内层探测的总预算 < 外层 per-target 超时
- 错误 MUST 脱敏为分类码；MUST NOT 回吐原始错误串
- 真正的 metrics 基础设施落地后 MUST 退役该通道

该类例外 MUST NOT 覆盖任何业务东西向调用——服务间强类型业务调用的规则不变。南北向 Connect / gRPC-Web 透明转发属于 §4.5 定义的合法接入模式，**转发行为本身**不需要例外 ADR；但转发时是否注入可信身份 header，取决于 §4.6 的边界信任模型，该模型 MUST 由项目 ADR 声明。

### 4.5 南北向通信协议（外部接入）

南北向（浏览器 / 移动端 / 外部 IoT 设备 → backend）默认使用 ConnectRPC；文件上传 / 下载、流媒体和外部设备协议接入允许使用 WebSocket / MQTT / SSE / HTTP-REST，**但帧 schema MUST 用 Protobuf 契约化**：

| 维度 | 规则 |
|------|------|
| 帧 schema | 上下行消息 MUST 在项目契约目录声明对应 message；MUST NOT 仅以客户端语言类型或 JSON Schema 维护字段定义 |
| 协议桥接 | 边界组件（网关 / BFF，若项目设有该层）负责南北 ↔ 东西转换；向上游服务的调用 MUST 用 §4.4 规定的 ConnectRPC（含 bidi-stream）；MUST NOT 把裸 WS 帧透传到上游 |
| 透明转发（合法接入模式） | 浏览器的 **Connect / gRPC-Web over HTTP** 请求 MAY 由边界组件**透明转发**到上游：body 仍为 proto（不反序列化），边界只做准入与按 `service/method` 路由。proto 契约端到端在场，故与上一行禁止的「透传裸 WS 帧」性质不同。**是否在转发时注入可信身份 header，取决于项目采用的信任模型（§4.6）**——per-service trust-root 模型下 MUST NOT 注入 |
| 字段裁剪 | 边界组件 MAY 在 proto ↔ JSON 转换层做字段过滤 / 权限脱敏 |

**典型链路**：浏览器 WS 帧 ↔ 边界组件的 proto ↔ JSON 转换 ↔ 生成的 stream client bidi-stream ↔ 上游 stream service

**文件 / 流媒体 / 外部协议例外**：偏离默认 ConnectRPC 的此类通道 MUST 先落项目 ADR，并在项目侧（后端架构文档）维护中心登记表；新增通道 MUST 先 ADR 再回登。通用选型准则：

| 场景 | 推荐通道 |
|------|---------|
| 文件持久化于另一服务，且每次访问需过领域门控（授权 / 归属 / 审计） | 东西向 server-streaming RPC：帧用 proto `stream` 契约化，不绕协议、不受单进程内存 buffer 约束 |
| 瞬时解析缓冲，内容仅作本服务的解析输入，无跨服务存储 | 本地 REST 通道：解析后即弃、不持久化、不跨服务取字节 |

> 两类常见方案的否决理由：unary `bytes` 在大文件场景会撞 RPC 单消息上限（ConnectRPC 量级为 4 MB），通常否决；signed-URL 会绕开逐次访问的门控与审计链，在有该类合规要求时否决。东西向的上游字节读取 method MUST 标记为内部专用（前端不直连、边界不代理）。具体案例与内部鉴权范式见项目 overlay。

### 4.6 边界信任模型（项目 MUST 择一并落 ADR）

「谁负责解析凭证、谁的断言被下游信任」是架构选择，本规范**不预设也不强制**。两种模型都成立，代价不同。项目 MUST 在 ADR 中显式声明采用哪一种，MUST NOT 靠默认或惯例隐式确定。

| 维度 | 模型 A：per-service trust-root（无网关） | 模型 B：gateway trust-root（有网关） |
| --- | --- | --- |
| 凭证解析 | 每个服务各自解析并校验客户端凭证 | 边界网关统一解析校验，上游不再解 |
| 身份传递 | 无中间人——凭证本体透传到每个服务 | 网关注入可信 identity / scope header |
| 上游信任姿态 | 服务 MUST NOT 信任任何上游注入的身份 header | 上游 MUST 信任网关注入的 header，且 MUST NOT 接受来自网关以外来源的同名 header |
| 边界组件职责 | L7 路由与转发；MUST NOT 解析凭证、MUST NOT 注入身份头 | 认证、鉴权、白名单、身份注入、路由 |
| 主要代价 | 每服务重复认证成本；凭证扩散面更大 | 网关成为单点信任根；网关到上游的链路一旦可绕过即全线失守 |
| 适用信号 | 服务数量可控、团队自治、要求纵深防御 | 服务多、需统一接入策略、外部集成密集 |

**两种模型共同的 MUST**：

- 项目 MUST 在 ADR 中声明所采用的模型，并写明该选择的触发条件与退出条件。
- 稳态下同一部署单元内 MUST NOT 混用两种模型——混用会让「这个 header 可信吗」失去确定答案，属于安全语义级的分裂。切换期的临时并存 MUST 由切换 ADR 明确界定范围与截止条件（见下）。
- 采用模型 B 时，MUST 保证上游只能经网关到达（网络隔离、mTLS 或等价手段）；做不到则等同于「任何人都可伪造身份头」，该模型不成立。
- 采用模型 A 时，边界组件（反向代理 / 负载均衡）MUST NOT 解析凭证或注入身份头——一旦开始注入，实际已切换为模型 B 而 ADR 未更新，这是最危险的漂移形态。

**模型切换**（A ⇄ B，两个方向对称）是架构变更，MUST 走新 ADR 并作废旧 ADR。切换 ADR MUST 给出迁移方案：过渡期两种模型如何并存、身份 header 从何时起被信任（或停止被信任）、以及回滚路径。MUST NOT 通过逐服务改造静默完成切换——迁移期内「哪些服务已切」本身就是必须被记录的状态。

---

## 5. 共享库（Common Library）治理

目标：减少重复定义与重复实现，但不引入编译期 / 语义耦合。

### 5.1 SHOULD 放入共享库的内容

- 契约生成代码与基础类型（ID、枚举、分页、审计元数据、错误码等）
- 与领域无关的通用能力
  - 序列化 / 反序列化、校验器、加密 / 脱敏工具、时间 / ID 工具、客户端拦截器

### 5.2 MUST NOT / SHOULD NOT 放入共享库的内容

三者风险性质不同，强度不一刀切：

| 内容 | 强度 | 理由与例外路径 |
| --- | --- | --- |
| 授权决策规则与策略实现细节（如 PDP 的核心判断逻辑） | **MUST NOT** | 安全不变式：共享库内联判定即产生第二决策点，策略变更无法统一生效，决策也不再可追溯到单一 PDP。无例外 |
| 身份流程规则（去重、绑定、恢复、风控策略等） | **SHOULD NOT** | SoR 的领域逻辑一旦外泄成副本即有版本漂移风险。确需本地预校验以减少往返时 MAY 放入，但 MUST 记录漂移防护措施（版本绑定或定期核对） |
| 直接映射数据库表的 ORM Model | **SHOULD NOT** | 强绑定 schema 演进，会迫使跨服务同步发版，与 §5.3 相悖。紧耦合服务组有意接受同步发版时 MAY 放入，但 MUST 在 ADR 记录理由与退出条件 |

> 设计根据：本节列表本质是「防止共享库降级为浅模块」（[design-philosophy.md §3.2 浅模块气味](./design-philosophy.md#32-浅模块气味must-避免)）。共享库一旦统一服务内 ORM / PDP 规则，就会变成「接口规模 ≈ 实现规模」的浅包装，并把跨服务的 schema 变更耦合放大。

### 5.3 发布与依赖策略

- 共享库 MUST 版本化发布；各服务 SHOULD 被允许不同步升级
- 共享库 SHOULD 只对外暴露稳定契约层，否则会退化为「隐形单体」

---

## 6. 安全、合规与审计最低要求（跨服务一致）

- **最小权限**：Consumer 访问 Producer 复制源的账号 MUST 只授予复制所需权限；复制表在 Consumer 侧 MUST 只读
- **敏感数据最小化**：契约与复制面 MUST NOT 传播明文高敏字段；必要时 MUST 改用引用、哈希或域内驻留策略
- **可追溯**：关键写操作（授权 / 撤销 / 紧急访问 / 角色关键变更）MUST 落审计字段集合，并 MUST 可关联到主体的可验证身份
- **可复现**：关键决策 SHOULD 保留输入摘要、命中策略的版本引用、输出理由与义务（Obligations），用于回放与稽核

---

## 7. 参考落地：身份事实服务与授权决策服务（示例）

- 身份事实服务（Producer/SoR）
  - 归属：主体标识、组织与成员关系、身份绑定与签名能力
  - 输出：最小必要主体与关系索引（Read Model 发布表）
- 授权决策服务（Consumer/PDP）
  - 归属：Grant、Policy、Assignment、Share、Decision/Audit 明细
  - 输入：来自复制的主体/关系索引 + 本域授权事实 + 上下文属性
