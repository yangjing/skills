# Code Review Checklist

通用 Rust 代码审查清单，lib / bin crate 都适用。逐项过，命中即记一条发现（带
`file:line`）。覆盖正确性、安全性、性能、可维护性。源出 rust-code-reviewer，
并入 Rust API Guidelines / Cargo SemVer / Unsafe Code Guidelines 的权威口径。

> 本清单只看代码本身的质量维度。若被审 crate 是 lib，**还要**叠加
> [api-ergonomics-checklist.md](api-ergonomics-checklist.md) 的下游消费者视角
> （含 semver 隐藏破坏面）。

## 1. API Design
- [ ] public API 直观且与 std / 生态惯例一致？
- [ ] trait bound 精选且最小？
- [ ] 泛型用得恰当，没有过度抽象？
- [ ] 复杂配置走 builder pattern / functional options？
- [ ] 该有的 `From`/`Into`/`TryFrom`/`TryInto` 都有？
- [ ] 方法命名一致（`new`/`with_*`/`into_*`/`as_*`/`to_*`）？
- [ ] 给外部类型加功能用 extension trait？
- [ ] 不应被外部实现的 trait 用 sealed trait？
- [ ] 向后兼容：non-exhaustive enum / 隐藏字段？
- [ ] **没有用 `impl Deref` 模拟「继承」**——`Deref` 只给智能指针（`Box`/`Rc`/`Arc`/`String`/`Vec`）。用 `Deref` 让 Wrapper 暴露内层方法会在方法解析、auto-deref、`&` 借用上行为诡异且语义错误。（API Guidelines C-DEREF）
- [ ] **运算符重载符合数学直觉**——`Add` 就是加法、`BitAnd` 就是按位与；运算符没有方法名提示，下游无法从 `a + b` 看出意外语义（如「拼接日志」），故禁止语义漂移。（C-OVERLOAD）
- [ ] **trait 的 object-safety 是有意决策**——这个 trait 会不会被 `dyn`？事后给 trait 加泛型方法 / 无默认值的关联类型 / 返回 `Self` 会让它失去 object-safety，是 major semver 破坏。设计期就定。（C-OBJECT）

## 2. Error Handling
- [ ] 所有错误路径都走 `Result`？
- [ ] 自定义错误类型结构良好（`thiserror` 或手写 `Error` impl）？
- [ ] `?` 传播时保留了上下文？
- [ ] 库代码里没有 `.unwrap()`/`.expect()`（测试 / 可证安全场景除外）？
- [ ] binary 用 `anyhow`，library 用类型化错误？
- [ ] 错误枚举 vs trait object 选择恰当？
- [ ] 有 `From<E>` 转换让 `?` 顺手？
- [ ] 区分了可恢复 vs 不可恢复错误？
- [ ] **`Drop::drop` 里不会 panic**——析构里 panic 会触发 double-panic → 进程 abort，无法挽回。析构必须 fail-safe。（C-DTOR-FAIL）

## 3. Ownership & Lifetimes
- [ ] 能借用就不 clone？
- [ ] 编译器能推断的地方省略了显式生命周期？
- [ ] 没有用 `.clone()` 掩盖所有权问题？
- [ ] 条件所有权用 `Cow<'_, T>`？
- [ ] `Arc`/`Rc` 只在真正需要共享所有权时用？
- [ ] 生命周期标注清晰且最小？
- [ ] 用 move 语义避免了拷贝？

## 4. Performance
- [ ] 热路径上没有多余分配？
- [ ] 用 iterator chain 而非手写循环？
- [ ] `collect()` 带类型提示和容量预分配（`Vec::with_capacity`）？
- [ ] 能用 `&str` 就不分配 `String`？
- [ ] `Box<dyn Trait>` vs 泛型的动态派发成本是否清楚？
- [ ] 小拷贝类型实现了 `Copy`？
- [ ] 库代码里小而高频的函数标了 `#[inline]`？
- [ ] 没有不必要的 async（async 有开销）？
- [ ] **没有双重间接 / 包装浪费**——`Vec<Box<T>>`、`Rc<String>`（多一次分配）、`Box<Vec<_>>` 这类组合通常是误用；审查时点出来。

