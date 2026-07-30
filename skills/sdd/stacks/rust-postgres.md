# 栈适配层：Rust + PostgreSQL + sqlx

> **Status**: active · **Version**: v1（2026-07-30）
> **适配对象**：[`../references/backend-layering.md`](../references/backend-layering.md) §3.5（数据类型分层）
> **规范语言**：BCP 14（RFC 2119/8174）
> **本层职责**：该栈的依赖开关与生态细则，以及**换栈时的映射判据**。类型映射表本身在 backend-layering §3.5，本文 MUST NOT 复制

## 0. Agent 执行协议

1. **Trigger**：项目后端为 Rust + PostgreSQL（sqlx），且命中 backend-layering §3.5 时，MUST 与该节一并加载本文。
2. **Load**：只读命中节。
3. **Apply**：类型映射以 [backend-layering §3.5](../references/backend-layering.md#35-数据类型分层强类型原则) 的表为准，本文只补该表未覆盖的依赖开关与生态选择。
4. **Conflict / Stop**：项目实际 DDL 与 §3.5 表冲突时，MUST 以项目 DDL 为事实并停止报告——MUST NOT 用示例栈类型表覆盖项目实际 schema。
5. **Output**：交付说明 MUST 点名新增 / 变更字段的「列类型 → native 类型 → wire 类型」三段映射，以及跑过的编译与迁移校验结果。
6. **MUST NOT**：MUST NOT 在本文重复 §3.5 的类型表、反例表或 helper 签名。

---

## 1. 依赖开关（`references/` 未固化的部分）

backend-layering §3.5 要求「若 SQL 驱动需额外 feature 才能直接 bind / decode 十进制类型，项目 MUST 在依赖配置中启用」。本栈的具体落点：

| 列类型 | 需要的 crate 与 feature | 缺失时的失败形态 |
| --- | --- | --- |
| `UUID` | `sqlx` feature `uuid` + `uuid` crate | 编译期 `Encode`/`Decode` trait 不满足 |
| `TIMESTAMPTZ` / `DATE` / `TIME` | `sqlx` feature `chrono` + `chrono` crate | 同上 |
| `DECIMAL(p,s)` / `NUMERIC(p,s)` | `sqlx` feature `rust_decimal` + `rust_decimal` crate | 同上；**MUST NOT** 退化为 `f64` 绕过 |
| `JSONB` | `sqlx` feature `json` + `serde_json` | 同上 |

`rust_decimal` 的精度上限为 28-29 位有效数字。业务要求超过该范围时 MUST 在项目 overlay 中声明替代方案，MUST NOT 静默截断。

## 2. 生态细则

- **`sqlx::FromRow` 字段对齐**：Row struct 的字段类型 MUST 与列类型严格对齐。错配不在编译期暴露，而在运行时 PG 解析阶段崩溃——这是本栈最高频的回归形态，MUST 在 repo 层新增字段时逐个核对 DDL。
- **`Option<T>` 与 `NOT NULL`**：可空列 MUST 映射 `Option<T>`；非空列 MUST NOT 用 `Option<T>` 兜底。用 `Option` 包非空列会把「schema 违约」降级成「业务分支」，缺陷被静默吞掉。
- **查询宏与运行时查询**：`sqlx::query!` 系列宏提供编译期校验，但要求构建期可连数据库或存在离线缓存。项目 MUST 在 overlay 中声明采用哪种模式及缓存文件的更新命令。
- **事务上下文传递**：下层持久化方法 MUST 接收调用方传入的事务上下文执行 SQL，MUST NOT 自行开启事务（事务边界归属见 [backend-layering §3.2](../references/backend-layering.md#32-application)）。

## 3. 换栈映射判据

换掉本栈时，[backend-layering §3.5](../references/backend-layering.md#35-数据类型分层强类型原则) 中**哪些要改、哪些不能改**：

| §3.5 条款 | 性质 | 换栈时 |
| --- | --- | --- |
| 三层用强类型、`api` 层负责 wire ↔ native 转换 | 硬要求 | **不变** |
| 转换位置唯一（`api` 层）、禁止 wire string 传到 SQL bind | 硬要求 | **不变** |
| 物理主键 MUST 为 `UUID` 或 `BIGINT`，MUST NOT 用 `TEXT` | 硬要求 | **不变** |
| 业务自然键用独立字段承载，不当物理主键 | 硬要求 | **不变** |
| 禁止 parse 失败兜底默认值 | 硬要求 | **不变** |
| 跨模块禁止 `id.to_string()` → 再 parse 往返 | 硬要求 | **不变** |
| 具体类型映射表（`uuid::Uuid`、`chrono::DateTime<Utc>`、`rust_decimal::Decimal`…） | 形态 | **替换**为目标语言的等价类型 |
| `parse_*_field` helper 签名 | 形态 | **替换**为目标语言的错误类型与惯用签名 |
| `sqlx::FromRow` / `bind()` 相关条款 | 形态 | **替换**为目标驱动的行映射机制 |

替换类型时的选择判据（按优先级）：

1. **精度不可损**：十进制金额 MUST 选任意精度十进制类型，MUST NOT 选浮点。
2. **时区不可丢**：`TIMESTAMPTZ` MUST 选带时区语义的类型，MUST NOT 选 naive/local 类型。
3. **可空性显式**：MUST 选能在类型层表达「可空」的形态，MUST NOT 用零值代表 NULL。
4. **无隐式截断**：目标类型的值域 MUST 覆盖列的值域（典型陷阱：`BIGINT` → JS `number` 精度丢失，见 §3.5 的 `jstype` 条款）。

数据库换成 MySQL / SQL Server 等时，额外注意：`TIMESTAMPTZ` 无直接等价物，MUST 在项目 overlay 中声明用「UTC 存储 + 应用层附加时区」还是「带时区列类型」，并写明该选择对 [SPECIFICATION §6.2](../references/SPECIFICATION.md#62-时区归属) 时区归属的影响。
