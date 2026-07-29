# axum-tower

在 Rust 项目中编写或评审 HTTP Web 服务代码时的 axum 0.8 + tower 模式速查与规范。

## 简介

覆盖基于 axum / tower / hyper 构建 HTTP 服务的核心模式：

- **Axum 0.8**：handler / extractor 组合规则、`Router` 路由（`/{id}`、`/{*rest}` 新语法）。
- **Tower**：中间件栈 `Layer` / `Service` / `ServiceBuilder`、layer 执行顺序语义。
- **横切能力**：超时 / 限流 / CORS / 压缩 / 错误传播（`?` + `From<T> for AppError`）。
- **Common Mistakes**：路由旧语法 panic、`Rc<T>` in State、async 中 blocking、SSE 套压缩层、裸 `JoinHandle` 泄漏等高频陷阱及正确写法。

本文示例为**通用 axum 形态**；使用 Fusion 技术栈的项目请以 [`fusions`](../fusions/SKILL.md) skill 的覆盖约定为准。

## 适用场景

- 编写 / 评审 axum、tower、hyper Web 代码
- "加个 HTTP 接口 / API 端点 / 中间件"——即使未点名 axum 也触发
- handler 报天书 trait 错误、middleware 顺序推导不出来、extractor 组合拿不准

**不适用于**：ConnectRPC 服务装配与 Fusion 技术栈的 handler 状态注入（以 fusions skill 为准）、纯前端代码。

## 安装

```bash
# 安装到当前项目
npx skills add <owner>/my-skills --skill axum-tower

# 全局安装
npx skills add <owner>/my-skills --skill axum-tower -g -y
```

## 使用说明

本 skill 面向 AI Agent 自动加载，默认 `**/*.rs` 文件触发。

- 速查：路由参数语法、handler 签名、middleware 组合见 `SKILL.md` 的 Quick Reference 与 Core Patterns。
- 深入：按需加载 references——
  - handler 签名 / extractor 组合 / Router 嵌套 / SSE / WebSocket / 文件上传 → [`references/axum.md`](references/axum.md)
  - 自定义 Layer / Service 实现 / middleware 执行顺序 / tower-http 组件配置 → [`references/tower.md`](references/tower.md)

## 关键约定

| 项目 | 正确 |
|------|------|
| 路由 | axum 0.8 用 `/{id}` / `/{*rest}`；旧 `/:id` / `/*rest` 直接 panic |
| State | `Arc<T>`，不要用 `Rc<T>` |
| async 中的 blocking | `spawn_blocking`（已开跑的 blocking 任务不可 abort） |
| handler 中的 `unwrap()` | 用 `?` + 错误转换 |
| SSE / 长流式响应 | 不要套 CompressionLayer / TimeoutLayer，用 `NotForContentType` 排除或单独挂路由 |
| `reqwest::Client` | 进程级复用单例（内部已是 Arc + 连接池），单请求超时用 `RequestBuilder::timeout` |

## 目录结构

```
axum-tower/
├── SKILL.md              # 执行协议 + Quick Reference + Core Patterns + Common Mistakes
├── references/
│   ├── axum.md           # handler/extractor/Router/SSE/WebSocket/上传具体形态
│   └── tower.md          # 自定义 Layer/Service、执行顺序、tower-http 配置细节
└── evals/
    └── evals.json
```
