# 命名规范（Naming Conventions）

> **Status**: active · **Version**: v3（2026-07-30）
> **适用范围**：跨系统命名风格，覆盖产品规划、架构设计、研发实现、第三方对接与长期演进；支撑「概念层 ↔ API/schema 层 ↔ 策略契约层」的稳定映射
> **规范语言**：BCP 14（RFC 2119/8174）—— MUST、MUST NOT、SHOULD、SHOULD NOT、MAY
> **定位**：命名领域的规范性来源（[SPECIFICATION §1.3](./SPECIFICATION.md#13-优先级与规范性来源)）。本文承载**词表与清单**；「何为好名字」的判据见 [design-philosophy §9](./design-philosophy.md#9-命名判据)
> **本文不重述**：项目专属 action 词表、模块订阅、菜单映射、历史迁移 → 项目 overlay

## 0. Agent 执行协议

1. **Trigger**：新增或重命名概念、字段、枚举、权限码、路由，或 PR review 命中命名争议时，MUST 加载本文。
2. **Load**：先查 §2 统一词表与 §9 字段映射确认无同义词，再读命中章节；权限码相关 MUST 同时读 §8。
3. **Apply**：本文给通用形态与词表；项目专属 action、菜单归属、订阅命名以项目 overlay 为准。
4. **Conflict / Stop**：需要新增词表条目或扩展 action 时 MUST 停止并走设计变更提案（§8.1.3），MUST NOT 自行扩展。
5. **Output**：涉及命名的交付说明 MUST 点名新增 / 变更的词表条目与同步到的代码侧类型。
6. **MUST NOT**：MUST NOT 为个人风格造新词；MUST NOT 把项目专属词表写进本文。

---

## 1. 三层命名分工（强制）

| 层级          | 适用范围                           | 命名风格                                                                   | 示例                                      |
| ------------- | ---------------------------------- | -------------------------------------------------------------------------- | ----------------------------------------- |
| 概念/文档层   | 实体名、概念字段、流程说明         | 实体/类型/字段为 PascalCase；字段后缀规范化（ID/Ref/At/Type/Status/Scope） | Grant、OwnerID、PolicyRef、ExpireAt       |
| API/schema 层 | 对外 API、存储 schema、事件 schema | 字段 snake_case；枚举值 snake_case                                         | grant_id、expire_at、policy_status=active |
| 策略契约层    | PDP 输入、策略模板、Obligations    | `namespace.snake_case`（如 subject./resource./grant./env./context.）       | subject.tenant_id、context.risk_score     |

---

## 2. 统一词表（Vocabulary）

| 语义          | 规范用词 | 避免/禁用      | 说明                               |
| ------------- | -------- | -------------- | ---------------------------------- |
| 删除资源      | delete   | remove/erase   | 删除语义统一为 delete              |
| 撤销授权/令牌 | revoke   | cancel/disable | revoke 表达「撤销且可审计」          |
| 到期失效      | expire   | timeout/end    | expire 表达「时间驱动失效」          |
| 审批通过      | approve  | allow/confirm  | allow 用于 PDP 决策结果            |
| 审批拒绝      | reject   | deny           | deny 用于 PDP 决策结果             |
| 组内/归宿分配 | assign   | allocate       | allocate 语义更偏资源调度          |
| 分享          | share    | grant          | share 是协作动作；grant 是同意实例 |
| 授权记录      | grant    | permission     | permission 是权限项；grant 是记录  |
| 设备关联      | attach   | bind/link      | attach 表达申请/审批/生效的关联    |
| 设备认领      | claim    | register       | register 表达注册，不等同认领      |

---

## 3. Casing 与分隔符（强制）

| 项                | 规范                        | 示例                                  |
| ----------------- | --------------------------- | ------------------------------------- |
| 实体/对象名       | PascalCase（单数）          | Grant、RelationTuple、CapabilityToken |
| 概念字段名        | PascalCase                  | OwnerID、PolicyRef、CreatedAt         |
| API/schema 字段名 | snake_case                  | owner_id、policy_ref、created_at      |
| 枚举值            | snake_case                  | active、device_data、user_group       |
| 关系名（ReBAC）   | snake_case                  | member_of、assigned_to、managed_by    |
| 权限码            | `resource:action`（全小写） | task:create、report:export            |
| 策略契约字段      | `namespace.snake_case`      | resource.owner_id、env.network_zone   |
| Obligations 键    | `namespace.snake_case`      | auth.step_up、token.issue.ttl_seconds |

---

## 4. 缩写规则（ID/URL/API/OTP 等）

- 概念/文档层（PascalCase）：缩写整体大写：ID、URL、API、OTP、MFA、PDP、PEP、RBAC、ABAC、PBAC、ReBAC
- API/schema 与策略契约层（snake_case）：缩写整体小写：id、url、api、otp、mfa

---

## 5. 前端环境变量

- 环境变量名 MUST 在 spec / design 阶段确定，代码实现 MUST 与 spec 一致
- 命名 MUST 采用 UPPER_SNAKE_CASE，并携带构建工具要求的暴露前缀（如 Vite 的 `VITE_`）
- MUST 提供示例环境文件（如 `.env.development.example`）登记全部可用变量

## 6. 契约字段格式一致性

- Proto 中用 `string` 表达列表的字段（如逗号分隔），客户端序列化代码与测试 fixtures MUST 遵循相同格式，MUST NOT 自行拆为数组
- 测试 fixtures 中的 proto 枚举字段 MUST 使用 JSON wire format（SCREAMING_SNAKE_CASE 字符串），MUST NOT 使用目标语言的数字枚举值

## 7. 枚举（Enum）

- 枚举值 MUST 采用 snake_case；枚举名遵循所用语言的规范（如 Rust 用 PascalCase，TypeScript / Python / Java 用 UPPER_CASE）
- 外部标准且大小写敏感的值 MAY 原样保留，此时 MUST 在字段说明中标注「原样值，不做大小写转换」

---

## 8. 权限码（Permission Code）

- 权限码格式：`{resource}:{action}`，全小写，单数 resource
- 每个项目 MUST 在自己的实现规范中声明 action 词表的代码真相源；本节只给通用命名原则
- 项目专有 PermissionAction、模块归属、订阅命名或历史迁移规则 MUST 放在项目 overlay，不写入本通用规范

### 8.1 PermissionAction 命名规约

#### 8.1.1 推荐 action

| action | 语义 | 典型用例 |
|---|---|---|
| `create` | 新建资源（含批量创建、注册等「从无到有」） | `user:create`、`device:create` |
| `read` | 读取资源（列表 + 详情合一；字段差异由策略义务表达，不靠拆动作） | `user:read`、`task:read` |
| `update` | 更新资源（含一般状态切换、移动节点、重命名等无显著副作用的变更） | `user:update` |
| `delete` | 删除资源（含软删除） | `facility:delete` |
| `assign` | 关系分配（角色↔用户、权限↔角色等） | `user:assign` |
| `submit` | 提交并触发执行 | `workflow:submit` |
| `complete` | 标记完成 | `task:complete` |
| `register` | 登记 / 注册，偏外部触发的入账 | `visit:register` |
| `review` | 审批 | `request:review` |
| `set_status` | 显著合规 / 副作用语义的状态切换 | `user:set_status` |

#### 8.1.2 不推荐 action（`list` / `get`）

| action | 状态 | 说明 |
|---|---|---|
| `list` | SHOULD NOT | 列表 / 详情通常属于同一读取视图族；字段差异用策略义务（如 `mask_fields`）表达 |
| `get` | SHOULD NOT | 同上，详情读取通常收敛到 `read` |

#### 8.1.3 词表扩展规则

- 新模块 MUST NOT 自行扩展词表。确有新业务动作不在保留集且无法归并到 `read` / `update` 时，MUST 通过项目的设计变更流程显式提案，并给出「为什么不归并」的依据
- 词表与代码中的权限 action 类型 MUST 保持一致；任一变更 MUST 在同一 PR 内同步两侧

### 8.2 `set_status` 与业务专用 action 的判定标准

何时独立成 action，何时归并到 `update`，按以下两条同时满足为准：

1. **显著合规 / 副作用语义**：动作触发权限码以外的明显效果（会话强制下线、禁止登录、级联停用、外部通知、不可逆状态变迁等）
2. **差异化授权诉求**：与同 resource 的 `update` 在角色授权层面有差异化决策需求（即「能改资料但不能停用某用户」是真实业务诉求，而非过度细粒度幻想）

**对照判例**：

| 案例 | 决策 | 理由 |
|---|---|---|
| `user:set_status`（启停用户） | 独立成 `set_status` | 副作用：停用 → 会话强制下线 + 登录拒绝；授权差异：能改资料不等于能停用账号 |
| `staff:update`（普通资料更新） | 归并到 `update` | 副作用偏弱；授权层面与改资料无明显角色分裂 |
| `request:review`（审批请求） | 独立成 `review` | 副作用：决定请求是否生效；授权差异：申请人与审批人不同 |
| `workflow:submit`（提交向导 / 流程） | 独立成 `submit` | 副作用：触发初始化、通知或后续审批；授权差异：编辑草稿不等于提交生效 |

### 8.3 列表 vs 详情字段差异化授权 → `Obligation.mask_fields`

历史上为表达「列表脱敏、详情完整」的授权差异，曾考虑拆 `:list` / `:read`。**该方向已被否决**：

- 单一 `xxx:read` 权限码授予列表 + 详情视图族
- PDP / policy service 在响应中携带 `Obligation.mask_fields`（列表场景脱敏 PII，详情场景不脱敏或更小 mask）
- PEP 响应过滤层应用 mask，业务代码不参与硬编码差异判断

### 8.4 `role_code` 与 PDP 决策的关系

`role` 在权限模型中**只是 permission bundle**：

- PDP allow / deny 决策 MUST 只看 `permission_code`；MUST NOT 把 `role_code` 作为授权依据写进 PEP、PDP 或测试断言。`role_code` 仅 MAY 出现在前端展示、审计 metadata 与诊断信息中。
- role binding 表是 binding 的收集入口，但 PDP 在评估时 MUST 立刻把 role 展开成 `permission_code` 集合；后续匹配、deny override、scope applicability 全部以 `permission_code` 为单位。
- 测试断言反例：`expect(decision.role_code).toBe('tenant_admin')` —— MUST 改为对 `permission_code` 断言。
- `permission_code` MUST 严格遵守 §8.1 的 `resource:action` 两段式形态；MUST NOT 用三段式或前缀通配作为授权依据。

---

## 9. 字段映射写法（概念层 ↔ API/schema ↔ 策略契约）

统一用三列表达字段映射，避免实现层重复「翻译」。

| 概念/文档层（PascalCase） | API/schema（snake_case） | 策略契约（namespace.snake_case）     |
| ------------------------- | ------------------------ | ------------------------------------ |
| Owner.OwnerID             | owner.owner_id           | subject.owner_id / resource.owner_id |
| Owner.OwnerType           | owner.owner_type         | subject.owner_type                   |
| Grant.GrantID             | grant.grant_id           | grant.id                             |
| Grant.ExpireAt            | grant.expire_at          | grant.expire_at                      |
| Grant.Purpose             | grant.purpose            | context.purpose                      |
| Grant.Level               | grant.level              | context.level                        |
| Context.RiskScore         | context.risk_score       | context.risk_score                   |
| Env.NetworkZone           | env.network_zone         | env.network_zone                     |

---

## 10. 前端路由命名规约

适用范围：使用 TanStack Router 文件路由或同类文件路由体系的 Web 前端应用。项目专有菜单层级、模块订阅与历史路由约束应放在项目 overlay 中，不写入本通用规范。

### 10.1 Route 文件命名

TanStack Router 文件路由命名 MUST 遵循官方约定：

| 语义 | 命名 |
|---|---|
| 根路由 | `__root.tsx` |
| pathless layout | `_layout.tsx` 或 `_authenticated.tsx` |
| 动态段 | `$id.tsx` / `$entityId.tsx` |
| 排除路由树 | `-components/` / `-utils/` |
| 目录路由 | `route.tsx` 或 `.route.tsx` |
| lazy split | `.lazy.tsx` |

### 10.2 URL 语义

- URL path SHOULD 反映用户理解的业务域，而不是组件名、数据库表名或内部技术层。
- 同一实体的列表、详情、编辑、创建页 SHOULD 处于同一 URL 域下。
- 隐藏路由（详情 / 编辑 / 创建 / `$id` 等）不应脱离实体所在域。
- 顶级路径变更属于用户可见契约变更，MUST 同步菜单、导航、测试、文档与重定向策略。

### 10.3 菜单与 URL

- 菜单是导航入口，不是 URL 真相源；URL 应先按业务域稳定设计，再由菜单引用。
- 目录型菜单 SHOULD 只表达分组，不强行挂可访问页面。
- 菜单、权限、订阅模块之间的映射属于项目业务规则，MUST 在项目设计文档中声明唯一真相源。

---

## 11. 一致性与禁用模糊词

本节是 [design-philosophy §9 命名判据](./design-philosophy.md#9-命名判据) 与 [§10 一致性](./design-philosophy.md#10-一致性consistency-as-a-tool) 的可执行落地点，也是这两项的**唯一真实源**。

### 11.1 一致性优先

大系统中消除「未知的未知」的最强武器：读者一旦在 A 处理解某模式，在 B / C / D 处可零成本复用。

- MUST 引入新概念前先搜本文 §2 词表与 §9 字段映射，确认无同义词；若有 → 复用
- MUST NOT 为「个人风格」造新词；引入新词 MUST 在 §2 词表增补一行并 PR review 显式确认
- 跨模块同一概念 SHOULD 用同一字段名 / 错误码 / 状态值
- 一致性偶尔与「局部最优」冲突 → MUST 倾向一致性，除非有显式 ADR 记录例外

### 11.2 禁用模糊词

以下词 SHOULD NOT 单独出现在变量 / 函数 / 类 / 模块名（作为后缀消歧除外）：

| 禁用词            | 问题             | 替代方向                            |
| ----------------- | ---------------- | ----------------------------------- |
| `data`            | 万能但无信息     | `user_records` / `audit_payload`    |
| `info`            | 同上             | `tenant_meta` / `device_spec`       |
| `handle`          | 既可名词也可动词 | `process_event` / `event_listener`  |
| `process`         | 同 `handle`      | `validate_input` / `dispatch_task`  |
| `manager`         | 万能但无职责边界 | `connection_pool` / `cache_evictor` |
| `helper` / `util` | 收容站，吸引浅模块 | 按动作命名或并入有职责的模块      |

模糊名字是模糊思维的化石 —— 写不出精确名字往往意味着设计未想清。引入禁用词 MUST 在 PR review 显式说明「为何无法用精确名」，并优先回头改设计。

## 12. 代码注释与日志语言

代码内自然语言文本分两个面。**语言取值 MUST 由项目 overlay 声明**——它取决于团队母语、协作面与是否开源，换项目一定变；本节只约束一致性与边界：

| 文本面 | 主要读者 | 取值考量 |
| ------ | -------- | -------- |
| 注释 / doc comment | 维护者、code review | 读者是人：母语降低理解与表达成本，英文利于跨语言协作与开源 |
| 日志文案 / panic·assert 消息 / 错误消息 | 运维检索、告警规则、日志平台与工具链 | 读者含机器：非英文会撞上编码、grep、第三方平台规则匹配 |

- 两个面 MAY 取不同语言（如注释母语 + 日志英文），但**各自内部 MUST 单一语言**——同一文本面内混排会让检索与告警规则失效。
- 标识符不在本节范围：无论注释取何语言，标识符 MUST 英文（§3）。
- **语言取值确立或变更 MUST NOT 触发存量批量回改**：仅当所在代码因功能修改被触及时才顺带统一。批量回改的巨型 diff 会淹没功能变更并废掉 blame。
- 本节只约束代码内文本；规格、设计文档、用户手册的语言同样由项目 overlay 决定。
