---
status: active
last_updated: 2026-11-17
---

# 栈适配层：Vue 3 + OpenTiny TinyVue + Vite

> **适配对象**：[`../references/frontend-conventions.md`](../references/frontend-conventions.md)（主）、[`../references/naming-conventions.md`](../references/naming-conventions.md) §10、[`../references/i18n-conventions.md`](../references/i18n-conventions.md) §5 / §8
> **规范语言**：BCP 14（RFC 2119/8174）
> **本层职责**：把通用前端约定落到 Vue 3 + OpenTiny TinyVue（`@opentiny/vue@3`）这一组具体库的 API、装配顺序、主题机制与版本陷阱上。**MUST NOT 写项目路径、端口、域名**——那些属项目 overlay

## 0. Agent 执行协议

1. **Trigger**：项目使用 Vue 3 + `@opentiny/vue@3` + Vite，且命中 frontend-conventions 任一章节时，MUST 与该章节一并加载本文对应节。
2. **Load**：按各节标题下的「对应」链接加载（本文 §2 ↔ frontend-conventions §3，§3 ↔ §4，§4 ↔ §5，§6 ↔ §6.2；§5 对应 i18n-conventions §5 / §8）；frontend-conventions 的 React 专属条款（Provider 装配 / antd 约束 / Rules of Hooks）MUST NOT 直接套用，以本文对应节的 Vue 等价形态为准。
3. **Apply**：通用职责边界以 `references/` 为准，**本文只覆盖 API 与配置的具体形态**。
4. **Conflict / Stop**：本文与 `references/` 原则冲突时，MUST 以 `references/` 为准并报告本文需要修订；需要在业务层绕过 TinyVue 组件自绘 DOM 或引入第二套组件库时，MUST 停止并报告。
5. **Output**：交付说明 MUST 点名改动的 route / 组件 / query key，以及跑过的 lint、类型检查与构建结果。
6. **MUST NOT**：MUST NOT 把本文条款当作其它前端栈的依据；MUST NOT 依赖 `.tiny-*` 内部 DOM 类名做大范围样式覆盖（主题定制只走 `--tv-*` 变量）。

---

## 1. 本栈采纳的结论

