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
- [ ] 该有的 `From`/`TryFrom`/`AsRef`/`AsMut` 都有？**绝不直接实现 `Into`/`TryInto`**——blanket impl 经 `From` 免费提供，直实现触发 `clippy::from_over_into`（默认警告）。（C-CONV-TRAITS）
- [ ] 方法命名一致（`new`/`with_*`/`into_*`/`as_*`/`to_*`）？
- [ ] **转换方法前缀符合成本-所有权矩阵**——`as_` 廉价（borrowed→borrowed，`as_bytes`）；`to_` 昂贵或产出 owned（`to_lowercase`）；`into_` 消费所有权（`into_bytes`）；`mut` 修饰按返回类型位置写（`as_mut_slice`，不是 `as_slice_mut`）；单值包装类型暴露内值用 `into_inner()`。（C-CONV）
- [ ] **getter 不带 `get_` 前缀**——`first()` 而非 `get_first()`；`get` 只用于「单一显然可取之物」（`Cell::get`）。带运行时校验的索引访问配齐 `get`/`get_mut`/`get_unchecked`/`get_unchecked_mut` 四件套。（C-GETTER）
- [ ] **访问器命名成套**——`foo()` / `foo_mut()` / `set_foo()` / `take_foo()`（取走并置默认）/ `replace_foo()`（换新返旧）/ `with_foo()` / `with_mut_foo()`（闭包作用域访问）。interior mutability 字段优先 `with_foo(|f| …)` 而非返回 `MutexGuard`——后者向下游泄漏实现细节。（Google）
- [ ] **fallible 构造器叫 `try_new()`**；重要的 `From` impl 配显式 `from_foo()` 构造器——`from_` 版本可以 unsafe、可带额外参数，`From` trait 不行。（C-CTOR）
- [ ] **enum 参数优先于 `bool` / 裸 `Option`**——`Widget::new(Small, Round)` 优于 `(true, false)`：核心类型语义多义，自定义类型传达解释且可扩展。（C-CUSTOM-TYPE）
- [ ] **标志集合用 bitflags 而非 enum**——互斥选择用 enum；可组合位标志用 `bitflags`。（C-BITFLAG）
- [ ] **实现同形 std trait 而非自定义方法**——`impl FromStr` 而非 `fn from_str()`。`clippy::should_implement_trait` 只覆盖固定 trait 清单，人审补清单外场景。（Google）
- [ ] **成套 API 一起出现**——`len`↔`is_empty`、`get`↔`get_mut`、`iter`/`iter_mut`/`into_iter` 三件套；迭代器返回类型名与方法匹配（`iter()` → `Iter`）。`len_without_is_empty`/`new_without_default` 机器已覆盖，三件套与类型名匹配靠人审。（C-ITER、C-ITER-TY）
- [ ] **trait 只为泛型约束 / `impl Trait` / `dyn` / extension trait 而定义**——不用 trait 组织代码；其余场合用 inherent impl。（Google）
- [ ] **智能指针不加大批 inherent 方法**——`Box::into_raw` 是关联函数而非 `self` 方法，避免与 pointee 方法在方法解析里混淆。（C-SMART-PTR）
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
- [ ] **错误类型实现 `std::error::Error` + `Send` + `Sync`**——不满足则 `thread::spawn` 返回、`Arc` 跨线程传递、`io::Error::new`（要求 `Error + Send + Sync`）全受阻。（C-GOOD-ERR）
- [ ] **没有 `Result<T, ()>`**——`()` 无 `Error`/`Display`，下游不能 `?`、不能 `From`、unwrap 出无意义 Debug；零信息错误也定义 unit struct 错误类型。（C-GOOD-ERR）
- [ ] **错误 `Display` 消息小写、无尾标点、简洁**——std 错误消息全部如此（"unexpected end of file"）；下游会把消息直接拼进自己的日志 / UI。（C-GOOD-ERR）
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
- [ ] **迭代器链 vs 手写循环按可读性与场景选，不按性能默认**——变换/组合用迭代器链；早退（`break`/`continue`/`return`）、简单副作用、可读性优先用手写 for；不在 for 头部拼长链（提为具名变量）；避免 `Iterator::for_each`。热路径取舍以 benchmark 为准——实证数据（rustc 1.99 / arm64）：`filter+map+sum` 链未获自动向量化，等价手写 for 被向量化、快 6.4×。（Google）
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
- [ ] **`Send`/`Sync` 契约有静态断言测试钉住**——`fn assert_send<T: Send>() {}` + `assert_send::<MyType>()`（`Sync` 同理）；含裸指针 / `Rc` / `Cell` 字段的类型靠它把回归拦在编译期。（C-SEND-SYNC）
- [ ] **不掏 poisoned mutex 的内部**——`PoisonError::into_inner` 不为拿数据冒险：中毒意味着另一线程在持锁时 panic，数据可能处于半更新态。（Google）
- [ ] **`Drop` 不阻塞**——析构里持锁、同步 IO、`join` 会卡住线程甚至死锁；阻塞型 Drop 是 dependability 缺陷。（C-DTOR-BLOCK）

