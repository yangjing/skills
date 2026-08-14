# API Ergonomics Checklist

站在**下游消费者**视角审查 lib / framework 的 public API。源出
rust-api-ergonomics-reviewer，并入 Rust API Guidelines 的 interoperability /
flexibility / future-proofing 维度。**仅适用于 lib crate**——bin crate 没有下游
消费者，不审本清单。

> 立场：你的职责不是找测试能查出的 bug，而是找下游用户第一次集成这个 crate 时
> 会绊倒、眯眼、不得不读源码才能理解的东西。把自己代入「第一次把这个 crate 接
> 进自己项目的人」。

## 1. Happy-path friction

把最常见的用法逐字写出来，数 ceremony：

- [ ] 导入数量合理？该 re-export 到 crate root 的东西 re-export 了？
- [ ] 「我拿到值」到「我返回它」之间的包装层（`Ok(...)`/`.into()`/`Box::pin(...)`/
      类型标注）层数合理？
- [ ] `..Default::default()` 能用，还是类型 `#[non_exhaustive]` 必须先 default 再
      mutate？doc 有没有老实说明是哪种？
- [ ] 80% 场景有 one-liner 构造器，还是每个调用方都得拼同一个三字段 builder？
- [ ] **调用方控制分配与摆放**——接收 `&str` 而非 `String`、`AsRef<Path>` 而非
      `PathBuf`、不在库内部主动 clone；避免 out 参数（传 `&mut Vec` 收结果）改用
      返回值。把「要不要拷贝 / 拷到哪」的决定权交给调用方。（C-CALLER-CONTROL、C-NO-OUT）

> 红线：如果「最短的正确写法」比「看起来对但其实是错的写法」还长，必报。

## 2. Downstream compiler output

用户编译的是**他们自己的 crate**，不是这个 crate。落到他们终端的是什么：

- [ ] 在 **impl 站位**（而非 trait 定义站位）触发的 lint——`refining_impl_trait`、
      `async_fn_in_trait`、`private_bounds`？workspace 级 `allow` 对他们无效。
- [ ] bound 写错时的类型错误：把错误版本写出来读一遍，修复路径能不能从消息里推
      出？还是消息里提到一个他们闻所未闻的内部类型？
- [ ] 容易在链中段被 drop 的 builder 标了 `#[must_use]`？
- [ ] `#[deprecated]` 指向了替代品？

## 3. Runtime surprises the type system doesn't prevent

- [ ] builder 方法有没有在非法输入时 **panic**（伪装的 `TryInto`）？有没有 fallible
      兄弟方法？panic 在**调用点**文档化了吗（而非三跳之外）？
- [ ] 跨配置的行为不对称：某个方法对一种 codec / protocol / feature 能用，对另一
      种就报错，而签名里毫无警示——用户在生产环境吃 500 才发现？
- [ ] 任何 map-like 东西的 `.append` vs `.insert` 语义？如果 `with_foo` 是累加的，
      说清楚。
- [ ] builder 的顺序依赖：`.a().b()` 和 `.b().a()` 行为不同？整体替换型方法会
      静默丢弃之前的调用？

## 4. Type-signature honesty

- [ ] 有没有 doc-only 的不变量其实能用类型系统表达？（「实现必须产生能解码为 `M`
      的字节」是契约——考虑 sealed trait / newtype / associated-type bound 来承载。）
- [ ] doc 叫你别碰的 public 字段——要么强制（私有 + accessor），要么承认暴露。
- [ ] `'static` bound 以后会放松成 `'a`——指出后续会有一次破坏性变更，或一次两都落地。
- [ ] 返回位置的 `impl Trait`：rust-analyzer hover 里用户看到什么？一个没有方法的
      不透明类型是死胡同。

## 5. Naming & semantic precision

- [ ] 错误码 / variant 选择：这是 `Internal`（我们坏了）还是 `Unimplemented`
      （你要的东西我们不做）还是 `InvalidArgument`（你坏了）？区别决定用户是重试、
      提 bug、还是改自己的代码。
- [ ] `new` vs `with_*` vs `from_*` vs `build`——crate 内是否一致？
- [ ] public 名字里的缩写和行话。`ctx`/`req`/`resp` 没问题；项目内部代号不行。
- [ ] 名字和 std / 生态同类对得上吗？用户靠 `Cow`/`Arc`/`IntoIterator` 做模式匹配；
      一个「差一点点」的 `MaybeBorrowed` 应该说明它和 `Cow` 哪里不同。