## 5. Concurrency Safety
- [ ] `Send` / `Sync` bound 恰当？
- [ ] `Arc<Mutex<T>>` vs `Arc<RwLock<T>>` 选对了？
- [ ] 锁粒度小——临界区最小？
- [ ] 锁顺序有没有死锁风险？
- [ ] async 取消安全（drop guard、`select!` 行为）？详见 §15。
- [ ] tokio task spawn 后正确 join / abort？
- [ ] channel 选型（`mpsc`/`oneshot`/`broadcast`/`watch`）合适？
- [ ] 能用原子量就不用锁？
- [ ] **`Send`+`Sync` 作为库 API 契约**——下游会默认你的公共类型是 `Send + Sync`；一旦不是，下游的 `Arc<T>`、`tokio::spawn`、跨线程 channel 全受阻。做不到要在 docs 说明原因。（C-SEND-SYNC）
- [ ] **`Drop` 不阻塞**——析构里持锁、同步 IO、`join` 会卡住线程甚至死锁；阻塞型 Drop 是 dependability 缺陷。（C-DTOR-BLOCK）

## 6. Code Organization
- [ ] 模块层级清晰合理？
- [ ] 可见性（`pub`/`pub(crate)`/`pub(super)`）最小且有意？
- [ ] crate root 有为 public API 便利做的 re-export？
- [ ] `mod.rs` vs `module_name.rs` 风格一致？
- [ ] 可选功能用 feature flag？
- [ ] `#[cfg(test)]` 模块与实现就近放置？
- [ ] workspace 内 crate 间职责分明？

## 7. Rust Idioms
- [ ] 模式匹配穷尽且地道？
- [ ] 用 `Option` 组合子（`map`/`and_then`/`unwrap_or_else`）而非冗长 match？
- [ ] 用 iterator adaptor 而非手写循环？
- [ ] 解构用得到位？
- [ ] 恰当处用 `impl Trait` 作参数 / 返回？
- [ ] 复杂类型有 type alias？
- [ ] 生产代码里没有 `todo!()`/`unimplemented!()`？
- [ ] `derive` 宏用得恰当？（具体陷阱见 §14）

## 8. Unsafe Code
- [ ] 每个 `unsafe` 块都有 `// SAFETY:` 注释说明理由？
- [ ] 不变量写清楚了？
- [ ] unsafe 表面最小化？
- [ ] 能用安全抽象替代的 unsafe 都替代了？
- [ ] unsafe trait 的实现正确？
- [ ] FFI 边界做了输入校验？
- [ ] **`#[repr(packed)]` 字段用 `addr_of!`/`addr_of_mut!` 取引用，禁止裸 `&packed.field`**——对齐不保证，`&packed.field` 在多数平台是 UB，Clippy 默认抓不全。（Unsafe Code Guidelines）

## 9. Edge Cases & Robustness
- [ ] 所有边界情况都处理（空集合、`None`、溢出）？
- [ ] 整数溢出用 checked / saturating / wrapping 算术？
- [ ] 不会为零的值用 `NonZero*`？
- [ ] panic 路径文档化或消除？
- [ ] debug 构建用 `debug_assert!` 守不变量？
- [ ] **公开函数 fail-fast 校验参数**——public API 边界是错误面也是攻击面：空切片、负数、超长字符串、非法 UTF-8 等「显然不行」的输入应在入口就拒绝（`Err` 或 panic 看契约），而不是带到内部产生诡异现象。（C-VALIDATE）

## 10. Test Coverage
- [ ] `#[cfg(test)]` 模块里有单元测试？
- [ ] `tests/` 目录里有集成测试？
- [ ] public API 有 doc test（`///` 示例）？
- [ ] 复杂逻辑考虑了 property-based test（proptest / quickcheck）？
- [ ] 边界和错误路径测了？
- [ ] 测试 helper 减少了重复？
- [ ] 预期 panic 用了 `#[should_panic]`？
- [ ] async test runtime 配置正确？

## 11. Documentation
- [ ] 所有 public item 有 doc comment（`///`）？
- [ ] 模块级文档（`//!`）说明了用途？
- [ ] doc comment 里的示例能编译能跑？
- [ ] 有 `# Errors` 段说明何时返回 `Err`？
- [ ] 有 `# Panics` 段说明 panic 条件？
- [ ] unsafe 函数有 `# Safety` 段？
- [ ] 用 `` [`backtick`] `` 语法链到相关 item？

