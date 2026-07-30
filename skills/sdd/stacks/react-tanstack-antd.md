# 栈适配层：React 19 + TanStack Router/Query + Ant Design 6 + Vite

> **Status**: active · **Version**: v1（2026-07-30）
> **适配对象**：[`../references/frontend-conventions.md`](../references/frontend-conventions.md)（主）、[`../references/naming-conventions.md`](../references/naming-conventions.md) §10、[`../references/i18n-conventions.md`](../references/i18n-conventions.md) §5 / §8
> **规范语言**：BCP 14（RFC 2119/8174）
> **本层职责**：把通用前端约定落到这一组具体库的 API、插件顺序、版本陷阱上。**MUST NOT 写项目路径、包名、端口、域名**——那些属项目 overlay

## 0. Agent 执行协议

1. **Trigger**：项目使用 React 19 + TanStack Router / Query + antd 6 + Vite，且命中 frontend-conventions 任一章节时，MUST 与该章节一并加载本文对应节。
2. **Load**：按节号对应加载（本文 §N ↔ frontend-conventions §N）；§5 对应 naming-conventions §10；§6 对应 i18n-conventions §5 / §8。
3. **Apply**：通用职责边界以 `references/` 为准，**本文只覆盖 API 与配置的具体形态**。
4. **Conflict / Stop**：本文与 `references/` 原则冲突时，MUST 以 `references/` 为准并报告本文需要修订；需要偏离固定 Provider 顺序或在业务层引入 mock 数据时，MUST 停止并报告。
5. **Output**：交付说明 MUST 点名改动的 route / Provider / query key，以及跑过的 lint、类型检查与构建结果。
6. **MUST NOT**：MUST NOT 把本文条款当作其它前端栈的依据；MUST NOT 在本文写项目专属 baseUrl / CSRF / 错误映射实现。

---

## 1. 本栈采纳的结论

