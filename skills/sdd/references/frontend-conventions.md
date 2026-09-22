---
status: active
version: v6  # 2026-09-02 增 §8.5 驻 store 表单新建入口复位原语条款（持盈 r417 实证回流）；v5 2026-09-01 增 §8.2 键盘布局 / §8.5 预填意图 / §9 操作出口与异步反馈 / §10 控件组件层与跨端清单口径（移动端双栈第二批实证回流）；v4 2026-08-30 增 §8
---

# 前端工程约定（SPA 通用）

> **适用范围**：单页 Web 应用（SPA）的工程组织原则——route 职责边界、Provider 生命周期、远程数据分层、渲染纪律；§8 表单交互与敏感值、§9 操作出口与异步反馈、§10 控件组件层与跨端清单口径为跨端通用（Web / 移动端同守）。**与具体框架无关**
> **规范语言**：BCP 14（RFC 2119/8174）—— MUST、MUST NOT、SHOULD、SHOULD NOT、MAY
> **本文不重述**：路由文件命名 → [naming-conventions §10.1](./naming-conventions.md#101-route-文件命名)；i18n 工程规范 → [i18n-conventions](./i18n-conventions.md)；质量门禁 → [SPECIFICATION §13](./SPECIFICATION.md#13-质量门禁通用)；fixtures 与开发数据策略 → [SPECIFICATION §4.4](./SPECIFICATION.md#44-开发数据策略)
> **栈落地形态**：React 19 + TanStack Router / Query + Ant Design 6 + Vite 的具体 API、插件顺序、组件约束见 [`../stacks/react-tanstack-antd.md`](../stacks/react-tanstack-antd.md)；移动端分栈（RN iOS 壳 / HarmonyOS ArkTS）见 [`../stacks/react-native-ios.md`](../stacks/react-native-ios.md) · [`../stacks/harmonyos-arkts.md`](../stacks/harmonyos-arkts.md)。本文只定原则与禁忌，不写框架 API

## 0. Agent 执行协议

1. **Trigger**：新增或改动 route、Provider 装配、远程数据接入、组件用法、样式、金额 / 日期渲染，表单交互（字段 label / 键盘 / 日期输入 / 弹层承载 / 预填意图）与敏感值脱敏，操作出口与异步反馈（弹层取消 / 动作反馈 / 定时器生命周期），或控件组件层与跨端清单口径（控件封装 / 规格单源 / 逃逸口 / 披露文案）时，MUST 加载本文。
2. **Load**：只读命中章节；每章末尾的「禁忌」小节 MUST 一并读取——多数回归缺陷出在那里。命中章节标注了栈落地形态时，MUST 一并加载对应 `stacks/` 适配层。
3. **Apply**：本文定通用职责边界与禁忌；框架 API 与插件配置以 `stacks/` 适配层为准；baseUrl、CSRF、错误映射、包名与目录以项目 overlay 为准。
4. **Conflict / Stop**：需要偏离固定 Provider 顺序、需要在业务层引入 mock 数据，或需要以 §8–§10 禁忌形态交付（如半屏弹层承载多字段键盘表单、文本输入承接日期值、弹层态无显式退出出口、样式逃逸口开放尺寸类属性）时，MUST 停止并报告。
5. **Output**：交付说明 MUST 点名改动的 route / Provider / query key，以及跑过的 lint、类型检查与构建结果。
6. **MUST NOT**：MUST NOT 在业务运行时源码 import fixtures；MUST NOT 依赖 UI 库内部 DOM 类名做大范围样式覆盖。

---

## 1. 采纳的结论

每个 SPA MUST 就下列维度做出**显式选择**并记录在项目 overlay 或栈适配层；本表只定各维度的通用取向，具体库与 API 见 [`../stacks/react-tanstack-antd.md`](../stacks/react-tanstack-antd.md) §1。

| 维度 | 通用取向 |
| --- | --- |
| 路由声明 | MUST 用文件路由 + 生成的 route tree；MUST NOT 手写 history 路由 |
| 代码拆分 | 大页面 MUST 按 route chunk 拆分；拆分由路由工具链自动完成，MUST NOT 手工维护 chunk 清单 |
| 路由守卫 | guard MUST 从 store 或 router context 读取状态；MUST NOT 在 guard 内调用只能在组件树中运行的 hook |
| URL 状态 | 列表筛选、分页、scope id、重定向地址 MUST 类型化并落在 URL query 中，MUST NOT 挂组件本地状态 |
| 远程数据 | 每个 feature MUST 通过查询定义工厂导出查询，query key MUST 集中管理以支持按 prefix 失效 |
| 列表分页 | 翻页 MUST 保留上一页数据直到新页就绪，MUST NOT 在翻页时闪回空态 |
| Provider 装配 | 顶层 Provider 顺序 MUST 固定并在栈适配层写死；MUST NOT 按需调换 |
| 长期实例 | router、数据客户端、传输层、i18n MUST 在模块顶层声明，以规避严格模式双调与热更新竞态 |

### 1.1 官方文档

外部依据 MUST 只采用所选库的官方文档；MUST NOT 依据博客、问答站或模型记忆编写约定。各栈的官方文档清单见对应 `stacks/` 适配层。

---

## 2. Route 层约定

route 文件命名（根路由、pathless layout、动态段、排除前缀等）见 [naming-conventions.md](./naming-conventions.md) §10.1，本节不重述。

route 文件只承载这些职责：

- 声明路由本身。
- 入口判断：登录、scope context、权限、订阅模块、i18n namespace。
- 校验 query string；列表页筛选和分页必须进 URL。
- 首屏必要 prefetch，使用 feature 提供的查询定义。
- 挂载 feature page，不内联复杂 UI。
- 按 route 粒度定义 pending / error / notFound 边界。

路由守卫：

- 根路由 MUST 携带类型化的 router context，至少包含 i18n 与数据客户端。
- 认证 layout MUST 唯一收口会话 bootstrap、scope 切换、CSRF 刷新、scope 选择、权限与菜单过滤。
- 需要 hook 结果时，MUST 在组件层通过 Provider / store 注入，再由 router context 或 store 快照读取。

URL 参数校验：

- MUST 用 schema 校验并提供 fallback，类型由 schema 推导，MUST NOT 手写类型与 schema 双写。
- 全部 schema MUST 集中在统一模块内按 domain 命名导出；SHOULD 用 lint 规则阻止 route 文件内联回归。
- 分页字段 MUST 做数值强制与下限约束，避免非法输入落地为 `NaN`。

禁忌（MUST NOT）：

- 在路由 guard、普通工具函数或网络拦截器中调用只能在组件树内运行的 hook。
- 把登录页 / scope 选择页放进认证 layout 之下（造成 guard 循环重定向）。
- 把 URL 参数 schema 写在 route 文件内联（无法 reuse / audit）。
- 把列表筛选 / 分页 / scope id / 重定向地址挂在组件本地状态上（必须进 URL 以可分享、可恢复）。
- 在 route 的 component 字段内联复杂 UI（route 文件应保持薄）。

---

## 3. App 壳层与 Provider

启动流程的通用形态：

```
入口模块
  创建 router
  创建 app 壳
  等待 i18n 就绪
  向 router 注入 context（i18n、数据客户端）
  挂载根组件
```

Provider 顺序 MUST 在栈适配层固定并写死；调换顺序属破坏性变更，MUST 走评审。

实例生命周期：

- router、数据客户端、传输层、i18n MUST 在模块顶层声明。
- 数据客户端单例 MUST 在独立模块创建，由 app 壳注入 Provider。
- 热更新 dispose 时 MUST 解绑 i18n 就绪回调，避免重复 render。

禁忌（MUST NOT）：

- 调换固定的 Provider 顺序。
- 把顶层 Provider 下沉到 route 树（route 树不应负担顶层 context 实例化）。
- 在组件 render 中创建数据客户端 / 传输层 / router（严格模式双 mount 与热更新会导致重复实例化）。
- 在 API 汇总模块中创建数据客户端（该模块只做客户端集中导出）。

---

## 4. UI 组件库约束

- 全局配置 Provider MUST 唯一；需要局部主题时 MAY 嵌套，但必须有明确业务原因。
- 命令式反馈（message / modal / notification 等）MUST 通过携带 context 的实例获取，MUST NOT 顶层静态调用——静态调用拿不到主题、locale 与 CSS 变量。
- 主题优先级：全局 token → 组件 token → 实例级 className / style。
- 实现或修改具体组件前，SHOULD 先查该组件的官方 API（项目若提供离线 API 查询工具则优先使用），改动后 MUST 跑组件库相关 lint 规则。
- 卡片类容器 MUST NOT 作默认页面容器。页面结构 MUST 使用顶层布局容器 + 内容面；页面级标题使用语义 heading；卡片仅用于重复内容单元、局部摘要、表单分组、列表项或弹层内部的明确分组。

禁忌（MUST NOT）：

- 顶层 import 并调用命令式反馈 API（无 Provider context，主题 / locale / CSS 变量全部丢失）。
- 引入绕过 Provider context 的全局静态配置作为例外口。
- 依赖 UI 库内部 DOM 类名做大范围样式覆盖；需要语义插槽时使用官方提供的 className / style 字段。

具体库的组件约束、lint 规则名与版本适配见 [`../stacks/react-tanstack-antd.md`](../stacks/react-tanstack-antd.md) §3。

---

## 5. 渲染层约束

- 页面组件保持纯渲染；网络请求放数据层、route loader 或明确的 event action 中。
- 大路由 chunk MUST 走路由级 code splitting；route 级 pending / error 边界提供局部反馈。
- 表单提交、保存、删除等 action MUST 用局部 pending 表达（按钮 loading、mutation 状态或渲染层 transition）。
- 手写并发调度原语只用于本地昂贵状态切换。

禁忌（MUST NOT）：

- 在路由 guard、普通工具函数或网络拦截器中调用 hook。
- 在组件 render 中 new 长期对象（router / 数据客户端 / 传输层 / i18n / store）。
- 把路由跳转包在并发调度原语中（路由库内部已处理）。
- 用全屏 spinner 阻塞用户（route 级 pending 边界提供局部反馈）。

框架版本特定的约束见 [`../stacks/react-tanstack-antd.md`](../stacks/react-tanstack-antd.md) §4。

---

## 6. 远程数据约定

本节为远程数据接入的通用分层约定。具体传输层配置（baseUrl、credentials、CSRF、错误映射）属项目接入层，不在本规范内。

API 分层：

```
lib/transport            # 传输配置：baseUrl、credentials、CSRF、错误映射
lib/<protocol>-client    # 协议客户端薄封装；只绑定 transport
api                      # 对生成 Service 创建客户端并集中导出，不定义新 API surface
lib/query-client         # 数据客户端单例
features/*/api/*.queries # query keys、查询定义、mutation helper；不是协议层 client
```

规则：

- 协议生成物（Service、message、enum、字段类型）只从生成包统一导入，任何 app 不再自定义另一套 API client 接口或后端 DTO。
- 页面 / 组件 / feature 查询模块 / hook 的业务数据 MUST 来自真实协议 client；后端 stub 返回空数组或空 message 时，前端显示 Empty / 空态。
- fixtures 边界以 [SPECIFICATION §4.4](./SPECIFICATION.md#44-开发数据策略) 为准。前端侧的落点：页面、组件、hook 与 feature 查询模块均属业务运行时源码，MUST NOT import fixtures，MUST NOT 在 catch 分支 fallback 到 fixtures，MUST NOT 伪造列表 / 详情 / 权限 / 菜单数据。
- 远程读取优先走声明式查询或 route loader 的 prefetch，二者 MUST 复用同一份查询定义。
- 每个 feature MUST **同时**导出 key factory 与查询定义工厂：
  - factory 用于 mutation 后按 prefix 集中失效。
  - 查询定义工厂用于复用各消费形态（订阅、prefetch、缓存直写）间的类型推导。
  - 两者并存不是冗余，是各司其职。
- query key 必须是数组，必须包含影响请求结果的全部变量（分页、筛选、scope id、状态）。
- 分页 / 列表查询 MUST 保留上一页数据直到新页就绪。
- mutation 成功后按 feature query key 精准失效。
- 金额/费用等 decimal wire 字段在前端统一使用 `DecimalString` 语义（详见 §6.1）；命名、precision/scale、币种等完整契约由各项目 field-contracts overlay 文档定义，本文只规范前端使用方式。

禁忌（MUST NOT）：

- 在 API 汇总模块中包装出与协议契约不一致的方法名 / 参数形态 / 返回 DTO。
- 从页面 / 组件 / feature 查询模块 / hook import fixture 源文件或项目 fixtures 包。
- 使用 `try → fallback fixtures`、静态数组或 mock map 作为业务接口失败兜底。
- mutation 成功后无参粗暴刷新全部查询（必须按 feature key prefix 精准失效）。
- 在 query key 中遗漏影响请求结果的变量（如 search / scope id / page）—— 会导致缓存命中错误数据。
- 在页面 / 组件内自建请求状态机（loading / error / reload 全部走统一数据层）。

具体库的 API 名、版本迁移陷阱与代码示例见 [`../stacks/react-tanstack-antd.md`](../stacks/react-tanstack-antd.md) §2。

### 6.1 DecimalString 与金额字段

前端金额/费用字段 MUST 使用以下类型别名表达 wire 字符串语义：

```ts
export type DecimalString = string;
```

规则：

- 契约生成的金额/费用字段保持 `string`；feature 层 UI model / form model MAY 用 `DecimalString` 提升语义。
- 只展示金额时 SHOULD 保持字符串输入，格式化输出为字符串。
- 前端本地需要合计、折扣、比较、排序或四舍五入时，MUST 使用统一 decimal helper；helper 内 MAY 使用任意精度十进制库，并 MUST 从 `DecimalString` 构造。
- 前端 MUST NOT 用 `number` / `Number()` / `parseFloat()` / `+value` 计算金额。
- 表单提交前 SHOULD 做基础格式校验；最终 precision/scale、币种 minor unit 与 rounding 校验以服务端为准。

### 6.2 日期时间字段（datetime / date 字符串）

后端 datetime 字段为 RFC 3339 ISO 字符串（含时区，如 `2026-06-05T02:10:28+00:00`），
纯日期字段为 `yyyy-MM-dd`（格式真源见 [SPECIFICATION §6.1](./SPECIFICATION.md#61-wire-与存储形态)）。时区策略真源见
[SPECIFICATION §6.2](./SPECIFICATION.md#62-时区归属)「前端展示：调用方按本地时区自行转换」。本节定义前端落地实现。

- **MUST** 用项目 overlay 指定的共享 datetime helper 渲染后端日期时间，禁止页面内自造或内联格式化调用：
  - 日期时间 → `formatDateTime(iso)` → `YYYY-MM-DD HH:mm`
  - 纯日期 → `formatDate(iso)` → `YYYY-MM-DD`
  - 秒级（审计 / 时间线）→ `formatDateTimeSeconds(iso)` → `YYYY-MM-DD HH:mm:ss`
  - 紧凑无年份（卡片 / 移动端）→ `formatDateTimeShort(iso)` → `MM-DD HH:mm`
- 全部 helper 自动转**浏览器本地时区**、**不显示时区后缀**；空 / 非法值统一回 `—`。
  上列 token 为日期库惯用写法，等价于规范 §6.1 的 `yyyy-MM-dd`，仅大小写差异。
- **禁止**：
  - 原样渲染日期字段 / 缺 `render` 的日期列；
  - `new Date(x).toLocaleString()` / `.toLocaleDateString()`（依赖浏览器 locale，格式不统一）；
  - 页面内各自定义 `formatDate` / `formatTime`。
- **例外**（不经 helper）：构造**发给后端**的 ISO（保留时区）、now 计算、时间选择控件的受控值格式、纯时刻 / 图表轴标签
  —— 这些是序列化 / 输入 / 非 datetime 字段，非展示。

### 6.3 Cursor 分页与页码控件桥接

后端主模式为 Cursor 分页（[SPECIFICATION §15.1](./SPECIFICATION.md#151-cursor-based-分页默认符合-aip-158)）时，表格控件需要 `current` / `total` 这类页码语义。桥接算法见 [SPECIFICATION §15.4](./SPECIFICATION.md#154-页码型-ui-控件桥接)；本节只给前端侧绑定纪律：

- 在 feature 的查询层或组件状态中维护 `pageTokens: string[]`，`pageTokens[0] = ''`。
- 翻页时用 `pageTokens[page - 1]` 作为请求 token；响应回来后把 `nextPageToken` 写入 `pageTokens[page]`。
- 总数用响应的 `totalSize`；服务端未返回时按 `current * pageSize + (hasNext ? pageSize : 0)` 近似。
- 当前页码 MUST 来自 URL 参数（§2「列表筛选 / 分页必须进 URL」），MUST NOT 挂在组件本地状态上。

MUST NOT 为了适配表格控件而要求后端改用 Offset 分页——分页模式的选择判据在 [SPECIFICATION §15.3](./SPECIFICATION.md#153-模式选择指南)。

---

## 7. 样式约定

- 全局 CSS 只放 reset、CSS variables bridge、layout 基础类。
- feature 私有样式靠 CSS modules 或 feature 局部 class。
- 优先使用 UI 库的设计 token，而非硬编码色值与尺寸。
- 自定义 CSS 变量统一加应用约定的前缀，不混入无前缀变量。

禁忌（MUST NOT）：

- 新增大而全的全局样式表（feature 样式 co-locate 在 feature 内）。
- 使用 UI 库内部选择器；需要语义插槽时使用官方提供的 className / style 字段。
- 引入无统一前缀的自定义 CSS 变量。

---

## 8. 表单交互与敏感值（跨端通用）

> 移动端双栈（RN iOS / HarmonyOS ArkTS）真机实证提炼的交互底线，Web 同守。本节只定**原则与禁忌**；键盘行为、弹层组件、日期选择器等**栈落地形态**见 [`../stacks/`](../stacks/README.md) 对应适配层。日期时间的**渲染**纪律在 §6.2，本节只管**输入**。label 视觉规格（字阶 / 颜色 / 布局位）属项目设计系统，不在本节。

### 8.1 字段身份

- 表单字段 MUST 有常驻 label——字段身份 MUST NOT 依赖 placeholder：placeholder 在有值后消失，字段即不可辨。
- placeholder MAY 保留，语义降级为填写示例；口令、一次性定稿向导等例外语境由项目 overlay 显式登记，MUST NOT 逐屏自行豁免。

### 8.2 键盘可达性与弹层承载

- 软键盘在场时，聚焦输入框与提交动作排 MUST 保持可见、可达（避让 + 滚动，形态见 stacks）。
- 无 return key 的数字键盘（decimal-pad 类）MUST 提供显式收起通道（收起浮条 / 滚动收起）；平台自带收起位时 SHOULD 直接采用（留验证证据），MUST NOT 自绘重复件。
- 数值字段 MUST 声明数字键盘布局（键盘类型属性，形态见 stacks）；字符过滤（正则 / 长度限制）只拦截非法输入，MUST NOT 视为键盘布局切换的等价物——只设过滤时用户仍面对全键盘逐字试错。
- 半屏弹层 / drawer MUST NOT 承载含软键盘输入的多字段表单——键盘压缩后可用高度不足，提交动作排出视口。承载形态 = 独立二级页、全屏表单页，或**该栈已实证键盘避让可靠**的底部对齐弹层（在对应 stacks 适配层登记）；未实证的弹层形态 MUST NOT 未经实机验证直接采用。
- 模态内 MUST NOT 再开模态选择器（层级互盖 / 系统层焦点互斥，双端实证形态各异）——多字段表单页面化后，选择器为普通页上的单层模态。

### 8.3 日期输入

- 日期字段 MUST 用平台原生日期选择器（draft 滚动、确定才回写）；MUST NOT 以文本输入承接日期值——手输 `YYYY-MM-DD` 不可用且无法校验合法值。
- 选择器「确定」动作 MUST 回写**并关闭**——只回写不关闭是通用缺陷（用户无法判断编辑是否生效）。

### 8.4 敏感值与脱敏

- 脱敏渲染 MUST 经单源入口分发（集中脱敏态 + 统一分发 helper，具体命名属项目 overlay）；组件内自写脱敏三元 = 违例（散落分支必漂移）。
- 脱敏值（占位符）MUST NOT 进入表单模型——预填占位符经隐式转换（`Number()` 等）产出静默脏数据（实证形态：NaN 静默清空字段后保存成功）；编辑态预填 MUST 用原始值，表单录入面整体列入脱敏排除清单。
- 命令式预拼串（非响应式重算填充）MUST 在脱敏态切换时联动重算——响应式注入面自动跟随，预拼面不会自动跟随。
- 敏感面清单 MUST 逐渲染点盘点登记；正则类自动断言只证明**已枚举形态**被覆盖（无货币符号、异常精度等形态天然漏网），MUST NOT 以单一正则通过为覆盖证明。
- 敏感值复制到剪贴板 MUST 限时清除，且切后台 MUST 立即清除。

### 8.5 预填意图与草稿

- 表单的显式预填意图（编辑 / 复制 / 外部定位 / 解析结果回填等）与本地草稿恢复并存时，意图 MUST 优先于草稿消费——草稿覆盖意图 = 入口静默失效（用户从外部入口进入却看到旧草稿，无从分辨）。
- 意图 MUST 一次性（消费即清）；残留意图会劫持后续进入（新建态被旧意图预填）。
- 表单值驻全局 / 单例 store（非组件内 state）时，「新建」语义的**全部入口**（页内常驻钮 / 快捷方式 / deep link / 语音·解析预填 / 解锁脉冲等）MUST 走同一复位原语后再进页——任一入口跳过复位 = 上次输入（含编辑态残留）静默漏出；解析预填路径 = 复位在前、patch 覆盖在后（顺序安全）；「返回保留输入」类既有设计例外 MUST 显式登记并与保存成功路径分立（首证 2026-09-02 持盈 r417 记一笔：快捷方式 add/ocr、解锁快捷脉冲、语音预填三入口跳过 `resetTxFormForNew` + 编辑保存成功分支不清表单值——同症状不同根因的残留四路径）。

禁忌（MUST NOT）：

- 以 placeholder 为唯一字段身份。
- 键盘在场时聚焦框或提交动作不可见、不可达；数字键盘表单无收起通道；数值字段只设字符过滤不声明键盘布局。
- 半屏弹层 / drawer 承载多字段键盘表单；模态内嵌模态选择器。
- 文本输入承接日期值；日期选择器「确定」只回写不关闭。
- 组件内自写脱敏三元；脱敏值预填表单；敏感值复制后无时限驻留剪贴板。
- 预填意图被草稿覆盖；意图消费后残留。

---

## 9. 操作出口与异步反馈（跨端通用）

> 移动端双栈真机 UAT 实证提炼的交互底线，Web 同守。本节只定**原则与禁忌**；弹层组件、手势与原生资源形态见 [`../stacks/`](../stacks/README.md) 对应适配层。

### 9.1 操作出口完备

- 弹层与全屏页的每个用户可进入态（新建 / 编辑 / 引导 / 确认）MUST 有显式退出出口（取消 / 关闭动作位）；仅保存单钮 = 缺陷。
- 同一容器的出口 MUST 跨态对称——新建态与编辑态其一有取消、另一无，即不对称缺陷（实证形态：新建态保存后无法原路退出）。
- 系统级关闭能力（下滑清除 / 遮罩点击）存在端与形态差异，MUST NOT 作为唯一退出出口依赖；自带显式出口后系统手势属增量。

### 9.2 动作反馈（死按钮禁止）

- 用户可触发的动作在**前置未满足**（依赖未就绪 / 权限未决）与**执行失败**两种形态下 MUST 呈现可见反馈：前置未满足 = 等待 / 引导态，失败 = 错误原因 + 重试入口。
- 点击零反馈（无请求发出、无 UI 变化）= 缺陷——用户无从判断是卡顿还是被拒。

### 9.3 异步落定与定时器生命周期

- 跨语言桥 / 系统异步的 promise MUST 保证落定：系统回调存在机型性不达（实证形态：部分结果正常回流但终态回调缺失），收尾方 MUST 提供超时兜底出口（以已回流的部分结果落定）；悬挂 promise 的 UI 形态 = 忙态永久锁死。
- 自动收尾定时器（超时上限 / 限时任务）MUST 在全部提前退出路径（正常完成 / 取消 / 重入）清理——残留定时器在后续状态触发幽灵副作用（实证形态：确认态弹已过时错误）。
- 限时副作用计时器（N 秒后清除类）MUST 单例管理——连续触发时旧计时器提前作用于新内容 = 数据丢失（实证形态：连续复制，首次的清除计时器清掉了二次复制的内容）。

禁忌（MUST NOT）：

- 弹层 / 页面态无显式退出出口；新建态与编辑态出口不对称。
- 动作前置不满足或执行失败时点击零反馈。
- 桥 promise 无兜底落定通道；自动收尾定时器存在任一提前退出路径不清理；限时副作用计时器非单例。

---

## 10. 控件组件层与跨端清单口径（跨端通用）

> 同形控件逐屏手拼与跨端清单隐式对位的收敛纪律；平台控件默认值陷阱与封装形态见 [`../stacks/`](../stacks/README.md) 对应适配层。

### 10.1 控件组件层与规格单源

- 跨端同形控件（按钮 / 胶囊 / 分段器等）MUST 收敛到端内**薄组件层**（基础呈现控件 + 设计 token 自绘），MUST NOT 逐屏手拼同形控件样式。平台内建按钮不可定制（原型级）、或默认值构成隐藏的第二套规格（默认圆角强制 / 默认高与规格冲突）时，薄封装 + 显式规格覆盖是唯一路径。
- 控件规格值（高 / 圆角 / 字阶 / 色态）MUST 设计 token 单源；端侧 MUST NOT 手抄规格值，MUST NOT 依赖平台默认值充当规格（默认值 = 第二套规格，实证形态：同一「普通按钮高度」多值并存）。
- 组件样式逃逸口 MUST 限定布局类属性（间距 / 对齐 / 弹性权重）；尺寸与形状类（高 / 宽 / 圆角）MUST NOT 可覆盖——可覆盖的逃逸口必然被覆盖出规格漂移（实证形态：统一控件高经逃逸口回退为逐屏异值）。
- 组件层 MUST 默认齐备无障碍语义（角色默认、标签透传）与测试锚通道（测试标识透传）——消费方声明锚即生效，MUST NOT 由消费方逐处补挂。
- 新代码 MUST 消费组件层；存量按「触及即换」渐进迁移（评审纪律，非机械可测门），MUST NOT 开全量迁移专项批。
- 迁移引入显式视觉 / 行为变更时 MUST 留迁移前基线截图——基线不可事后补拍，验收对照以基线为据。

### 10.2 跨端清单与文案口径

- 跨端共享的结构化清单（字段 / 文案 / 结果行 label）与端内渲染键序 MUST 显式键绑定（键 → 条目映射），MUST NOT 依赖两个数组的隐式顺序对位——任一端插入条目即静默错位；两端共享同一单源时同步错，双端对照不设防（实证形态：结果行 label 整体错位一格）。
- 同一功能的隐私 / 能力披露文案 MUST 按端实际链路分端取值，MUST NOT 照抄他端——他端口径在本端不成立时即为虚假披露（实证形态：端侧识别口径照抄到云端链路端）。

禁忌（MUST NOT）：

- 逐屏手拼同形控件样式；手抄规格值或以平台默认值充当规格。
- 样式逃逸口开放尺寸 / 形状类属性。
- 组件层无障碍语义与测试锚通道缺位，由消费方逐处补挂。
- 并行数组靠顺序隐式对位；披露文案照抄他端口径。
