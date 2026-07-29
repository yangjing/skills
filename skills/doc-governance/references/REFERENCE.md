# 项目 overlay 模板

> 主入口：[`../SKILL.md`](../SKILL.md) · 工作流：[`./workflow.md`](./workflow.md)

本文件是**项目中立模板**。本 skill 不知道你的工作区里有哪些权威文档、有哪些系统简称、有哪些废弃口径。调用方 MUST 在自己的仓库内**复制 / 填充**下列表格，把它作为审计与同步阶段的输入。

推荐做法（任选其一）：

- 在 skill 安装目录同级新建 `<skill-name>.overlay.md`（本 skill 即 `doc-governance.overlay.md`）写入填充后的表格——发现由命名约定承担（SKILL.md「项目 overlay 自动发现」），无需在项目 `CLAUDE.md` / `AGENTS.md` 另设链接入口
- 直接在调用 skill 时把填充后的表格作为上下文提交给 agent

下列表格保留**空表头 + 一个示意行**，示意行 MUST 在使用前删除或替换。

## 工作区权威来源（待填充）

| 类别 | 真实源（项目内相对路径） |
|------|------------------------|
| 仓库总规则 | `<例：CLAUDE.md / AGENTS.md>` |
| 产品口径 / 业务模型总纲 | `<例：docs/<your-specs-root>/<main>.md>` |
| 字段命名 / 载荷契约 / 废弃映射 | `<例：docs/<your-specs-root>/<contracts-appendix>.md>` |
| 文档阅读顺序与导航 | `<例：docs/<your-specs-root>/index.md>` |
| 设计文档导航 | `<例：docs/<your-designs-root>/index.md>` |
| 主规范 / 命名规范 / 协议规范 | `<例：docs/<your-references-root>/<spec>.md>` |
| 架构文档（后端 / 前端 / 部署 / 权限） | `<例：docs/<your-designs-root>/<area>-architecture.md>` |

## 概念归属（canonical ownership，待填充）

| 概念 | 真相源 |
|------|--------|
| 账号 / 身份 / 组织模型 | `<file>` |
| 字段命名 / 载荷契约 / 废弃字段映射 | `<file>` |
| 系统特有行为 / 系统边界与依赖 | `<per-system-file>` |
| 权威入口 / 阅读顺序 / 导航 | `<index file>` |
| 服务进程 / 端口 / RPC 框架基线 | `<file>` |
| 部署形态 / 配置归口 / 反代 / 生命周期 | `<file>` |
| 权限模型 / PEP / PDP / 行级安全 | `<file>` |

> 行级安全（RLS）、`audit_ctx` 等概念若存在,MUST 指向该概念的唯一规范文件。

## 协作边界模式（与具体系统列表无关）

| 系统类型 | 应承担 | 不应承担 |
|---------|--------|---------|
| **业务入口系统**（业务真相来源） | 业务语义定义 / 业务事件 / 域内语义对象 | 通用底座能力描述 |
| **平台底座系统**（通用能力承载方） | 通用能力 + 统一契约 / 工作流 / 模板通道 / 设备治理 / 数据沉淀 | 业务语义 |

> 调用方 MUST 在 overlay 中点名"哪些系统是业务入口、哪些是平台底座"，并标注高耦合链路（例：`A ↔ B / C / D`），让审计阶段能成组检查。

## 审计高频检查点（项目中立模板）

- 系统文档中重复出现的上下文字段列表 → 应迁附录
- 总纲之外重复定义的账号 / 组织规则 → 应改链接
- 偏离正式简称集合的系统代号 → 应替换
- 旧字段别名 / 废弃名被误当作现行字段 → 应替换或加 deprecation 标
- 重复描述"系统依赖什么 / 拥有何种职责" → 应摘要化或改链接
- 同主题"现行规范"与"历史口径"并存 → 应明确角色
- 是否存在唯一规范文件被次级文档"暗中重新定义" → 高优冲突
- 历史 PRD / 草稿是否被索引误挂权威入口 → 应降级为"历史参考"
- 双 skill 路径（如 `.agents/skills/` 与 `.claude/skills/`）是否说明"真相源 / 兼容映射"
- 面向 Agent / LLM 的索引、触发规则、加载规则、review gate、迁移 / 同步 / 治理 workflow 是否使用执行协议：`Trigger → Lookup/Load → Apply → Conflict/Stop → Output`，并包含 `MUST NOT`

> 项目可在 overlay 中追加自己的实现约束 SSOT 检查项（如分页、i18n、主题包归属、Proto 入口等），点名"哪一个 spec 文件是唯一规范"。

## 同步收口高频对象（项目中立模板）

- 旧系统代号 / 旧英文副标题 / 旧系统名引用 → 统一到正式集合
- 业务入口与平台底座之间重复描述的能力项 → 业务语义归入口、通用能力归底座
- 应由入口系统承担定义、却散落在平台系统的业务语义 → 回迁入口
- 只应留在平台系统的底座能力表述 → 从入口系统压缩为链接
- 旧 PRD / 草稿仍当作现行规格入口的写法 → 改为"历史参考"
- 旧实现约束口径（任何已被新规范取代的写法）→ 统一到新规范
- 旧入口引用 / 脆弱编号锚点 / 重复 skills 路径 → 改用稳定标题 + 相对链接
- 解释性 Agent 规则段落 → 改写为执行协议，保留触发信号、检索 / 加载步骤、冲突处理、停止条件、输出证据和禁止行为

## 旧术语可安全保留的位置

仅以下场景 MAY 保留旧术语：

- migration mapping tables
- deprecation notes
- compatibility sections
- 历史示例（必须显式标记"旧写法"）

其他位置 MUST NOT 出现旧术语。

## 摘要重点（PR 描述视角）

摘要 MUST 优先说明：

- 哪些内容成为正式来源
- 哪些术语被统一
- 哪些重复内容被删除 / 压缩 / 改链接
- 哪些系统文档完成同步
- 哪些协作边界被重新收口（业务入口定义 / 平台底座承载）
- 是否检查过 diagnostics（typecheck / linter / link-check 脚本）

高耦合链路 MUST 按链路分组写摘要：

```
<SystemA> → <SystemB> → <SystemC> → ...
```

实现约束统一时 MUST 单独点名（指向项目 overlay 中登记的唯一规范文件）。

旧 PRD / 旧草稿 / 兼容路径降级时 MUST 写"保留链接但角色改为历史参考 / 兼容映射"。

## 常需点名的权威文件（占位）

> 调用方 MUST 在 overlay 中替换为本项目实际权威文件清单，便于摘要阶段引用。

- `<canonical-main-spec>.md`
- `<canonical-contracts-appendix>.md`
- `<canonical-index>.md`
- `<canonical-designs-index>.md`
- `<per-system-spec-dir>/*.md`
- `<canonical-references-dir>/*.md`
