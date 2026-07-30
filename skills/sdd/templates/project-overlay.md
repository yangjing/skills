---
overlay-for: sdd
purpose: 登记本项目对 SDD 通用规范的取值、落点与例外，供 sdd skill 各分册引用
ssot: 本文件只登记项目侧取值与指针；通用规则正文留在 skill `references/`，MUST NOT 在此复制
---

# <项目名> — sdd 项目 overlay

> skill 主入口：[`SKILL.md`](sdd/SKILL.md) · 分册总览：[`sdd-overview.md`](sdd/references/sdd-overview.md) · 栈适配层：[`stacks/`](sdd/stacks/README.md)

本文件是本仓对项目中立 sdd skill 的 overlay。**只登记 [sdd-overview §2](sdd/references/sdd-overview.md#2-项目-overlay-边界) 禁止写入 skill 的内容**：真实路径、包名、命令、专属词表、当前阶段的兼容性放宽。

放置位置 MUST 为 skill 安装目录同级，文件名 MUST 为 `sdd.overlay.md`（自动发现依赖该命名）。

> 标注 **TODO** 的条目随对应设施建立后补充；未覆盖处以 skill `references/` 通用规范为准。

## 1. 技术栈声明

登记本项目使用的栈，决定加载哪些 [`stacks/`](sdd/stacks/README.md) 适配层。

| 维度 | 本项目选型 | 适配层 |
| --- | --- | --- |
| 契约与 RPC | `<例：Protobuf + ConnectRPC>` | `stacks/protobuf-connectrpc.md` |
| 后端语言 + 数据库 | `<例：Rust + PostgreSQL>` | `stacks/rust-postgres.md` |
| 前端框架 | `<例：React 19 + TanStack + antd 6>` | `stacks/react-tanstack-antd.md` |

栈不在 `stacks/` 表内时，MUST 按 [stacks/README §2](sdd/stacks/README.md#2-新增一个适配层) 新建适配层，MUST NOT 在本文件里硬套默认基线栈的 API。

## 2. 目录与路径取值

| 类别 | 本项目路径 |
| --- | --- |
| 契约根目录（IDL / schema / fixtures） | `<例：contracts/>` |
| 规格根目录 `<specs-root>` | `<例：docs/specs/>` |
| 设计文档根目录 | `<例：docs/designs/>` |
| 后端进程单元 / 共享库 | `<例：bins/ ↔ crates/>` |
| 前端应用 / 共享包 | `<例：apps/ ↔ packages/>` |
| 测试落点 | `<例：tests/>` |

## 3. 命令与门禁

SDD 各分册中以「项目 overlay 声明的命令」表述之处，在此固化：

| 用途 | 命令 |
| --- | --- |
| 契约 lint | `<例：buf lint>` |
| 契约兼容性检查 | `<例：buf breaking>` |
| 契约代码生成 | `<例：buf generate>` |
| 生成产物一致性校验 | `<TODO>` |
| 数据库重建 | `<TODO>` |
| 全量门禁 | `<TODO>` |

## 4. 受控词表与扩展流程

[naming-conventions](sdd/references/naming-conventions.md) 要求扩展词表 MUST 走变更提案。本项目的落点：

| 项 | 真相源 / 流程 |
| --- | --- |
| 权限码 action 词表 | `<file>` |
| 业务术语表 | `<file>` |
| 枚举落库形态约定 | `<file>` |
| 扩展提案流程 | `<流程或文档>` |

## 5. 架构裁决登记

各分册要求「项目 MUST 择一并落 ADR」的选择，在此登记裁决与 ADR 编号：

| 裁决项 | 本项目选择 | ADR |
| --- | --- | --- |
| 边界信任模型（[service-dependency-contract §4.6](sdd/references/service-dependency-contract.md#46-边界信任模型项目-must-择一并落-adr)） | `<模型 A / 模型 B>` | `<ADR-NNNN>` |
| 服务依赖形态（独立库 + 复制 / 在线调用） | `<选择>` | `<ADR-NNNN>` |
| 协议例外通道登记表 | `<file>` | — |

## 6. 兼容性阶段

| 项 | 当前口径 | 解除条件 |
| --- | --- | --- |
| 是否已发布 1.0 | `<是 / 否>` | — |
| 兼容窗口放宽 | `<例：未发布 1.0 前内部契约可重用字段号>` | `<发布 1.0>` |

## 7. 文档体裁归类

[SPECIFICATION §4.1.1](sdd/references/SPECIFICATION.md#411-体裁边界本结构的适用范围) 要求「项目侧各目录文件的逐份归类由项目 overlay 登记」：

| 目录 | 体裁 | 结构要求 |
| --- | --- | --- |
| `<specs-root>/<system>/main.md` | ① 功能 / 系统规格 | §4.1 全结构 + §4.2 BDD |
| `<specs-root>/README.md` | ② 总纲 / 索引 | 仅文档控制字段 + 指针纪律 |
| `<designs-root>/*.md` | ③ 技术设计 / 架构裁决 | 文档控制字段 + 验收 ↔ Oracle ↔ Evidence 表 |

## 8. 历史参考（MUST NOT 当作现行规范）

| 路径 | 角色 |
| --- | --- |
| `<例：docs/exec-plans/archived/**>` | 已完结计划的历史留档，非现行规格依据 |
