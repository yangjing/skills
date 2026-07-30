# 国际化规范（i18n Conventions）

> **Status**: active · **Version**: v2（2026-07-26）
> **适用范围**：采用 react-i18next + Ant Design + dayjs 的 Web 前端应用；内容分类（§4）与机构级默认语言（§10）的判据与技术栈无关
> **规范语言**：BCP 14（RFC 2119/8174）—— MUST、MUST NOT、SHOULD、SHOULD NOT、MAY
> **本文不重述**：日期 / 时间格式 → [SPECIFICATION §6](./SPECIFICATION.md#6-日期时间格式强制)；前端装配与 Provider 顺序 → [frontend-conventions](./frontend-conventions.md)
> **由项目 overlay 定义**：支持语言集与默认语言、localStorage key、命名空间归属、i18n 实例装配落点

## 0. Agent 执行协议

1. **Trigger**：新增或调整多语言能力、改动 locale JSON / 命名空间 / 语言切换入口、或判断某段文案该不该进前端静态 JSON 时，MUST 加载本文。
2. **Load**：文案归属问题先读 §4 分类规则；「整页显示 key」类故障按 §9 清单顺序排查；其余只读命中章节。
3. **Apply**：本文定规则与判据；取值（语言集、key 名、包路径）以项目 overlay 为准。
4. **Conflict / Stop**：需要把语言偏好挂到 user 账号 / server profile、或需要为 D 类数据引入第二套静态 JSON 通道时，MUST 停止并报告。
5. **Output**：交付说明 MUST 列出改动的命名空间、涉及的 locale 文件，以及验证过的语言环境。
6. **MUST NOT**：MUST NOT 引入浏览器语言探测库（§1）；MUST NOT 对硬编码 key 使用 `defaultValue`（§8）。

---

## 1. 语言状态管理（强制）

语言由用户在 UI 中选择，MUST 持久化到 **localStorage（per-device）**，**不挂在 user 账号 / server profile 上**。这是有意的 per-device 设计 —— 同一用户在不同设备的语言诉求可能不同（如 PC 与移动端用不同语言），跨设备同步反而坏体验。

同类 per-device 偏好（如「上次访问的工作区」）遵循同一规则：localStorage per-device，不存 user 表，不加 proto 字段。

### 规则

- 语言设置存储在 **localStorage**，使用一个稳定的 key（如 `app_locale`）；同一项目的多个 SPA 可共享同一 key
- 未登录时使用浏览器语言（`navigator.language`）匹配支持的语言集，无匹配则 fallback 到默认语言
- 用户主动切换语言 MUST 同步更新三层（见第 5 节）并写入 localStorage
- 跨设备允许语言不同 —— **不**通过 RPC 调用同步到服务端

### 禁止事项

- MUST NOT 使用 URL 路径驱动语言状态（管理后台类应用无 SEO 需求）
- MUST NOT 把语言偏好挂在 user 账号 / server profile（如 `User.preferences.locale` proto 字段、user 表 column）
- MUST NOT 实现「跨设备语言同步」—— 这是有意的 per-device 行为
- 禁止使用 `i18next-browser-languagedetector` 库
- 评审 PR 时如看到 proto/SQL 把语言偏好等 per-device 字段挂在 user/account 上，应挑战「是否真的有跨设备同步诉求」

### 语言偏好读取优先级

```
1. localStorage 中的 locale key               ← 最高优先（per-device 持久化）
2. 浏览器语言匹配（navigator.language → 支持的语言集）
3. 默认语言                                    ← fallback
```

### 语言切换入口

- 入口 SHOULD 置于顶部导航栏右侧（用户菜单内，或直接可操作的语言下拉）
- 切换后立即生效，无需刷新页面
- 下拉选项仅展示支持的语言集

---

## 2. 命名空间拆分与按路由懒加载（强制）

翻译资源 MUST 按命名空间拆分，业务命名空间 MUST 按路由 lazy load。

### 命名空间策略

| 命名空间     | 加载方式         | 所属位置   | 说明                                            |
| ------------ | ---------------- | ---------- | ----------------------------------------------- |
| `common`     | 静态（始终加载） | 共享 UI 包 | 通用 UI 文案：保存、取消、确认、删除等          |
| `errors`     | 静态（始终加载） | 共享 UI 包 | 通用错误/提示文案：网络错误、权限不足等         |
| 业务命名空间 | 按路由 lazy load | 各 app     | 按功能模块拆分，在路由 `beforeLoad` 中加载      |

### 共享资源文件结构

- 共享 UI 包的语言文件允许在同一 JSON 中包含多个顶层分组，例如 `common.json` 同时承载 `common.*` 与 `login.*`
- 当命名空间加载器读取共享 JSON 时，MUST 返回**整份 JSON 对象**
- MUST NOT 只返回 `json.common` 之类的子树，否则同文件中的 `login.*` 等 key 会直接回显原始 key

示例：

```jsonc
// 共享 UI 包 locales/zh/common.json
{
  "common": {
    "save": "保存",
  },
  "login": {
    "title": "应用标题",
  },
}
```

```ts
// 正确：返回整份 JSON
if (ns === "common") return commonResources[lng];

// 错误：只返回子树，会导致 login.* 查找失败
if (ns === "common") return commonResources[lng].common;
```

### 命名空间与路由映射

业务命名空间名称 SHOULD 与路由路径一级目录对应（如 `/orders/*` → `orders` 命名空间、`/settings/*` → `settings` 命名空间），便于按路由 lazy load。

### 懒加载实现

```typescript
// 路由 beforeLoad 中加载命名空间
export const Route = createFileRoute("/_authenticated/dashboard")({
  beforeLoad: async ({ context }) => {
    await context.i18n.loadNamespaces("dashboard");
  },
});
```

加载失败的兜底策略：`loadNamespaces` 失败时使用 fallback 语言的同名命名空间；fallback 也失败则静默跳过（不影响页面渲染）。

### 动态 JSON 加载规则

- 在 Vite 中，`import('*.json')` 返回的是模块对象，MUST 显式读取 `.default`
- 业务命名空间加载器 MUST 返回纯翻译对象，而不是 ES module 包裹对象

示例：

```ts
// 正确
return (await import(`@/locales/${lng}/${ns}.json`)).default;

// 错误
return await import(`@/locales/${lng}/${ns}.json`);
```

### Workspace 包开发态解析规则

- 在 workspace monorepo 中，开发态 SHOULD 让 app 直接解析共享包的 `src`
- 对被频繁联调的 workspace 共享包，Vite alias 与 `tsconfig.paths` MUST 保持一致
- MUST NOT 让本地 dev server 继续消费过期 `dist`，否则会出现「源码已修复但运行时仍是旧行为」的假象

典型故障信号：

- 某个动态接口按源码应已存在，但浏览器 Network 中没有发出该请求
- 语言切换组件、i18n 初始化逻辑、共享 `common.json` 修复后，页面行为仍与旧版本一致
- 浏览器实际加载的是 `dist/*.js` 而不是 workspace `src/*`

### 禁止事项

- MUST NOT 在应用启动时一次性加载所有语言的翻译资源
- MUST NOT 将所有翻译放在单一 JSON 文件中
- SHOULD NOT 在非必要的路由中加载不相关的命名空间

---

## 3. 翻译 Key 结构（强制）

翻译 key MUST 使用点分层级结构，反映功能模块和页面位置。

### Key 格式

完整引用路径：`t('{namespace}.{page}.{element}')`

JSON 文件内的 key 不含命名空间前缀（命名空间由文件名决定）：

```jsonc
// locales/zh/orders.json（命名空间 = orders）
{
  "list.title": "订单管理",
  "list.createButton": "新增订单",
  "detail.basicInfo": "基本信息",
  "form.name": "名称",
}

// 引用时：t('orders.list.title')
```

### 示例

```jsonc
// common 命名空间（共享 UI 包 locales/zh/common.json）
{ "save": "保存", "cancel": "取消", "confirm": "确认", "delete": "删除" }
// 引用：t('common.save')

// system 命名空间（app locales/zh/system.json）
{
  "menu.dashboard": "工作台",
  "roles.title": "角色管理"
}
// 引用：t('system.menu.dashboard')、t('system.roles.title')
```

### 禁止事项

- MUST NOT 使用无结构的 key（如 `title`、`button1`、`msg`）
- MUST NOT 在 key 中嵌入翻译文本（如 `save_button_保存`）
- SHOULD NOT 使用过长层级（最多 3 段，不含命名空间前缀）

---

## 4. 翻译内容分类与边界（强制）

不是所有显示文本都进入前端静态 locale JSON。实现前 MUST 先判断文本所属类别，再决定真相源与翻译策略。

### 分类规则

| 类别                       | 典型对象                                   | 真相源                | 翻译来源                                        | 规则                               |
| -------------------------- | ------------------------------------------ | --------------------- | ----------------------------------------------- | ---------------------------------- |
| A 类：静态界面文案         | 页面标题、按钮、表头、空状态、错误提示     | 前端代码/设计稿       | 前端 locale JSON                                | MUST 使用 `t('{namespace}.{key}')` |
| B 类：系统预置参考数据     | 菜单、系统预置字典、系统内置标签           | DB seed + 后端 API    | 前端 locale JSON，实体返回稳定 `key/code/value` | MUST 使用 `t()` + API fallback     |
| C 类：契约枚举/常量        | Proto enum（如 `OrderStatus`）、错误码     | Proto enum / 共享常量 | 前端按枚举值映射翻译 key                        | MUST 保持枚举为真相源              |
| D 类：租户自定义运行时数据 | 租户自定义字典、自定义分级、多语言模板     | 业务表                | 后端按 locale 返回本地化文案                    | MUST NOT 依赖前端静态 JSON         |

### 判定规则

- 若某值参与状态机、权限判断、路由守卫或 API 契约兼容性，MUST 归为 C 类，而不是可编辑字典
- 若某值是系统内置、跨环境稳定、由后台控制启停/排序，但语义不应被租户改写，SHOULD 归为 B 类
- 若某值是页面固定文案且不来自 API，MUST 归为 A 类
- 若某值由租户在运行时创建/编辑，且同一条业务数据要求多语言展示，MUST 归为 D 类
- 用户输入的实体名（组织名、人名等）MUST NOT 放入前端 locale JSON，除非产品明确要求多语言内容管理

### B 类：系统预置参考数据规则

- 后端实体 MUST 提供稳定标识字段，菜单使用 `key`，系统预置字典使用 `code + value`
- 实体中的 `name` / `label` 保留默认语言值，仅作为翻译缺失时的 fallback
- 前端渲染 MUST 使用 `t(key) ?? fallbackValue` 模式
- 菜单 MUST 使用 `menu` 命名空间：`t('menu.' + item.key) ?? item.name`
- 系统预置字典 SHOULD 使用 `dict` 命名空间：`t('dict.' + dictCode + '.' + itemValue) ?? item.label`
- B 类翻译文本 MUST NOT 成为数据库唯一真相源

#### 字典列表 RPC 的返回字段契约

字典项列表 RPC MUST 按字典类别返回不同字段集（具体 RPC 名由项目契约定义）：

| 字典类别 | MUST 返回字段 |
| --- | --- |
| 系统预置字典（B 类） | `dictCode`、`itemValue`、`label`（默认语言） |
| 租户运行时字典（D 类） | `dictCode`、`itemValue`、`defaultLabel`、`localizedLabel`、`effectiveLocale` |

`effectiveLocale` MUST 标识实际生效的语言（命中当前 locale、fallback 链、或默认语言），使前端可判断是否走了兜底。

### C 类：契约枚举/常量规则

- Proto enum / 共享常量 MUST 继续作为真相源
- 前端映射层 MUST 从「中文 label 常量」改为「`labelKey` + color/value」或等价的 `t()` 包装器
- `Tag` / `Badge` / `Descriptions` / `Select options` SHOULD 在渲染时调用 `t(labelKey)`，MUST NOT 在常量层直接写中文 `label`
- 若历史上同一枚举同时存在 `MAP` / `LABELS` / `OPTIONS` 三套展示常量，SHOULD 先收敛为单一真相源，再派生展示结构

#### C 类 Key 命名规范

- 状态类 MUST 使用 `"{namespace}.status.{value}"`，如 `orders.status.pending`
- 类型类 MUST 使用 `"{namespace}.type.{value}"`，如 `devices.type.sensor`
- 等级类 SHOULD 使用 `"{namespace}.level.{value}"`，如 `alerts.level.critical`
- 计划/流程状态 SHOULD 使用 `"{namespace}.planStatus.{value}"`，如 `subscriptions.planStatus.active`
- 通用共享枚举 MUST 使用 `"common.enum.{enumName}.{value}"`，如 `common.enum.gender.male`
- `value` 段 MUST 使用 lowerCamelCase，MUST NOT 直接复用 proto 的全大写枚举名
- `value` 段 SHOULD 表达稳定业务语义，例如 `FALSE_ALARM -> falseAlarm`、`IN_PROGRESS -> inProgress`

### D 类：运行时动态翻译边界

- D 类数据 MUST 由后端按当前 locale 返回本地化文案，并同时保留默认值字段作为 fallback
- D 类数据 MUST NOT 复用 `menu.json`、`dict.json` 或其它业务静态 locale JSON
- 若后续新增 D 类能力，SHOULD 独立设计翻译存储模型与 API，不与本规范中的静态装载链路混用

---

## 5. 三层同步（强制）

切换语言时 MUST 同步更新以下三层：

| 层                  | 同步方式                               | 触发时机                    |
| ------------------- | -------------------------------------- | --------------------------- |
| react-i18next       | `i18n.changeLanguage(locale)`          | 语言切换时                  |
| antd ConfigProvider | `getAntdLocale(locale)` 动态 import    | 响应 `languageChanged` 事件 |
| dayjs               | `dayjs.locale(getDayjsLocale(locale))` | 响应 `languageChanged` 事件 |

### 失败处理

- `i18n.changeLanguage(locale)` 成功后，antd/dayjs 的同步 SHOULD 继续执行
- `getAntdLocale(locale)` 动态 import 失败时，MUST NOT 回滚 react-i18next 的当前语言；antd 组件可暂时保持切换前语言，并输出 warning 日志
- `dayjs.locale(...)` 对应 locale 缺失时，MUST NOT 阻塞页面渲染，并输出 warning 日志

---

## 6. Fallback 链与语言归一化

### 支持的语言集

项目支持的具体语言集是项目配置，MUST 显式声明并设定一个默认语言作为最终兜底。下例为一种常见配置：

| 语言码  | 说明                            |
| ------- | ------------------------------- |
| `en`    | 英文（默认，兜底 fallback）     |
| `zh`    | 简体中文                        |

### Fallback 链

缺失翻译条目时按链式回退，最终兜底为默认语言。以上例配置：

```
en  → （无进一步回退，自身即兜底）
zh  → en
```

浏览器语言的地区变体 MUST 归一化到基础语言码：`zh-CN` / `zh-TW` / `zh-HK` 等 `zh-*` 统一映射为 `zh`，`en-US` / `en-GB` 等 `en-*` 统一映射为 `en`。

### 与 i18next 配置的约束

- 当项目已显式实现地区变体兼容映射（如 `zh-CN -> zh`、`en-US -> en`）与 `zh* -> zh`、`en* -> en` 归一化时，MUST NOT 开启 `nonExplicitSupportedLngs`
- 原因：该选项可能让归一化行为与运行时判定重复叠加，导致 `isSupportedCode()` 与资源查找链路出现不一致
- `supportedLngs` MUST 只包含真正维护的语言码

```ts
supportedLngs: ['zh', 'en'],
// 不要再配置 nonExplicitSupportedLngs: true
```

### 新增语言检查清单

新增语言时 MUST 同步更新以下位置：

1. 共享 i18n 模块中的支持语言表、antd locale 映射、dayjs locale 映射、fallback 配置
2. 共享 UI 包的 `locales/{new-locale}/common.json`
3. 各 app 的 `locales/{new-locale}/{namespace}.json`
4. 语言切换 UI 的下拉选项

---

## 7. 翻译文件治理（强制）

### 文件结构

- 翻译文件 MUST 放在 `locales/{locale}/{namespace}.json`
- 默认语言 MUST 作为完整参考语言，所有 key 必须存在
- 其它语言 MUST 覆盖所有 key
- 业务命名空间文件 SHOULD 同时承载本模块的 A 类静态文案与 C 类枚举显示文案
- `dict.json` 仅用于系统预置字典，MUST NOT 用于租户自定义运行时数据

### 文件维护规则

- 同一命名空间下的 key SHOULD 按字母序排列，便于 diff 与 review
- 新增 key 时 MUST 同步补齐所有语言
- 共享 JSON 若包含多个顶层分组，加载器 MUST 返回整份对象，而不是某个子树
- Vite 动态 import JSON 时 MUST 读取 `.default`

---

## 8. 运行时失败与降级约束（强制）

### 命名空间加载

- `loadNamespaces` 失败时 MUST NOT 阻塞路由导航
- 失败时 SHOULD 尝试 fallback 语言的同名命名空间
- fallback 也失败时 MUST 静默跳过，页面允许显示原始 key 或 API fallback 值
- 加载失败 MUST 输出 warning 级别日志，便于定位

### `t()` 函数参数约束（强制）

- `t(key, { defaultValue: '...' })` MUST NOT 用于**硬编码的前端翻译 key**
- `defaultValue` 参数仅在**动态后端内容**或**三方库集成**场景允许使用

理由：

- i18next 缺失 key 时的默认行为是**返回 key 字符串本身**（如 `create.fields.currency`），在 UI 上非常显眼，能让开发者/QA 第一时间发现问题
- 使用 `defaultValue` 会**静默吞掉 key 缺失的错误**，使漏配翻译、key 路径拼写错误、key 被误删除等问题在开发和生产环境中完全不可见
- fallback 链已能保证功能不中断，`defaultValue` 提供的是不必要的第三层软兜底

```tsx
// ❌ 禁止 —— changePassword 所有 key 已在 locale JSON 中定义
t('changePassword.success', { defaultValue: '密码修改成功，请重新登录' })

// ✅ 正确 —— key 缺失时会显示 changePassword.success，立即可见
t('changePassword.success')
```

检出时机：Code Review 时 MUST 拦截新增的 `defaultValue` 参数；存量清理纳入项目技术债跟踪。

### 语言偏好持久化

- 用户主动切换语言后，UI MUST 立即生效，并同步写入 localStorage
- localStorage 写入失败（如隐私模式 / 配额已满）MUST NOT 阻塞或回滚当前会话语言，SHOULD 输出 warning 日志

### 登录态约束

- 登录页 MUST NOT 显示语言切换入口
- 未登录场景的语言仅由浏览器语言匹配与默认语言兜底决定

---

## 9. 故障排查与防回归清单

本节是 troubleshooting 体裁，不构成新的规范条款；其价值在于固定排查顺序，避免从最贵的一步开始猜。

出现「整页显示 key」时，MUST 按以下顺序排查：

1. **先查语言匹配**
   - 检查 `supportedLngs`
   - 检查浏览器语言归一化结果
   - 检查是否误开 `nonExplicitSupportedLngs`
2. **再查资源加载**
   - 共享 JSON 是否返回整份对象
   - 业务 `import(...json)` 是否读取 `.default`
   - Network 面板是否真的请求了对应 `{locale}/{namespace}.json`
   - 在 monorepo 开发态中，确认 app 实际解析的是 workspace `src` 而不是过期 `dist`
3. **再查 i18next 运行时状态**
   - `i18n.language`
   - `i18n.services.languageUtils.isSupportedCode(i18n.language)`
   - `i18n.services.languageUtils.toResolveHierarchy(i18n.language)`
   - `i18n.hasLoadedNamespace(ns)`
   - `i18n.store.data`
4. **最后查组件使用方式**
   - `useTranslation(ns)` 的命名空间是否正确
   - `t()` 的 key 是否与 JSON 结构一致

### 防回归规则

- 新增/修改 i18n 初始化逻辑后，MUST 至少验证以下页面：
  1. 登录页共享文案
  2. 任一已登录页面的菜单/面包屑/TopBar
  3. 任一业务页面的表头/按钮/空状态
- 验证时 MUST 同时检查：
  - 各支持语言的浏览器环境
  - 页面不出现形如 `namespace.key` 的原始 key
- 若本次变更涉及 workspace 共享包：
  - MUST 额外确认浏览器 Network/模块解析路径与本地源码一致
  - MUST 至少验证一次依赖共享包的动态请求确实发出

---

## 10. 机构级默认语言（Org / Facility Default Locale）

§1 规范的是**用户级 UI 语言**（per-device、由用户选择、localStorage 持久化）。与之并列存在另一类语言概念：**机构级默认语言**——在**没有用户 UI 上下文**时作为语言 fallback 的机构属性。两者 MUST 区分，MUST NOT 互相替代。

### 两类语言的边界

| 维度     | 用户级 UI 语言（§1）              | 机构级默认语言（本节）                                       |
| -------- | --------------------------------- | ------------------------------------------------------------ |
| 语义     | 当前用户在当前设备看到的界面语言  | 机构（组织 / 场所实体）在无用户上下文时的默认 / fallback 语言 |
| 真相源   | localStorage（per-device）        | 机构实体的通用设置属性（服务端）                             |
| 典型场景 | 前端 i18n 渲染                    | 语音识别的默认语言提示、机构级批量通知 / 报表 / 模型输出语言 |
| 消费方   | 前端                              | 与消费方无关：同一属性被 UI 默认、通知、报表等多方复用       |

### 规则

- 机构级默认语言 MUST 建模为**与消费方无关的通用属性**；MUST NOT 绑定到某个具体增值能力（如绑死某条 AI / 语音功能的路由）。
- 取值 MUST 复用项目支持语言集的**基础语言码**（如 `zh` / `en`，见 §6），MUST NOT 携带地区后缀（不写 `zh-CN`）。
- 无用户上下文场景的语言 resolve 优先级 MUST 为：**请求显式指定 > 机构默认语言 > 系统默认语言**。
- 机构未配置默认语言时 MUST 平滑回退系统默认语言，MUST NOT 阻断功能。
- 当消费方自身支持自动语言识别时，机构默认语言 SHOULD 只作**软提示**（影响候选语言的构成与顺序），MUST NOT 收窄为单语硬锁——自动识别的兜底能力 MUST 保留。
- 机构默认语言 MUST NOT 挂在 user 账号 / server profile 上（用户语言仍遵循 §1 的 per-device 规则）。

> 各消费方对该属性的具体消费方式（语言提示的传递、模型 prompt 语言、resolve 链落点）由项目 overlay 定义。