## 12. Security
- [ ] 没有不经论证的 `unsafe`？
- [ ] public API 边界做了输入校验？
- [ ] 不受信输入不会触发无限分配？
- [ ] 比较秘密用 timing-safe？
- [ ] 秘密不出现在 `Debug` 输出里？
- [ ] 秘密材料用 `zeroize` 清理？
- [ ] **`unsafe impl` 的类型上慎用 `#[derive(Deserialize)]`**——反序列化可绕过 unsafe 不变量构造非法状态；若必须 derive，文档标注并校验。（对应 `clippy::unsafe_derive_deserialize`）

## 13. Dependencies
- [ ] 外部依赖最小？
- [ ] 用 feature flag 避免拉入不必要的传递依赖？
- [ ] 适用处考虑了 `no_std` 兼容？
- [ ] 依赖版本的 semver range 合适？
- [ ] 依赖间没有功能重复？
- [ ] **MSRV 是显式契约**——`Cargo.toml` 写 `package.rust-version`；patch/minor 更新里不得偷偷抬高（用了新 std 特性要对锁老工具链的下游负责，Cargo 把 MSRV 抬升列为 possibly breaking）。
- [ ] **供应链审计工具配置到位**——CI 跑 `cargo-audit`（扫 RustSec 漏洞库）和 `cargo-deny`（advisories + **license 策略**防 GPL 误入 + **banned crates** + **duplicate 版本检测** + **source 限制**只允许 crates.io）；`advisories.ignore` 列表保持干净（已列未用的 ignore 也会报错，防豁免过期）。

## 14. Type Design
- [ ] 领域概念用 newtype（而非裸基本类型）？
- [ ] 状态机和封闭变体集用 enum？
- [ ] 编译期状态强制用 type-state pattern？
- [ ] 未用类型参数用 `PhantomData` 且有目的？
- [ ] 带不变量的类型用 `NonZero*`/`NonNull`？
- [ ] exhaustive vs non-exhaustive enum 是有意选择的？
- [ ] **公共类型的「常见 trait 完备性」审计**——下游会默认 `Debug`/`Clone`/`Eq`/`Hash`/`Default`「应该有」，缺了要绕。eagerly implement：语义合理就主动加，而不是用到再补。至少审 `Debug`（必须）、`Display`（有字符串形态时）、`Clone`/`Copy`（廉价时）、`PartialEq`/`Eq`/`Hash`、`Default`（有自然零值时）。（C-COMMON-TRAITS；数值 / 位标志类型顺带审 `LowerHex`/`UpperHex`/`Octal`/`Binary`，C-NUM-FMT）
- [ ] **数据类型 impl Serde**——配置 / DTO / 事件类型下游几乎一定序列化；不提供 `Serialize`/`Deserialize`，下游被迫包一层代理。（C-SERDE）
- [ ] **`#[derive]` 不手写重复 bound**——写 `#[derive(Clone)] struct Foo<T: Clone>` 是错的，derive 宏会自动加 `T: Clone` bound，手写一遍会让下游用更宽松类型时挂。同理 `Eq`/`Hash`/`PartialOrd`。（C-STRUCT-BOUNDS）

## 15. Async Patterns
- [ ] `async fn` vs 返回 `impl Future` 选对了？
- [ ] 跨线程的 future 标了 `Send` bound？
- [ ] 没有跨 `.await` 持锁？持锁跨 await 是 async 死锁头号来源（`clippy::await_holding_lock` / `await_holding_refcell_ref`）。
- [ ] 流处理模式（缓冲、背压）到位？
- [ ] 优雅关闭（graceful shutdown）处理了？
- [ ] 有超时和取消支持？
- [ ] **把每个 `.await` 当 drop 点**——`select!`/`timeout`/外部取消会 drop 进行中的 Future；若该 Future 此时持有锁、已写一半 buffer、处于「半应用」状态，会留下脏数据或丢公平队列位置。审查每个 await 点：不变量是否在「到此为止已全部生效」？
- [ ] **锁与取消的交互**——持锁跨 await 时 `std::sync::Mutex` 不可用（`await_holding_lock` 拦截）；改用 `tokio::sync::Mutex` 本身又是「这里取消不安全」的信号，要评估被取消时锁是否泄漏 / 临界区是否半完成。（RFD 400）

## 16. Observability
- [ ] `tracing` span / event 在恰当级别？
- [ ] tracing event 用了结构化字段？
- [ ] 错误日志带了上下文？
- [ ] 该埋的 metrics 暴露点有？

---

## 审查工具栏

审查时跑这些命令，并**确认关键 lint 没被 `#[allow]` 静默绕过**（本仓口径：裸
TODO 不许留，同源地，`#[allow(...)]` 应带 `= "reason"`）：