## 6. Documentation drift & honesty

- [ ] 「后续会加 X」——本 PR 是不是那个后续？过期的将来时比没注释更糟。
- [ ] intra-doc 链接能不能解析（`[`ForeignType::method`]` 指向非依赖）？
- [ ] 示例能不能对当前 API 编译。doc-test 能抓一部分；指南里的散文片段一个都抓不到。
- [ ] CHANGELOG 迁移指引：用户能机械地照做，还是只描述了新形状？

## 7. Generated-code ergonomics（codegen crate 适用）

> 若被审 crate 不含 derive 宏 / 不自动生成类型，本节标 N/A，不强制。

- [ ] 用户 `cargo doc` 里生成的类型长什么样？trait bound 可读，还是一墙
      `Pin<Box<dyn Stream<Item = Result<...>>>>`？该给 type alias。
- [ ] 生成的代码会不会在用户 crate 里触发 lint（`clippy::use_self`、未用 variant
      的 `dead_code`）？他们改不了生成的代码。
- [ ] 多文件 / 多包产出：两个输入引用同一类型时，会不会在他们 crate 里产出重复
      impl（E0119）？

## 8. Semver 兼容性（隐藏破坏面）

库的每次改动都要问：这看起来是 minor / patch，但对下游是不是 major？Cargo 官方
semver 指南列了一堆「非显而易见破坏」，库作者极易踩。**这是本清单的最大议题**——
SemVer 表面是版本号，实质是「下游会不会被你的改动 break」。

逐条审本次变更是否触发：

- [ ] **给 trait 加带默认实现的方法**——可能与下游已 impl 的另一个同名 trait 冲突，
      编译报「multiple applicable items in scope」。
- [ ] **给类型加 inherent 方法**——可能撞上下游已 impl 的 trait 方法签名，静默改变
      运行时行为。
- [ ] **收紧泛型 bound**（`Foo<A>` → `Foo<A: Eq>`）——下游用不满足的类型直接挂。
- [ ] **给「全是 pub 字段」的 struct 加字段**——下游字面量构造 `Foo { x: 1 }` 失败；
      只有当 struct **已有**至少一个私有字段 / 标了 `#[non_exhaustive]` 时才安全。
- [ ] **事后补 `#[non_exhaustive]`**——本身就是 major 破坏，必须在初次创建时加。
- [ ] **改 `repr` 属性**（packed / C / transparent）——破坏 FFI、`size_of`、
      `transmute` 假设。
- [ ] **RPIT 捕获的泛型参数变化**——edition 2024 的 `+ use<...>` 语义；返回
      `impl Trait` 捕获的生命周期变了会破坏下游。
- [ ] **Cargo feature 移除 / 改 `default` feature**——下游 `Cargo.toml` 隐式失效。
- [ ] **MSRV 抬升**——对锁老工具链的下游是 breaking（见 code-review §13）。

> 工具辅助：`cargo-semver-checks` 能机器化检出大部分隐藏破坏；CI 接入可把本节
> 从人工审变成自动门禁。审查时确认是否接入。

---

## 不该花时间的地方

- 测试套件或一致性套件会抓的正确性 bug——假设它们跑过了。
- 性能——除非 API 形状**强迫**用户做一次无法避免的分配 / 拷贝。
- 内部（`pub(crate)`）代码风格——除非它泄漏进了 public 错误消息或文档。
- unsafe 健壮性——那是 code-review-checklist §8 的赛道。

## 与 code-review-checklist 的分工

| 维度 | 本清单看 | code-review-checklist 看 |
| ---- | -------- | ------------------------ |
| API Design | 下游用着顺不顺手、会不会踩、会不会被 break（semver） | 符不符合 Rust 惯例（sealed trait / non-exhaustive / 命名一致性 / Deref / 运算符） |
| 错误 | 错误码语义对用户的指引（retry / fix / report） | 错误结构、`?` 传播、`unwrap` 滥用、Drop fail-safe |
| 性能 | API 形状强迫的不可避免分配 | 热路径分配、iterator 选用、双重间接 |
| 文档 | 漂移、示例可编译、迁移可机械执行 | public item 是否有 doc、`# Errors`/`# Panics` 段齐不齐 |
| Semver | 隐藏破坏面（本清单 §8 独占） | MSRV 契约（§13）、供应链工具（§13） |

> 同一个问题不要在两份清单里各报一遍——归到更贴切的那个维度速评行。
