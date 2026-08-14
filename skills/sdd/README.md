# sdd

基于规格的开发（Spec-Driven Development）通用规范集：**契约先于实现，文档只写代码无法表达的内容，规则必须可验证**。

## 简介

跨边界交付的通用规范 skill。规则按"换什么会失效"分三层：

- **`references/`**：换栈、换项目都不变的方法论规则（契约形状、命名、分层、依赖、文档载体…）。
- **`stacks/`**：换项目不变、换栈就变的落地形态（protobuf-connectrpc / rust-postgres / react-tanstack-antd 的类型映射、框架 API、生成链）。
- **项目 overlay**：换项目一定变的取值（路径、包名、词表、命令、迁移策略）——由调用方仓库的 `sdd.overlay.md` 提供。

skill **项目中立**：本文不做具体取值。`SKILL.md` 只做**触发路由**与**执行协议**，条款全部在分册中，按需加载、不预读。

与 `doc-governance` skill 的分工：本 skill 负责**写什么 / 怎么写才合规**，doc-governance 负责**已写文档的一致性审计与批量同步**。

## 适用场景

即使用户只说「加个接口」「这字段该叫什么」「这段要不要写进文档」「这模块该不该拆」「这条规则放哪」而没提 SDD / 规范 / 契约，也命中。典型触发：

| 触发场景 | 分册 |
|---------|------|
| 写或评审任何文档（先过内容准入）、文档载体与代码引用 | SPECIFICATION §1 |
| 设计 / 变更 Contract Surface（API / 事件 / Schema / 权限码 / 错误码） | SPECIFICATION §4 / §7 |
| 一个域该有多少 RPC、能否合并、粒度下限 | SPECIFICATION §7.5 |
| 兼容性、破坏性变更、演进窗口 | SPECIFICATION §11 |
| 拆迭代任务、定义契约包、代码生成链 | spec-driven-development |
| 评审模块设计 / 判定是否重构 / 代码注释与 PR 质量 | design-philosophy |
| 新增或重命名概念 / 字段 / 枚举 / 权限码 / 路由 | naming-conventions |
| 跨服务依赖、通信协议选型、复制边界、边界信任模型 | service-dependency-contract |
| 后端模块结构、新增 crate / 包、字段类型落哪层 | backend-layering |
| 前端 route / Provider / 远程数据 / 金额与日期渲染 | frontend-conventions |
| 多语言能力、命名空间、文案真相源归属、fallback | i18n-conventions |
| 判断某条规则该不该存在 / 是否重复 / 该放哪层 | sdd-overview §2–3 |

完整路由表见 [`SKILL.md`](SKILL.md) §1。

## 安装

```bash
# 安装到当前项目
npx skills add <owner>/my-skills --skill sdd

# 全局安装
npx skills add <owner>/my-skills --skill sdd -g -y
```

## 依赖

需要文件系统读写 + shell（`python3`）；适用于 Claude Code / Codex 风格工作区。规范校验脚本零第三方依赖，未装 uv 的环境用 `python3` 直跑等价。

## 使用说明

本 skill 面向 AI Agent 自动执行。命中路由表任一行即加载对应分册章节；跨领域任务可命中多行。

**项目 overlay 自动发现**：overlay 必须命名为 `sdd.overlay.md` 并置于 skill 安装目录同级（skill 经 symlink 镜像到其它 skills 树时，以 resolve 后的真实安装目录同级为准）。加载任一分册前若该文件存在则先读取作为项目输入；未找到时回退到「调用方在上下文中提供」。骨架见 [`templates/project-overlay.md`](templates/project-overlay.md)。

### 规范符合性检查

新增 / 改动规格文档后必跑，检出五类**机械可判定**的违规（不做语义判断）：

```bash
uv run scripts/check-spec-conformance.py          # 扫描本 skill 的 references/ 与 stacks/
uv run scripts/check-spec-conformance.py --json   # 结构化输出
uv run scripts/check-spec-conformance.py --self-test  # 校验规则本身的检出能力
SDD_SCAN_ROOTS='docs/designs,docs/specs' uv run scripts/check-spec-conformance.py
```

| 检查 | 违规 |
|------|------|
| C1 | `path:line` 行号锚点（行号会随重构漂移，见 SPECIFICATION §1.2） |
| C2 | Agent 执行协议缺段（sdd-overview §3.3） |
| C3 | BCP 14 关键词小写（"must" 不是规范性语言） |
| C4 | `.overlay.md` 命名违规（sdd-overview §2.1） |
| C5 | 规格文档头缺 Status / Version 控制字段（SPECIFICATION §4.1） |

**扫描面限定为规格体裁**（功能 / 系统规格、总纲索引词表、技术设计与架构裁决）；执行计划、运营跟踪、UAT 记录、对外文稿不纳入，避免假阳性。

## 核心原则（MUST）

1. **契约先于实现**：设计或变更跨边界接口先定契约，实现服从契约。
2. **文档只写代码无法表达的内容**：写每一段前问「删掉它，只读代码的人会失去什么？」——答不上来就删。准入清单唯一真相源 = SPECIFICATION §1.0。
3. **规则必须可验证**：用 BCP 14 大写关键词（`MUST`/`SHOULD`/`MUST NOT`）表达硬约束；不可验证的条款不写进规范。
4. **章节号是公共引用锚点**：分册 `§N` 被文档、源码注释、门禁脚本引用；改标题 / 重排编号会静默断链，改前 MUST grep、改后 MUST 跑链接校验。
5. **以代码为事实**：规范与代码冲突时回头修订规范，而非迁就代码。需新增架构例外、无法判定现行真相、或需扩展受控词表时 MUST 停止并报告。

## 目录结构

```
sdd/
├── SKILL.md                     # 触发路由表 + 三层内容模型 + 执行协议 + Gotchas
├── references/                  # 通用规则分册（换栈换项目都不变）
│   ├── SPECIFICATION.md         # 总纲：内容准入 / 载体 / 契约形状 / 兼容性 / 门禁
│   ├── sdd-overview.md          # overlay 边界 + 第一性原理审查 + Agent 规则检查
│   ├── spec-driven-development.md  # 拆迭代任务 / 契约包 / 代码生成链 / 收尾 checklist
│   ├── design-philosophy.md     # 深模块 / 信息隐藏 / 设计两次 / 十二气味 / 注释准入
│   ├── naming-conventions.md    # 概念 / 字段 / 枚举 / 权限码 / 路由命名
│   ├── service-dependency-contract.md  # 依赖 / 协议 / 复制边界 / 信任模型
│   ├── backend-layering.md      # 后端模块结构 / 字段类型落层
│   ├── frontend-conventions.md  # route / Provider / 远程数据 / 金额日期渲染
│   └── i18n-conventions.md      # 多语言能力 / 命名空间 / fallback
├── stacks/                      # 技术栈落地形态（换栈就变）
│   ├── README.md                # 本层导览：现有适配层索引 + 新增适配层步骤 + 归属判断
│   ├── protobuf-connectrpc.md
│   ├── rust-postgres.md
│   └── react-tanstack-antd.md
├── templates/                   # feature-spec / project-overlay / stack-adapter 骨架
├── scripts/
│   └── check-spec-conformance.py  # 规范符合性检查（C1–C5，PEP 723 自包含）
└── evals/
    ├── evals.json
    └── trigger-queries.json
```
