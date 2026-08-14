---
name: rust-reviewer
description: >
  在 Rust 项目中评审 / review / code review / 审查 Rust 代码时使用：库（lib）crate
  同时审查代码质量与下游 API 人体工程学，二进制（bin）crate 只审查代码质量。涵盖
  正确性、unsafe 安全性、性能、错误处理、所有权与生命周期、并发安全、API 设计、
  命名、文档、测试——即使用户只说「帮我 review 这段 Rust 代码 / 审查这个 crate /
  看看这个模块写得怎么样 / 这 API 设计合不合理 / 帮我看看有没有 footgun」而未指明
  审查维度。自动按 Cargo.toml 判断 lib / bin 加载不同清单。不适用于：非 Rust 代码、
  纯格式化或重命名等机械操作。
globs:
  - "**/*.rs"
---

# Rust Code Reviewer

对 Rust 代码做结构化审查。按 crate 类型加载不同清单：lib crate 多审一层下游 API
人体工程学，bin crate 只审代码质量。

## Skill 执行协议

1. **Trigger**：评审 / review / 审查 Rust 代码（单个文件、模块、crate 或整个
   workspace）时使用本 skill。
2. **Classify**：先判定 crate 类型（见下「判定 crate 类型」）。这一步**先于**
   审查——它决定加载哪份清单。
3. **Load**：按判定结果读 references：
   - **lib crate** → 读 [code-review-checklist](references/code-review-checklist.md)
     **和** [api-ergonomics-checklist](references/api-ergonomics-checklist.md)
   - **bin crate** → 只读 [code-review-checklist](references/code-review-checklist.md)
4. **Apply**：按清单逐项审查，每条发现引用 `file:line`。
5. **Scope**：只审本次变更涉及的范围（diff / 指定文件 / 指定 crate）；除非用户
   明确要求全量审查，不扩散到未变更代码。
6. **Conflict**：与 fusions / axum-tower 等栈特定 skill 冲突时，技术栈项目以
   那些 skill 为准（本 skill 只管通用 Rust 维度）。

## 判定 crate 类型

按以下顺序判断，命中即停：

| 判定 | 依据 | 加载清单 |
| ---- | ---- | -------- |
| **lib** | `Cargo.toml` 含 `[lib]` 段，或存在 `src/lib.rs`，或 `[lib] crate-type` 含 `lib` / `cdylib` / `staticlib` / `rlib` / `proc-macro` | code-review **+** api-ergonomics |
| **bin** | 仅有 `src/main.rs` 或 `[[bin]]` 段，无 lib target | 仅 code-review |

在目标 crate 根目录执行，看清 target 结构：

```bash
grep -nE '^\[lib\]|^\[\[bin\]\]|^crate-type' Cargo.toml
ls src/lib.rs src/main.rs 2>/dev/null
```

> **同时含 lib + bin 的包**（workspace 成员常见）按 **lib** 审查——它对外暴露
> public API，api-ergonomics 适用。可只针对 lib 部分审 API 人体工程学，bin 部分
> 按需补 code-review。

## 审查维度速览

### code-review-checklist（lib / bin 都审）
正确性、错误处理、所有权与生命周期、性能、并发安全、代码组织、Rust 惯用法、
unsafe 安全性、边界情况、测试覆盖、文档、安全、依赖、类型设计、异步模式、
可观测性。共 16 类，详见 [references/code-review-checklist.md](references/code-review-checklist.md)。

### api-ergonomics-checklist（仅 lib）
站在**下游消费者**视角：happy-path 摩擦、下游编译器输出、类型系统拦不住的运行时
意外、类型签名诚实性、命名与语义精度、文档漂移、codegen 人体工程学，以及
**semver 隐藏破坏面**（最大议题）。共 8 类，详见
[references/api-ergonomics-checklist.md](references/api-ergonomics-checklist.md)。

> api-ergonomics 的核心立场：你的职责不是找测试能查出的 bug，而是找下游用户会
> 绊倒、眯眼、不得不读源码才能理解的东西。

## 输出格式

统一用以下结构（合并两份清单的发现，不重复列同一问题）：

### 1. 概要
- crate 名 + 判定类型（lib / bin）+ 审查范围（diff / 文件 / 全量）。
- 总体评价 1–2 句。

### 2. 发现（按严重度分级）
分 **Critical / High / Medium / Low** 四档。每条：
- **一句话陈述**用户 / 维护者的实际体验。
- `file:line`。
- **为什么重要**（从 correctness 或 consumer 视角，注明来自哪份清单）。
- **具体修复**，或无干净方案时的取舍。

> 严重度口径：Critical = 正确性 / 安全 / 数据损坏；High = 下游必踩 / 明显 bug；
> Medium = 摩擦 / 可维护性；Low = 风格 / 微优化。

### 3. 维度速评（仅 lib crate）
对 api-ergonomics 的 7 个维度各给一个速评（✓ 良好 / ~ 有保留 / ✗ 有问题），
让 API 健康度一目了然：

| 维度 | 速评 |
| ---- | ---- |
| Happy-path friction | |
| Downstream compiler output | |
| Runtime surprises | |
| Type-signature honesty | |
| Naming & semantic precision | |
| Documentation drift | |
| Generated-code ergonomics | |
| Semver 兼容性（隐藏破坏面） | |

> 若该 lib 不含 codegen（无 derive 宏 / 无自动生成类型），Generated-code 行可标
> N/A。**Semver 行对所有 lib crate 都必审**——它是「下游会不会被你的改动 break」
> 的底线，不是可选项。

### 4. Positive Observations
具体指出做得对、不应被回归的设计（「`Response::ok(body)` 省掉了 `.into()` 尾巴」
有用；「API 设计得好」没用）。

---

篇幅控制：发现条目聚焦可执行项；若无 Critical / High，直说并停。

## Related Skills

- `rust-best-practices` skill：通用 Rust 惯用法参考（写代码时；按 skill 名发现加载，未必与本文同处安装）
- [`fusions`](../fusions/SKILL.md)：Fusion 栈核心库模式（fusions 技术栈项目以其为准）
- [`axum-tower`](../axum-tower/SKILL.md)：axum + tower Web 代码模式