```bash
# 1. 编译告警全开
cargo clippy --all-targets --all-features --locked -- -D warnings

# 2. 库 crate 缺文档检查（lib.rs 顶上该有 #![deny(missing_docs)]）
cargo doc --no-deps --document-private-items

# 3. 供应链
cargo audit            # RustSec 漏洞
cargo deny check       # advisories + licenses + bans + duplicate sources
```

**审查时主动确认的关键 lint**（默认 allow、最易被绕过、且对应上面的硬规则）：

| Lint | 对应规则 | 一句话 |
| ---- | -------- | ------ |
| `clippy::await_holding_lock` / `await_holding_refcell_ref` | §15 | async 死锁头号来源 |
| `clippy::arithmetic_side_effects` | §9 | 未检查算术（溢出 / DoS 放大面） |
| `clippy::unwrap_used` / `expect_used` | §2 | 库公开路径不许 panic |
| `clippy::panic_in_result_fn` | §2 | 返回 Result 的函数里 panic 是反模式 |
| `clippy::missing_errors_doc` / `missing_panics_doc` / `missing_safety_doc` | §11 | `# Errors`/`# Panics`/`# Safety` 可机器化校验 |
| `clippy::must_use_candidate` / `return_self_not_must_use` | api-ergonomics §2 | 下游忽略返回值不报警 |
| `clippy::exhaustive_enums` / `exhaustive_structs` | api-ergonomics §8 | 公开 API 没加 `#[non_exhaustive]` 就警告 |
| `clippy::cast_possible_truncation` / `cast_sign_loss` / `cast_precision_loss` | §9 | 数值转型静默丢数据（加密 / 金额 / 索引） |
| `clippy::large_enum_variant` | §4 | enum variant 远大于其他 → 栈浪费，提示 `Box` |
| `clippy::allow_attributes_without_reason` | 全局 | `#[allow]` 必须带理由，防静默绕过 |
| `missing_docs`（rustc） | §11 | 公共 item 必须有 doc |

> 这些 lint 不是要求全开 deny，而是审查时**确认是否被有意处置**——要么开启，要么
> 带理由 `#[allow]`。`#[allow]` 裸写、`#[allow]` 在大范围（crate / module）无理由
> 地挂，本身就是一条发现。

---

## 输出注意

- 每类不强制逐条给结论——只对**命中的问题**输出发现，未命中不报流水账。
- 严重度见 [SKILL.md](../SKILL.md)「输出格式」第 2 节。
- 对 lib crate，本清单的 §1 API Design 与 api-ergonomics-checklist 视角互补：
  本节看「符不符合 Rust 惯例」，那边看「下游用着顺不顺手」——两者都报，但归到
  不同维度速评行。

## 权威依据

规则末尾的锚点用于溯源深读（稳定章节编号，非临时 URL）：

- **Rust API Guidelines** — <https://rust-lang.github.io/api-guidelines/checklist.html>
  （`C-DEREF` / `C-DTOR-FAIL` / `C-DTOR-BLOCK` / `C-SEND-SYNC` / `C-COMMON-TRAITS` /
  `C-NUM-FMT` / `C-SERDE` / `C-VALIDATE` / `C-OBJECT` / `C-OVERLOAD` /
  `C-CALLER-CONTROL` / `C-NO-OUT` / `C-STRUCT-BOUNDS`）
- **Cargo SemVer 兼容性** — <https://doc.rust-lang.org/cargo/reference/semver.html>
  （隐藏破坏面定义，api-ergonomics §8 主源）
- **Unsafe Code Guidelines** — <https://rust-lang.github.io/unsafe-code-guidelines/>
  （`repr(packed)` 引用 UB 等）
- **RFD 400: Cancel Safety in Async Rust** — <https://rfd.shared.oxide.computer/rfd/0400>
  （`std::sync::Mutex` vs `tokio::sync::Mutex` 取舍，§15）
- **Clippy Lint Master List** — <https://rust-lang.github.io/rust-clippy/master/>
  （「审查工具栏」表中 lint 释义）
- **RustSec** <https://rustsec.org/> · **cargo-deny** <https://embarkstudios.github.io/cargo-deny/>
  （供应链审计，§13）
- **cargo-semver-checks** — <https://github.com/obi1kenobi/cargo-semver-checks>
  （机器化检出 semver 破坏，api-ergonomics §8）