对应 [frontend-conventions §1](../references/frontend-conventions.md#1-采纳的结论)。下表只记**本栈做出的选择**；库本身的能力说明以官方文档为准（§1.1）。

| 主题 | 本栈采纳 |
| --- | --- |
| 版本 | Vue 3 项目 MUST 安装 `@opentiny/vue@3`（3.x 线，`~` 锁次版本）；Vue 2 线（`@opentiny/vue@2`）MUST NOT 混入 |
| 组件引入 | 全量注册（`app.use(TinyVue)`）为缺省；包体敏感时 MAY 按需引入命名导出（`import { Button as TinyButton } from '@opentiny/vue'`） |
| 模板标签 | 模板 MUST 用 `tiny-` 前缀 kebab 标签（`<tiny-button>` / `<tiny-grid>`） |
| 路由 | vue-router 4；文件路由非本栈硬约束，route 命名沿用 naming-conventions §10 的路径语义 |
| 远程数据 | @tanstack/vue-query（v5）；query key 工厂集中管理、mutation 后按 prefix 失效，与 react 栈同判例 |
| 构建模式 | `vite.config.ts` MUST `define: { 'process.env': { TINY_MODE: 'pc' } }`——tree-shake 移动端形态 |
| 主题 | `@opentiny/vue-theme` 全量 CSS + `--tv-*` CSS 变量定制；MUST NOT 耦合 `.tiny-*` 内部 DOM |
| 品牌主色 | TinyVue 工厂默认 `--tv-base-color-brand` 为近黑 `#191919`（蓝色 `#1476ff` 承担 info/active 语义）；需要蓝色主按钮时 MUST 以 `--tv-base-color-brand`（及 brand 色阶）单点覆写实现，MUST NOT 逐组件覆写 |
| 图标 | `@opentiny/vue-icon` 图标集；与 antd 图标集不同名不同形，MUST NOT 假设一一对应 |
| 日期工具 | 应用层日期格式化 MAY 保留 dayjs；TinyVue 日期组件不绑定 antd dayjs 生态 |

### 1.1 官方文档

外部依据 MUST 只采用官方文档：

- 安装与 CDN：[Installation](https://docs.opentiny.design/tiny-vue/guide/installation.html)
- 主题定制 / 暗色：TinyVue 官方文档 themes 节（`--tv-*` 变量清单以 `@opentiny/vue-theme` 产物为准）
- Agent 技能：[tiny-vue-skill](https://github.com/opentiny/agent-skills)——生成 TinyVue 代码前 MAY 加载该技能获取组件 API 细节

---

## 2. 安装与装配形态

对应 [frontend-conventions §3](../references/frontend-conventions.md#3-app-壳层与-provider)。

```ts
// main.ts
import { createApp } from 'vue';
import TinyVue from '@opentiny/vue';
import '@opentiny/vue-theme/index.css';

const app = createApp(App).use(TinyVue);
```

```ts
// vite.config.ts
export default defineConfig({
  plugins: [vue()],
  define: { 'process.env': { TINY_MODE: 'pc' } },
});
```

装配顺序（等价 react 栈的 Provider 链）：`createApp(App)` → `use(TinyVue)` → `use(router)` → vue-query plugin（`QueryClient` 单例在 `src/lib/query-client.ts` 创建后经 `VueQueryPlugin` 注入）→ i18n 初始化 → `mount('#app')`。

- `QueryClient` / router / transport / i18n MUST 在模块顶层创建，MUST NOT 在组件 `setup()` 内 new 长期对象。
- 品牌覆写在全局样式入口以 `:root { --tv-base-color-brand: <brand>; }` 形态落地（brand 色阶 1–13 若设计稿有要求则一并覆写；缺省只覆写基色时，派生色随 TinyVue 变量关系联动）。

---

## 3. 组件映射惯例（antd 语义 → TinyVue）

对应 [frontend-conventions §4](../references/frontend-conventions.md#4-ui-组件库约束)。

| antd 语义 | TinyVue 组件 | 备注 |
| --- | --- | --- |
| Table（分页 / 筛选 / 排序 / 行选 / 固定列） | `TinyGrid` | 功能等价且更强；分页器内建或配 `TinyPager` |
| Pagination | `TinyPager` | cursor 分页桥接判例同 react 栈：`current` MUST 来自 route search params |
| Drawer / Modal | `TinyDrawer` / `TinyModal` | 后果说明需阅读 = Modal；轻确认 = `TinyPopconfirm` |
| message / notification | `Modal.message` / `TinyNotify` | 静态调用经 TinyVue 服务式 API |
| Form + Input/Select/DatePicker/TimePicker | `TinyForm` + `TinyInput` / `TinySelect`(filterable) / `TinyDatePicker` / `TinyTimePicker` | 时段 = `TinyTimePicker is-range`（原生支持） |
| InputNumber | `TinyNumeric` | |
| Upload | `TinyUpload` | 文件 / 图片上传走 multipart 判例 |
| Alert / Tag / Badge / Tabs / Steps / Statistic | `TinyAlert` / `TinyTag` / `TinyBadge` / `TinyTabs` / `TinySteps` / `TinyStatistic` | Segmented 语义用 `TinyTabs` button-card 形态近似 |
| Dropdown / Tooltip / Popover | `TinyDropdown` / `TinyTooltip` / `TinyPopover` | |
| Result 页 | 无同名件——空 / 错误态用 `TinyException`；自定义结果面板组合 Alert + 图标实现 | |
| QR 码 | `TinyQrcode` | |
| 图表 | `TinyChart`（hui-charts） | 按需；简单趋势 MAY 保持轻量自绘 |

禁忌（MUST NOT）：

- 用 `el-*`（Element Plus）标签或混入第二套 Vue 组件库。
- 在 `.tiny-*` 内部 DOM 类名上写大范围样式覆盖（主题走 `--tv-*`）。
- 把 antd 的 `ConfigProvider` token 机制经验直接迁移（TinyVue 无 Provider 主题树，走 CSS 变量）。

---

## 4. 版本陷阱与渲染约束

对应 [frontend-conventions §5](../references/frontend-conventions.md#5-渲染层约束)。

- **ESM-only**：TinyVue 3.17+ 运行时仅发 `.mjs`（无 UMD/IIFE 全局包）——MUST 经 Vite 构建部署，MUST NOT 假设可直接以 `file://` 打开运行。
- **v-model 已知问题**：对 prop 直接 `v-model` 触发 Vite 编译错误时，MUST 拆为 `:modelValue` + `@update:modelValue`。
- **空 SFC**：`.vue` 文件 MUST 至少含一个 `<template>` 或 `<script>` 块（空文件报编译错）。
- 表单提交 / 保存 / 删除用 `TinyButton loading` + vue-query mutation 局部 pending；MUST NOT 全屏 spinner 阻塞。
- 页面组件保持纯渲染；网络请求放 vue-query / route 守卫 / 明确 event action。

---

## 5. i18n 三层同步

对应 [i18n-conventions §5](../references/i18n-conventions.md#5-三层同步强制) 与 [§8](../references/i18n-conventions.md#8-运行时失败与降级约束强制)。

| 层 | 同步动作 | 触发时机 |
| --- | --- | --- |
| vue-i18n | `i18n.global.locale.value = locale` | 语言切换时 |
| TinyVue locale | `@opentiny/vue-locale` 语言包动态 import 并重挂组件树 | 响应 `languageChanged` 事件 |
| dayjs | `dayjs.locale(getDayjsLocale(locale))` | 响应 `languageChanged` 事件 |

- TinyVue locale 包动态 import 失败时，MUST NOT 回滚 vue-i18n 当前语言；组件文案可暂时保持切换前语言并输出 warning 日志。
- vue-i18n 缺失 key 的默认显形行为与降级约束同 react 栈判例（MUST NOT 静默回退空串）。

---

## 6. 日期渲染的库落点

对应 [frontend-conventions §6.2](../references/frontend-conventions.md#62-日期时间字段datetime--date-字符串)。

- 共享 datetime helper 内部 MAY 使用 dayjs（token `YYYY-MM-DD` 等价规范 `yyyy-MM-dd`，仅大小写差异）。
- 构造发给后端的 ISO 用 `dayjs(x).format('YYYY-MM-DDTHH:mm:ssZ')` 保留时区。
- 金额计算的 helper 内 MAY 使用 `big.js`，并 MUST 从 `DecimalString` 构造。