## 6. Code Organization
- [ ] 模块层级清晰合理？
- [ ] 可见性（`pub`/`pub(crate)`/`pub(super)`）最小且有意？
- [ ] crate root 有为 public API 便利做的 re-export？
- [ ] `mod.rs` vs `module_name.rs` 风格一致？
- [ ] **没有 glob import**（`use foo::*`）——例外仅四处：内联模块 `use super::*`、enum 方法体内 `use Enum::*`、非叶模块 `pub use submodule::*` 合并 re-export、FFI 命名空间合并（合并产物 MUST NOT pub）。glob 让类型来源不可追踪、大规模重构困难。（Google）
- [ ] **trait 导入尽量局部化**——在函数体内 `use std::str::FromStr`，除非该 trait 的方法全文件高频使用。（Google）
- [ ] **非叶模块只放 `mod` 声明 + re-export，不实现 API**——少量「绑线」代码可接受，多了就是发现：结构与内容混杂，难找东西。（Google）
- [ ] **源文件 / 叶模块按其主要 user-defined item 命名**（`Foo` → `foo.rs`），文件用途一目了然。（Google）
- [ ] 可选功能用 feature flag？
- [ ] `#[cfg(test)]` 模块与实现就近放置？
- [ ] workspace 内 crate 间职责分明？

## 7. Rust Idioms
- [ ] 模式匹配穷尽且地道？
- [ ] 用 `Option` 组合子（`map`/`and_then`/`unwrap_or_else`）而非冗长 match？
- [ ] 迭代器适配器与手写循环的取舍遵循 §4 的可读性规则（早退 / 简单副作用 → for）？
- [ ] 解构用得到位？
- [ ] 恰当处用 `impl Trait` 作参数 / 返回？
- [ ] 复杂类型有 type alias？
- [ ] **类型推断没有过度省略**——`.into()` / `.parse()` / 复杂迭代链的结果在声明处标注类型（优于 turbofish）；不标的话，不熟代码的人无法推断出类型。（Google）
- [ ] 生产代码里没有 `todo!()`/`unimplemented!()`？
- [ ] `derive` 宏用得恰当？（具体陷阱见 §14）

## 8. Unsafe Code
- [ ] 每个 `unsafe` 块都有 `// SAFETY:` 注释说明理由？
- [ ] 不变量写清楚了？
- [ ] unsafe 表面最小化？
- [ ] 能用安全抽象替代的 unsafe 都替代了？
- [ ] unsafe trait 的实现正确？
- [ ] **每处 unsafe 能回答两个问题**——「为什么不能用安全代码实现」；「若动机是性能，benchmark 在哪」。理想上 unsafe 封装进低依赖的独立 crate、与业务逻辑隔离。（Google）
- [ ] FFI 边界做了输入校验？
- [ ] **`#[repr(packed)]` 字段用 `addr_of!`/`addr_of_mut!` 取引用，禁止裸 `&packed.field`**——对齐不保证，`&packed.field` 在多数平台是 UB，Clippy 默认抓不全。（Unsafe Code Guidelines）

## 9. Edge Cases & Robustness
- [ ] 所有边界情况都处理（空集合、`None`、溢出）？
- [ ] 整数溢出用 checked / saturating / wrapping 算术？
- [ ] 不会为零的值用 `NonZero*`？
- [ ] panic 路径文档化或消除？
- [ ] debug 构建用 `debug_assert!` 守不变量？
- [ ] **公开函数 fail-fast 校验参数**——public API 边界是错误面也是攻击面：空切片、负数、超长字符串、非法 UTF-8 等「显然不行」的输入应在入口就拒绝（`Err` 或 panic 看契约），而不是带到内部产生诡异现象。（C-VALIDATE）
- [ ] **不依赖 `panic::catch_unwind`**——`panic=abort` 环境下直接失效；防御性包裹必须论证「不依赖它提供任何性质」。（Google）
- [ ] **不在 `main()` 之前跑代码**——`ctor` 等手法破坏初始化顺序的可推理性。（Google）
- [ ] **拼接 >2 段字符串用 `format!` / `write!`**——`+` 链每级可能重分配（实测：4 段拼接 `+` 链 3 次分配 vs `format!` 2 次）。（Google）

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
- [ ] **示例用 `?` 而非 `unwrap` / `try!`**——示例会被逐字复制，unwrap 应是使用方的自觉决定；fallible 示例用隐藏模板 `# fn main() -> Result<(), Box<dyn Error>> { … }` 包裹（参与编译、不显示）。（C-QUESTION-MARK）
- [ ] **示例回答「为什么想用」而非机械演示调用**——`hello.clone()` 式示例零信息量；一处写透、他处链接即可。（C-EXAMPLE）
- [ ] **内部实现 impl 不出现在 rustdoc**——下游用不到的 `From<PrivateError>` 等标 `#[doc(hidden)]`，或干脆 `pub(crate)` 收编出公共 API 面。（C-HIDDEN）
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
- [ ] **feature 命名无占位词**——直接叫 `std`，不叫 `use-std` / `with-std`（与 optional dependency 隐式 feature 命名对齐）；负向命名（`no-abc`）几乎必错——Cargo feature 是加性的。（C-FEATURE）
- [ ] **（仅 `publish = true` 的 crate）发布面齐备**——`description` / `license` / `repository` / `keywords` / `categories` 元数据；发版有 release notes 且 breaking 显式标注；依赖保持宽松许可。内部 workspace crate（`publish = false`）标 N/A。（C-METADATA、C-RELNOTES、C-PERMISSIVE）
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
- [ ] **`Debug` 表示非空**——空概念值也输出 `""` / `[]` 而非空白；空 Debug 让下游日志抓瞎。（C-DEBUG-NONEMPTY）
- [ ] **公共数据类型优先命名字段而非元组**——`.0` / `.1` 索引很快失控；例外：单字段 newtype、极局部场景。（Google）
- [ ] **trait 实现细则**——错误类型能 `Copy` 就 `Copy`；给 `==` 用时先只实现 `PartialEq`（实现 `Eq` 需自觉承担反射律）；预计做 map key / 缓存键的类型实现 `Hash + Eq`，有清晰全序再加 `Ord`。（Google）
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

