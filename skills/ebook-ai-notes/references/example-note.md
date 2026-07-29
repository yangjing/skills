# 示例：一份完整的微信读书 AI 大纲笔记（范文）

> 这是 `SKILL.md` 中提到的完整范文，供 pattern-match。基于一本真实技术书（《AI Agents in Action》第 1 章）精简而成，展示完整的 5 段结构、图表/代码/术语的处理方式。生成笔记时以此为骨架，内容忠实于你正在精读的书。

---

# 第 1 章 · 智能体的崛起（The Rise of AI Agents）

> 本章是全书导论。核心问题：当 LLM 应用从"被动应答"走向"主动完成任务"时，如何定义 agent、它由哪些功能层构成、如何用 MCP 连接工具、如何从单智能体扩展到多智能体。本章是全书的概念地图。

**本章覆盖**：定义 agents 与智能体式思维 / 引入 MCP / 理解智能体的五大功能层 / 迈向多智能体系统

---

## 🔑 一句话精要

自主性（autonomy）与持续性（persistence）把系统从"被动助手"变成"主动智能体"。全书以**智能体的五大功能层**为主线，把读者从 prompt 调参者引向 agent 架构师。

---

## 📑 分节精要

### 1.1 定义智能体与智能体式思维

- **agent（智能体）** 在 AI 中并非新概念。跨各种传统的共同核心定义：**感知环境 → 决定做什么 → 采取行动以达成目标**。
- **agentic（智能体式的）** 描述展现 agency（自主性）的系统——在追求目标时具备感知、决策、行动的一定自主度。
- 与 AI assistant 的关键区别：助手回复一个 prompt 即停；agent 围绕目标跨越多个步骤工作，依据观察自主决定下一步。

#### 1.1.1 四种 LLM 交互模式（Table 1.1 核心）

> 图表是高密度信息，**必须提取**。这里把 Table 1.1 转成 markdown 表格，保留核心列。

| 模式 | 批准方式 | 自主度 | 典型用途 | 示例平台 |
|---|---|---|---|---|
| Direct LLM chat（直接聊天） | 不调用工具，仅生成文本 | 无 | 问答、起草、头脑风暴 | 初代 ChatGPT、早期 Claude |
| Tool-augmented LLM（工具增强） | 隐式按调用 | 低 | 图像生成、网页搜索 | 配 DALL·E 的 ChatGPT |
| Assistant（助手） | 按任务批准 | 中 | 结对编程、文档编辑 | Copilot Chat、Cursor |
| **Agent（智能体）** | 目标级批准 + 高风险动作设门禁 | 高 | 多步研究、仓库级重构 | Claude Code、Operator、Devin |

> ⚠️ 实践中 assistant 与 agent 是一个**光谱**而非硬边界。生产 agent 几乎都实现分级 human-in-the-loop 控制：低风险自主、中风险确认、高风险（发邮件、购买、删记录）必须显式批准。"自主"指能独立规划执行多步工作，**不等于**无人监督。

#### 1.1.2 SPAL 循环：感知-规划-行动-学习

```
sense（感知）→ plan（规划）→ act（行动）→ learn（学习）
   ↑_______________________________________|
```

- **SPAL 循环**是 agent 完成多任务目标的内部机制，呼应经典 AI 的 **OODA loop**（observe-orient-decide-act）、**BDI 架构**（信念-愿望-意图）。
- 适配到 LLM agent：sense ↔ 输入与上下文处理；plan ↔ LLM 推理；act ↔ 工具执行；learn ↔ 输出评估与记忆更新。

---

### 1.2 引入模型上下文协议（MCP）

- **MCP** 由 Anthropic 开发，2024 年 11 月发布，基于 **JSON-RPC 2.0** 的开放标准。被称为 **"USB-C for LLMs and agents"（LLM 的 USB-C）**。
- **连接流程**：启动 server → 向 agent 注册 → agent 先调 `list_tools` 获取可用工具 → 决定用哪个 → 执行 → 从结果学习 → 汇总最终输出。
- ⚠️ **安全与信任**：连接 MCP server 暴露了 agent 可自主调用的执行端点，server 是运行时的特权面。应把 MCP server 当作可信依赖：审查来源、锁定版本、最小权限运行、沙箱部署。

---

### 1.3 智能体的五大功能层

```
┌─────────────────────────────────────┐
│  Evaluation and feedback（评估与反馈）│
├─────────────────────────────────────┤
│  Knowledge and memory（知识与记忆）   │
├─────────────────────────────────────┤
│  Reasoning and planning（推理与规划） │
├─────────────────────────────────────┤
│  Tools and actions（工具与行动）      │  ← 核心三层（几乎所有 agent 必备）
├─────────────────────────────────────┤
│  Persona（人设）                      │
└─────────────────────────────────────┘
```

> 💡 **关键提醒**：并非所有 agent 都需要每一层；核心三层（persona、tools、reasoning）对几乎所有 agent 必不可少。**这些层不是固定自上而下的调用顺序**，而是在 agentic loop 中持续交互。

---

## 📚 关键术语表

> 中英对照表是「微信读书 AI 大纲」的标志性元素，帮助读者建立术语映射。

| 英文 | 中文 |
|---|---|
| agent | 智能体 |
| agentic / agency | 智能体式的 / 自主性 |
| assistant | 助手 |
| tool chaining | 工具链式调用 |
| SPAL cycle | 感知-规划-行动-学习循环 |
| OODA loop / BDI | 观察-定向-决定-行动 / 信念-愿望-意图架构 |
| MCP (Model Context Protocol) | 模型上下文协议 |
| persona / system prompt | 人设 / 系统提示词 |
| knowledge / memory | 知识（静态）/ 记忆（动态） |
| context window | 上下文窗口 |
| RAG | 检索增强生成 |
| guardrails | 护栏 |
| agentic loop | 智能体循环 |

---

## 💎 金句 / 重要观点

> 每条「加粗观点 + 简短解释」，3-6 条最值得记住的。

1. **自主性与持续性是 assistant 与 agent 的分水岭**——"autonomous"指能独立规划执行多步工作，不等于无人监督；生产 agent 几乎都设分级 human-in-the-loop 门禁。

2. **SPAL 循环是 agent 的内部引擎**，把经典 AI 范式适配到 LLM agent：sense↔输入上下文、plan↔LLM 推理、act↔工具执行、learn↔输出评估与记忆更新。

3. **MCP 是"LLM 的 USB-C"**——把工具集成从"每个 agent 做一次"变为"每个集成做一次"的共享可复用层；但 server 是运行时特权面，须当可信依赖对待。

4. **五个功能层是全书主线，但不是固定调用顺序**——分层图只组织能力，运行时各层在 agentic loop 中持续交互；核心三层（persona、tools、reasoning）几乎所有 agent 必备。

5. **多智能体：用最便宜够用的模式，而非最强大**——成本是一等关注；协作模式强大但话多重复、效率低、昂贵，仅在否则无法解决时使用。
