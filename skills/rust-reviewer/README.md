# rust-reviewer

对 Rust 代码做结构化审查：lib crate 同时审代码质量与下游 API 人体工程学，bin crate 只审代码质量。

## 简介

- **按 crate 类型分流**：自动读 `Cargo.toml` 判定 lib / bin（同时含 lib + bin 的包按 lib 审——它对外暴露 public API），lib 多审一层 API 人体工程学。
- **code-review-checklist**（lib / bin 都审）：正确性、unsafe 安全性、性能、错误处理、所有权与生命周期、并发安全、命名、文档、测试、依赖、类型设计、异步、可观测性等 16 类；并入 Rust API Guidelines / Cargo SemVer / Unsafe Code Guidelines 权威口径。
- **api-ergonomics-checklist**（仅 lib）：站在**下游消费者**视角——happy-path 摩擦、下游编译器输出、类型系统拦不住的运行时意外、类型签名诚实性、命名语义精度、文档漂移、codegen 人体工程学，以及 semver 隐藏破坏面，共 8 类。
- **结构化输出**：发现按 Critical / High / Medium / Low 分级，每条带 `file:line`、影响说明与具体修复；lib crate 另附 8 维 API 健康速评表；末尾点名不应被回归的正确设计。

## 适用场景

即使用户只说「帮我 review 这段 Rust 代码 / 审查这个 crate / 看看这个模块写得怎么样 / 这 API 设计合不合理 / 帮我看看有没有 footgun」而未指明审查维度，也命中。不适用于非 Rust 代码、纯格式化或重命名等机械操作。

## 安装

```bash
# 安装到当前项目
npx skills add <owner>/my-skills --skill rust-reviewer

# 全局安装
npx skills add <owner>/my-skills --skill rust-reviewer -g -y
```

## 使用说明

本 skill 面向 AI Agent 自动执行（globs `**/*.rs`）。默认只审本次变更涉及的范围（diff / 指定文件 / 指定 crate），除非明确要求全量。与 fusions / axum-tower 等栈特定 skill 冲突时，技术栈项目以那些 skill 为准（本 skill 只管通用 Rust 维度）。

## 文件

```
rust-reviewer/
├── SKILL.md                            # 执行协议 + crate 类型判定 + 审查维度 + 输出格式
└── references/
    ├── code-review-checklist.md        # 16 类代码质量清单（lib / bin 都审）
    └── api-ergonomics-checklist.md     # 8 类下游 API 人体工程学清单（仅 lib）
```