## 17. Macro Design（被审范围含 `macro_rules!` 定义或 proc-macro crate 时适用，否则标 N/A）

> 宏的「生成代码对用户的影响」在 [api-ergonomics-checklist §7](api-ergonomics-checklist.md)；
> 本节看宏自身的输入语法与可用性设计。

- [ ] **宏输入语法模仿其产出**——产出 struct 就带 `struct` 关键字、产出 const 用分号分隔；关键字与标点贴近将生成的代码，读者凭输入能猜到输出。（C-EVOCATIVE）
- [ ] **多产出宏支持逐 item 加属性**——每个产出 item 都能挂 `#[cfg]`、产出的 struct/enum 能接 `#[derive]`。（C-MACRO-ATTR）
- [ ] **item 宏在模块作用域和函数作用域都能用**——测试套里两处各调一次；`super::` 假设是常见翻车点（模块里展开正常、函数里失效）。（C-ANYWHERE）
- [ ] **item 宏支持可见性修饰符**——默认私有、写 `pub` 才公共，遵循 Rust 语法。（C-MACRO-VIS）
- [ ] **`$t:ty` 片段对全部类型形态可展开**——原始类型 / 相对路径 `m::Data` / 绝对路径 `::base::Data` / `super::Data` / 泛型 `Vec<String>`；把片段搬进新模块再引用是常见翻车点。（C-MACRO-TY）
- [ ] **宏是最后手段，优先级递减**——普通函数 / 类型 / trait > `macro_rules!` > 其他 codegen > proc_macro：每往下一级，IDE 与工具支持、跨代码库可移植性、大规模重构成本都变差。（Google）

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

**审查时主动确认的关键 lint**（前段默认 allow、最易被静默绕过；末两行默认
warn 已开启，属「机器已覆盖——确认没被 `#[allow]` 关掉」项）：

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
| `clippy::from_over_into` | §1 | 直接实现 `Into`——应实现 `From`（默认开，机器已覆盖） |
| `clippy::should_implement_trait` / `len_without_is_empty` / `new_without_default` | §1 / §14 | 同形 std trait、len↔is_empty、new↔Default 成套（默认开，机器已覆盖；iter 三件套命名等同类项靠人审） |

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
  `C-CALLER-CONTROL` / `C-NO-OUT` / `C-STRUCT-BOUNDS` / `C-CONV` / `C-GETTER` /
  `C-CTOR` / `C-CONV-TRAITS` / `C-CUSTOM-TYPE` / `C-BITFLAG` / `C-SMART-PTR` /
  `C-GOOD-ERR` / `C-DEBUG-NONEMPTY` / `C-FEATURE` / `C-INTERMEDIATE` / `C-BUILDER` /
  `C-GENERIC` / `C-CONV-SPECIFIC` / `C-NEWTYPE-HIDE` / `C-STABLE` / `C-RW-VALUE` /
  `C-QUESTION-MARK` / `C-EXAMPLE` / `C-HIDDEN` / `C-EVOCATIVE` / `C-MACRO-ATTR` /
  `C-ANYWHERE` / `C-MACRO-VIS` / `C-MACRO-TY` / `C-ITER` / `C-ITER-TY` /
  `C-METADATA` / `C-RELNOTES` / `C-PERMISSIVE`）
- **Google Rust Style Guide** — <https://google.github.io/styleguide/rustguide.html>
  （两份清单内标注「Google」条目的主源：getter/setter 命名表、trait vs inherent
  判定、代码组织与导入纪律、类型推断纪律、宏优先级梯子、const fn 责任等）
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