对应 [frontend-conventions §1](../references/frontend-conventions.md#1-采纳的结论)。下表只记**本栈做出的选择**；库本身的能力说明以官方文档为准（§1.1）。

| 主题 | 本栈采纳 |
| --- | --- |
| 文件路由 | 所有 app MUST 用文件路由 + 生成的 route tree；MUST NOT 手写 history 路由 |
| 代码拆分 | `vite.config.ts` MUST 用 `tanstackRouter({ target: 'react', autoCodeSplitting: true })`，且 MUST 排在 `react()` 之前；大页面按 route chunk 拆分 |
| 文件命名 | 认证 layout 用 `_authenticated.tsx`；route 私有组件 MAY 共置于 `routes/**/-components/` |
| Router Context | route guard MUST 从 store 或 router context 读取；需要 hook 结果时先在 React 层取出再注入 |
| Search Params | 列表筛选、分页、scope id、重定向地址 MUST 类型化，并 SHOULD 用 Zod v4 `.catch()` 原生 fallback |
| `queryOptions()` | 每个 feature MUST 通过 `queryOptions(...)` 工厂导出查询定义；query key MUST 由 factory 集中管理，便于 mutation 后按 prefix 失效 |
| Query 分页 | 列表 / 分页 query MUST 用 `placeholderData: keepPreviousData` |
| antd 版本 | React 19 + antd 6 组合成立；MUST NOT 引入 React 19 patch 包 |
| Provider 装配 | 顶层顺序固定为 `ThemeContext.Provider → ConfigProvider → AntdApp → QueryClientProvider → RouterProvider`；样式 MUST 优先用 token，MUST NOT 耦合 `.ant-*` 内部 DOM |
| React 19 | route / pending UI MUST 放在路由或布局边界；router、queryClient、transport、i18n MUST 在模块顶层声明，以规避 StrictMode 双调与 HMR 竞态 |

### 1.1 官方文档

外部依据 MUST 只采用官方文档：

- TanStack Router：[File-Based Routing](https://tanstack.com/router/latest/docs/routing/file-based-routing) · [Code Splitting](https://tanstack.com/router/latest/docs/guide/code-splitting) · [File Naming](https://tanstack.com/router/latest/docs/routing/file-naming-conventions) · [Router Context](https://tanstack.com/router/latest/docs/guide/router-context) · [Authenticated Routes](https://tanstack.com/router/latest/docs/guide/authenticated-routes) · [Validate Search Params](https://tanstack.com/router/latest/docs/how-to/validate-search-params)
- TanStack Query：[Query Options](https://tanstack.com/query/latest/docs/framework/react/guides/query-options) · [Migrating to v5](https://tanstack.com/query/latest/docs/framework/react/guides/migrating-to-v5)
- Ant Design：[Migration v6](https://ant.design/docs/react/migration-v6/) · [ConfigProvider](https://ant.design/components/config-provider/) · [App](https://ant.design/components/app-cn/) · [Customize Theme](https://ant.design/docs/react/customize-theme/)
- React：[Suspense](https://react.dev/reference/react/Suspense) · [useTransition](https://react.dev/reference/react/useTransition)

---

## 2. Route 与远程数据的 API 形态

对应 [frontend-conventions §2](../references/frontend-conventions.md#2-route-层约定) 与 [§6](../references/frontend-conventions.md#6-远程数据约定)。

route 示例：

```tsx
import { createFileRoute } from '@tanstack/react-router';
import { usersListQueryOptions } from '@/features/users/api/users.queries';
import { UserListPage } from '@/features/users/pages/UserListPage';
import { usersSearchSchema } from '@/lib/search-schemas';

export const Route = createFileRoute('/_authenticated/users/')({
  validateSearch: usersSearchSchema,
  loaderDeps: ({ search }) => ({ search }),
  beforeLoad: async ({ context }) => {
    await context.i18n.loadNamespaces(['common', 'users']);
  },
  loader: ({ context, deps }) =>
    context.queryClient.ensureQueryData(usersListQueryOptions(deps.search)),
  component: UserListPage,
});
```

- 根路由使用 `createRootRouteWithContext<RouterContext>()`，context 至少包含 `i18n` 与 `queryClient`。
- 认证 layout 使用 `_authenticated.tsx`。

Search params 校验：

- Zod v4 schema 直接传给 `validateSearch`，使用 `.catch(...)` 提供 fallback；类型用 `z.infer<typeof xxxSearchSchema>` 推导，避免手写 `interface` 与 schema 双写。
- 全部 schema 集中在 `lib/search-schemas.ts`，按 domain 命名导出（`usersSearchSchema`、`rolesSearchSchema` ...）；用 ESLint `no-restricted-syntax` 规则 `Property[key.name='validateSearch'][value.type=/ArrowFunctionExpression|FunctionExpression/]` 阻止 route 文件内联回归。
- 分页字段统一 `z.coerce.number().int().min(1).catch(1)` / `z.coerce.number().int().min(10).max(N).catch(20)`，避免 `?page=abc` 落地为 `NaN`。

`vite.config.ts` 标准：

```ts
import { tanstackRouter } from '@tanstack/router-plugin/vite';

export default defineConfig({
  base: '/{app-name}/',
  plugins: [
    tanstackRouter({ target: 'react', autoCodeSplitting: true }),
    react(),
  ],
});
```

查询定义示例：

```ts
import { queryOptions } from '@tanstack/react-query';
import { usersClient } from '@/api';
import type { UsersSearch } from '@/features/users/model/ui';

export const usersKeys = {
  all: ['users'] as const,
  list: (search: UsersSearch) => [...usersKeys.all, 'list', search] as const,
  detail: (userId: string) => [...usersKeys.all, 'detail', userId] as const,
};

export function usersListQueryOptions(search: UsersSearch) {
  return queryOptions({
    queryKey: usersKeys.list(search),
    queryFn: () => usersClient.listUsers(search),
  });
}
```

- 远程读取优先 `useQuery(queryOptions(...))` / route `loader` + `queryClient.ensureQueryData(queryOptions(...))`。
- 分页 / 列表 query 使用 `placeholderData: keepPreviousData`（来自 `@tanstack/react-query`）。
- mutation 成功后按 feature query key 精准 `invalidateQueries`。

**Cursor 分页与 antd Table 桥接**（对应 [frontend-conventions §6.3](../references/frontend-conventions.md#63-cursor-分页与页码控件桥接)）：

- `Table` 的 `pagination.onChange(page)` 触发时，用 `pageTokens[page - 1]` 作为请求 token；响应回来后把 `nextPageToken` 写入 `pageTokens[page]`。
- `pagination.total` 用响应的 `totalSize`；服务端未返回时按 `current * pageSize + (hasNext ? pageSize : 0)` 近似。
- `pagination.current` MUST 来自 search params，MUST NOT 挂在组件 `useState` 上。

禁忌（MUST NOT）：

- 在 `beforeLoad` / loader / 普通工具函数 / Connect interceptor 中调用 React hooks（违反 Rules of Hooks）。
- 把登录页 / scope 选择页放进 `_authenticated/` 下（造成 guard 循环重定向）。
- 同时使用 `zodValidator(schema)` 与 Zod v4 `.catch()`（混用导致输出类型变 `unknown`）。
- 在 `vite.config.ts` 中把 `tanstackRouter()` 排在 `react()` 之后（插件顺序错误会导致路由生成失败）。
- 在 useQuery 中写 `keepPreviousData: true`（v5 已移除该顶层选项，必须改用 `placeholderData: keepPreviousData`，判定字段为 `isPlaceholderData`）。
- 在 `src/api.ts` 中创建 `QueryClient`（仅 `createServiceClient` 集中导出）。

---

## 3. App 壳层与 antd 6 约束

对应 [frontend-conventions §3](../references/frontend-conventions.md#3-app-壳层与-provider) 与 [§4](../references/frontend-conventions.md#4-ui-组件库约束)。

启动流程：

```
main.tsx
  createRouter(routeTree)
  createApp(router)
  wait i18n initialized
  router.update({ context: { i18n, queryClient } })
  createRoot(root).render(<App />)

app/App.tsx
  ThemeContext.Provider
    ConfigProvider(locale, theme + cssVar)
      AntdApp
        QueryClientProvider
          RouterProvider
```

Provider 顺序固定为：`ThemeContext.Provider` → `ConfigProvider` → `AntdApp` → `QueryClientProvider` → `RouterProvider`。

- `QueryClient` 单例创建在 `src/lib/query-client.ts`，由 `app/App.tsx` 注入 `QueryClientProvider`。
- HMR dispose 时解绑 i18n `initialized` handler，避免重复 render。

antd 6：

- 根部只有一个 `ConfigProvider`。需要局部主题时使用嵌套 `ConfigProvider`，但必须有明确业务原因。
- `AntdApp` 必须在 `ConfigProvider` 下。业务组件使用 `const { message, modal, notification } = App.useApp()`。
- 主题优先级：全局 token → component token → `classNames` / `styles`。
- 主题配置使用 `theme={{ ...activeTheme, cssVar: { prefix: 'app' } }}`（`prefix` 由各应用统一约定）。
- `<Card>` 不作默认页面容器；页面级标题使用语义 heading 或 `Typography.Title`。

ESLint 防回归（由共享 ESLint 基线强制）：

- `no-restricted-imports`：禁 `antd` 顶层 import `message` / `notification`。
- `no-restricted-syntax`：禁 `Modal.*` 顶层调用。

禁忌（MUST NOT）：

- 调换 Provider 顺序（如 `QueryClientProvider` 放在 `ConfigProvider` 之外）。
- 把 `QueryClientProvider` 下沉到 `routes/__root.tsx`。
- 在组件 render 中 `new QueryClient()` / `createConnectTransport()` / `createRouter()`。
- 顶层 import 并调用 `message.success(...)` / `notification.open(...)` / `Modal.confirm(...)`。
- 引入 `ConfigProvider.config({ holderRender })` 作为静态调用例外口（`App.useApp()` 是唯一合法路径）。
- 引入 `@ant-design/v5-patch-for-react-19`（antd 6 已移除该 patch 的需求）。
- 依赖 `.ant-*` 内部 DOM 类名做大范围样式覆盖。

---

## 4. React 19 约束

对应 [frontend-conventions §5](../references/frontend-conventions.md#5-渲染层约束)。

- 页面组件保持纯渲染；网络请求放 TanStack Query、route loader 或明确 event action 中。
- 大路由 chunk 使用 TanStack Router code splitting；route `pendingComponent` / `errorComponent` 提供局部反馈。
- 表单提交、保存、删除等 action 使用 antd `Button loading`、Query mutation 状态或 React transition 的局部 pending。
- 手写 `startTransition` 只用于本地昂贵状态切换。

禁忌（MUST NOT）：

- 在 route `beforeLoad` / 普通工具函数 / Connect interceptor 中调用 React hooks。
- 在组件 render 中 new 长期对象（router / queryClient / transport / i18n / store）。
- 把 router navigation 包在 `startTransition` 中（TanStack Router 内部已处理 transition）。
- 用全屏 spinner 阻塞用户。

---

## 5. TanStack Router 文件路由命名

对应 [naming-conventions §10](../references/naming-conventions.md#10-前端路由命名规约)。该节的通用条款适用于任何文件路由体系；本栈的具体符号约定（`__root.tsx`、`_` pathless layout、`$` 动态段、`-` 前缀排除）以 TanStack Router 官方 [File Naming](https://tanstack.com/router/latest/docs/routing/file-naming-conventions) 为准。

---

## 6. i18n 三层同步

对应 [i18n-conventions §5](../references/i18n-conventions.md#5-三层同步强制) 与 [§8](../references/i18n-conventions.md#8-运行时失败与降级约束强制)。

| 层 | 同步动作 | 触发时机 |
| --- | --- | --- |
| react-i18next | `i18n.changeLanguage(locale)` | 语言切换时 |
| antd ConfigProvider | `getAntdLocale(locale)` 动态 import | 响应 `languageChanged` 事件 |
| dayjs | `dayjs.locale(getDayjsLocale(locale))` | 响应 `languageChanged` 事件 |

降级约束：

- `i18n.changeLanguage(locale)` 成功后，antd / dayjs 的同步 SHOULD 继续执行。
- `getAntdLocale(locale)` 动态 import 失败时，MUST NOT 回滚 react-i18next 的当前语言；antd 组件可暂时保持切换前语言，并输出 warning 日志。
- `dayjs.locale(...)` 对应 locale 缺失时，MUST NOT 阻塞页面渲染，并输出 warning 日志。
- 禁止使用 `i18next-browser-languagedetector` 库。
- i18next 缺失 key 时的默认行为是**返回 key 字符串本身**，在 UI 上非常显眼，能让开发者 / QA 第一时间发现问题——MUST NOT 配置成静默回退空串。

---

## 7. 日期渲染的库落点

对应 [frontend-conventions §6.2](../references/frontend-conventions.md#62-日期时间字段datetime--date-字符串)。

- 共享 datetime helper 内部 MAY 使用 dayjs；dayjs token `YYYY-MM-DD` 等价于规范 §6.1 的 `yyyy-MM-dd`，仅大小写差异。
- 构造发给后端的 ISO 用 `dayjs(x).format('YYYY-MM-DDTHH:mm:ssZ')` 保留时区。
- 金额计算的 helper 内 MAY 使用 `big.js`，并 MUST 从 `DecimalString` 构造。
