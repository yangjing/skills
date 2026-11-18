---
status: active
last_updated: 2026-11-06
---

# 栈适配层：微信小程序 Skyline + glass-easel

> **适配对象**：[`../references/frontend-conventions.md`](../references/frontend-conventions.md)（全册——skyline 分栈下的形态替换）+ [`../references/SPECIFICATION.md` §13.1](../references/SPECIFICATION.md#131-测试分层)（测试通道落地形态）
> **规范语言**：BCP 14（RFC 2119/8174）
> **本层职责**：微信小程序原生开发（无框架 TypeScript + skyline 渲染 + glass-easel 组件框架 + 开发者工具内置编译插件）的生态细则。**MUST NOT 写项目路径、包名、appid、密钥名**（属项目 overlay）；**MUST NOT 复制 references 条款正文**（违反 SSOT，改为链接）

## 0. Agent 执行协议

1. **Trigger**：项目含微信小程序端（skyline 渲染 + 无框架 TypeScript），且命中 frontend-conventions 或 [SPECIFICATION §13.1](../references/SPECIFICATION.md#131-测试分层) 时，MUST 一并加载本文。
2. **Load**：只读命中节；MUST NOT 预读全文。
3. **Apply**：职责边界与硬要求以 `references/` 为准，本文只覆盖 skyline / glass-easel / 开发者工具链的具体形态；路径、命令、appid、预览密钥通道以项目 overlay 为准。
4. **Conflict / Stop**：本文与 `references/` 原则冲突时，MUST 以 `references/` 为准并报告本文需修订；真机行为与本文冲突时，MUST 以真机为事实并停止报告。skyline 处于演进期，本文带日期的实证结论跨基础库 / 工具版本 MUST 复核后再依赖。
5. **Output**：交付说明 MUST 点名依据的适配节号与跑过的门禁（tsc type-check / 真机预览）。
6. **MUST NOT**：MUST NOT 把本文条款当作 webview 渲染模式或第三方框架（Taro / uni-app）小程序的依据。

---

## 1. 本栈采纳的结论

对应 [frontend-conventions §1](../references/frontend-conventions.md#1-采纳的结论)。下表只记**本栈做出的选择**：

| 主题 | 本栈采纳 |
| --- | --- |
| 渲染与组件框架 | skyline + glass-easel，app.json 四件套**全局声明**：`renderer: "skyline"` + `componentFramework: "glass-easel"` + `lazyCodeLoading: "requiredComponents"` + `rendererOptions.skyline`；页面 json MUST NOT 重复声明，继承全局 |
| 语言与编译 | TypeScript 由开发者工具内置编译插件**逐文件转译，无构建链**（无打包器、无模块解析） |
| worklet | 默认关闭，动效只走 CSS（本行为默认档；项目启用 worklet 属项目裁决，MUST 在项目 overlay 登记） |
| 原生导航栏 | 不可用（skyline 不支持）——`window.navigationStyle: custom` + 每页自绘导航组件（含状态栏高度占位） |

### 1.1 官方文档

- app.json 全局配置（renderer / componentFramework / lazyCodeLoading / rendererOptions）：[微信开放文档 · 全局配置](https://developers.weixin.qq.com/miniprogram/dev/reference/configuration/app.html)
- 自定义 tabBar（skyline 适配要求：根组件 `pointer-events: auto` 与定位自声明）：[微信开放文档 · 自定义 tabBar](https://developers.weixin.qq.com/miniprogram/dev/framework/ability/custom-tabbar.html)
- skyline 宿主容器根节点默认 `pointer-events: none` 的机制说明：[微信开放文档 · 全局工具栏 app-bar](https://developers.weixin.qq.com/miniprogram/dev/framework/runtime/skyline/appbar.html)
- wx.showModal 参数表（confirmText/cancelText「最多 4 个字符」上限原文）：[微信开放文档 · wx.showModal](https://developers.weixin.qq.com/miniprogram/dev/api/ui/interaction/wx.showModal.html)

---

## 2. 测试通道形态（对应 [SPECIFICATION §13.1](../references/SPECIFICATION.md#131-测试分层)）

- 无构建链 → 静态通道 = `tsc --noEmit`（逐文件转译不做模块级分析）。
- 真机通道 = miniprogram-ci preview 出预览二维码（需正式 appid + 上传私钥，均属项目 overlay）；真机 UAT 走该二维码人工签收。
- **开发者工具模拟器与真机存在行为差**：命中测试 / 事件派发类缺陷（点击穿透、事件不触发）在模拟器上 MAY 不复现——判定 MUST 以真机为准，模拟器通过不构成证据（2026-10-09 实证：自定义 tabBar 点击穿透，模拟器正常、真机整条栏死钮）。

---

## 3. 渲染层形态（对应 [frontend-conventions §5](../references/frontend-conventions.md#5-渲染层约束)）

- 页面级滚动 MUST 用 scroll-view 承载局部滚动，MUST NOT 依赖 webview 式全局滚动。
- `scroll-view`（type=list）的子节点拉伸需父级 flex + 子级 `align-self` 显式声明，否则拉伸不生效。
- 动效只做 `transform` / `opacity`（skyline 光栅化约束；worklet 默认关闭，见 §1）。
- `aspect-ratio` 高度解析异常 → 定比容器 MUST 用显式高度。

---

## 4. 远程数据与模块接入形态（对应 [frontend-conventions §6](../references/frontend-conventions.md#6-远程数据约定)）

无构建链的模块纪律（开发者工具编译插件不做模块打包与裸模块解析）：

- 源码 import MUST 全相对路径。
- npm 依赖（含 monorepo 内共享包的生成码）MUST 经「构建 npm」（miniprogram_npm）通道或端内手写镜像模块收口，MUST NOT 源码直接裸 import——两通道的选择由项目 overlay 登记。
- 端内手写消费 Connect-JSON wire 时：字段大小写与省略语义 MUST 对齐 proto JSON 映射（空 repeated 字段序列化侧省略——列表访问 MUST 兜底空值），并以实跑 fixture 校验。

---

## 5. 样式形态（对应 [frontend-conventions §7](../references/frontend-conventions.md#7-样式约定)）

skyline WXSS 与 web CSS 的差异：

- MUST NOT 用 `clip-path`——skyline 不支持。
- **伪元素条款修订（2026-10-26）**：原「skyline 不支持伪元素」前提作废——官方 WXSS 文档选择器表现列伪元素 `::before {}` / `::after {}` 为 ✓（且仅此两个；2026-08-25 文档错误修正）。装饰性视觉维持实体 view 判例不入伪元素；但**组件默认样式的伪元素复位允许且必要时必须**——`button` 默认边框（含圆角）画在 `::after` 且 border / border-radius 简写「支持解析但以展开属性为准」（官方属性表注），本体简写清零压不过组件默认展开属性，复位 MUST 展开长属性 + `::after` 边框清零双管（2026-10-26 真机取证：chooseAvatar 头像按钮灰框 = 精确按钮盒圆角发丝线，像素测量与按钮盒 84×84 重合；profile `.head-avatar-btn` 判例，全仓 8 处原生 button 同批收敛）。伪元素用位属真机差类，新增 MUST 真机复核。
- CSS 变量 MUST 定义在 `page` 选择器。
- **z-index 只在同层级节点间有效**（无 Web 标准层叠上下文）——浮层梯子（遮罩 / 弹层 / 固定底栏 / tabBar）MUST 设计为同级节点以 z-index 分层，跨层级嵌套的 z-index 声明无效。
- **组件样式隔离**：glass-easel 默认 `styleIsolation: isolated`——app.wxss / 页面 wxss 的类选择器不作用于自定义组件内部节点，「组件 wxss 留空复用全局类」不成立，组件 MUST 自带其 wxml 用到的全部类（2026-10-09 实证：弹层组件裸文本沉底、无遮罩无卡片；开发者工具模拟器通道。样式匹配属框架确定性语义，非 §2 命中测试类真机差，但按本节惯例版本升级时复核）。CSS 自定义属性按树继承、不受隔离影响，组件内可消费 `page` 选择器定义的变量。
- **盒模型默认 content-box**：`rendererOptions.skyline.defaultContentBox: true`（webview 对齐推荐档）下 `width` 百分比与 `padding` 并用的节点 MUST 显式 `box-sizing: border-box`——否则 `2×(50%−gap/2)+2×padding` 超宽，`flex-wrap` 网格逐卡换行退化为单列（2026-10-09 实证：模板卡网格，模拟器通道）。
- **flex 列内文本不回绕**：`align-items: flex-start` 的 flex 列中 `<text>` 按 fit-content（最长行）排开、不换行、溢出容器——文本子节点 SHOULD 交给默认 stretch 拉满换行，需收窄的节点单独 `align-self: flex-start`（2026-10-09 实证：卡片描述溢出卡外，模拟器通道）。**`align-items: center` 同病**（凡显式非 stretch 交叉对齐都不给 `<text>` 换行边界）：居中列内长文案按 max-content 单行排开、向可视区两侧溢出截断——需保持居中视觉的文案节点用 `align-self: stretch` + `text-align: center` 组合（stretch 取得换行边界、text-align 补偿对齐；两属性均在 skyline 完全支持列表），MUST NOT 只写 `text-align: center`（无宽度来源仍不换行）（2026-11-06 真机实证：空态提示长文案两侧截断；空态组件 + 全局镜像空态类同批收敛）。
- 固定底栏（含 tabBar）MUST `calc(… + env(safe-area-inset-bottom))` 让位全面屏安全区：栏体**背景**延伸进安全区，可点内容让出。**吸底让位空间 MUST 放滚动内容尾部 spacer，MUST NOT 用 scroll-view 自身 `padding-bottom`**：skyline list 型 scroll-view 把自身 padding 当内容死区——子节点只在 content-box 内布局与绘制，可视底线 = 容器底边 − padding-bottom，与有无 fixed 底栏及其高度**零相关**，该 padding 整段表现为底栏上方恒定空白带（2026-10-14 实证：padding-bottom 78px+safe-area，内容恰截于容器底边 −112px 且底栏改高零响应；滚动内容尾 spacer 化后空白带消失；开发者工具模拟器通道，布局语义属确定性类非 §2 命中测试类真机差；修复经真机验收）。
- **行内分隔线 MUST NOT 用绝对定位节点**：list 型 scroll-view 内，行数据异步 setData 触发重排时，行内 `position:absolute`（left+right+bottom 三边约束）的分隔线节点会被错位重排——横向按页面根容器解析（穿出卡片边界直至屏幕边），纵向落 flex 静态位（行垂直中心），并与原位分隔线**并存为多出的一条杂线**（2026-10-20 真机实证：设置组行值文本 `''`→异步回填后出现；取证判别口径 = 杂线横向跨度呈页面根容器几何、纵向恰为行文本块垂直中心、色值不匹配分隔线 token、条数比 wxml 分隔线节点数多一——区别于「分隔线整体错位」型）。官方兼容文档「Skyline 下 absolute 相对坐标不准」类。修复形态 = 分隔线改**行间流内元素**（无任何定位属性，侧向 inset 用 margin-left 表达），改全局形态时 MUST 先全仓盘点用位（行内 / 组内兄弟两类）逐一迁移——flex 行内的流内节点会横向占位，行内用位 MUST NOT 原地留置；流内元素结构上不可能脱离行间位置，是唯一对该错位类免疫的分隔线形态。

---

## 6. tap 与操作出口形态（对应 [frontend-conventions §9](../references/frontend-conventions.md#9-操作出口与异步反馈跨端通用)）

skyline + glass-easel 工具链的事件派发形态（[frontend-conventions §9.2](../references/frontend-conventions.md#92-动作反馈死按钮禁止) 死按钮原则的落地）：

- tap 绑定一律 `bind:tap`；容器关闭 / 含内层动作的行 handler MUST 加冒泡守卫（`e.target !== e.currentTarget` 即 return），守卫 MUST 只落在容器 / 遮罩自己的 handler 上——动作出口按钮（叶子，子节点仅文案 text / 图标）MUST NOT 与遮罩共享带守卫的 handler；导航类 handler 加 ~400ms 节流防双触发重复入栈。
- **实证登记（待复核）**：2026-10-09 遮罩与「取消」按钮共享同一带守卫 handler → 点在按钮文案 text 上 `target` 为该子节点（glass-easel 事件对象语义，源组件 = 命中的最内节点），守卫误判为内层动作即 return，按钮标签区零反馈死钮（收货地址弹窗真机报告；JS 事件对象语义属确定性类，非 §2 命中测试类真机差）——修复与形态 = 遮罩专用带守卫 handler + 按钮独立无守卫 handler（全仓同类 10 处已按此收敛）。
- **实证登记（待复核）**：2026-10-09 工具链下组件内 `catch:tap` 不触发（自绘导航栏返回键真点死钮，改 `bind:tap` 即活）——单例实证，基础库 / 工具升级时 MUST 复核，MAY 随版本修复转正或作废。
- **wx.showModal 按钮文字 4 字上限 + 类型词纪律（2026-11-06 实报回流）**：confirmText/cancelText 各最多 4 个字符（官方参数表明文，见 §1.1），**超限调用直接 fail（`showModal:fail`）且弹窗整个不显示**——开发者工具模拟器 MAY 照常弹出，判定 MUST 以真机为准（§2）。三层纪律：
  1. 按钮只放类型式短词（确定 / 取消 / 删除 / 清空 / 知道了 / 去设置 / 继续 等 ≤4 字动词或状态词）；业务宾语与流程语义（「取消抽奖」「立即终摇」「标记已领取」类）下沉 **title**（承载完整语义，无字数上限）与 **content**（承载明细，支持换行）。
  2. **变量注入是隐性超限面**——confirmText/cancelText 绑运行时变量时字面扫描报不出：动态文案的按钮位 MUST 收敛为常量类型词，变量语义只进 title（实证：抽奖履约标记 `confirmText: label`，label 运行时 5 字 → 该弹窗整条死路）。
  3. fail 回调 MUST 有可见兜底（toast 承接结果告知或等效反馈），MUST NOT 静默 resolve——超限 + 静默 = 操作已在服务端成功、端上零反馈，用户盲重试双落行（实证：创建成功弹窗 6 字 confirmText 超限静默，用户 7 秒后重复提交，服务端双落库）。落地形态 = **端内薄封装唯一收口**（`wx.showModal` 裸调禁用，经封装统一：fail 默认可见兜底（可定制 / 站点自带时可关）+ 4 字超限运行时回退默认按钮文案 + 旧安卓「fail cancel」取消分流；配套静态门禁扫描禁裸调）。

---

## 7. 自定义 tabBar 形态（对应 [frontend-conventions §10](../references/frontend-conventions.md#10-控件组件层与跨端清单口径跨端通用)）

app.json `tabBar.custom: true` + 根目录 `custom-tab-bar/index` 组件（目录名框架固定，不可改）在 skyline 下的形态：

- **根节点 MUST `pointer-events: auto`**：宿主容器默认 `pointer-events: none` 且被子节点继承——缺省则整条栏渲染正常但命中测试全穿透（真点死钮；官方自定义 tabBar 文档 skyline 适配要求原文，2026-10-09 真机实证）。
- **定位 MUST 自声明**：skyline 下框架不再代为固定底部（webview 才有框架代办的 fixed 包装容器），缺省渲染进页面流顶部；`fixed` / `absolute` 均可，安全区让位见 §5。
- **`getTabBar` 官方仅有同步签名**（文档与 typings 一致，未区分渲染引擎）：返回当前页 tabBar 组件实例，未就绪 / 非 tab 页为 `undefined`——tab 页 onShow 高亮同步 MUST 成员调用 + 判空（`this.getTabBar()?.setData(...)`）。**MUST NOT 拆成裸函数调用**：`this` 丢失即被基础库实例守卫拒绝，抛 `Method should be called on a valid component instance`（2026-10-09 实证，开发者工具模拟器通道 lib 3.17.2；JS 调用语义属确定性类，非 §2 命中测试类真机差）。
- 中央凸起钮（FAB）SHOULD 把 tap 目标绑在整段插槽而非仅视觉圆钮（扩大命中面）；负 margin 上移只改视觉，不改变命中域。

---

## 8. 依赖开关与生态细则

| 能力 | 依赖 / 开关 | 缺失时的失败形态 |
| --- | --- | --- |
| skyline 四件套 | app.json：renderer + componentFramework + lazyCodeLoading + rendererOptions.skyline | 真机白屏 / 动效失效 / 组件行为回退 webview 语义 |
| 自定义 tabBar | `tabBar.custom: true` + `custom-tab-bar/index` 组件四件 | skyline 下整条栏点击穿透（§7 pointer-events 缺省形态） |
| TypeScript 编译 | 开发者工具 `useCompilerPlugins` 含 `typescript` | `.ts` 不转译，直接报语法错 |
| 真机预览通道 | miniprogram-ci + 正式 appid + 上传私钥 | 无法出预览二维码，真机 UAT 通道不可用 |
| 朋友圈单页模式 × skyline（b055 实证 2026-10-26） | 官方分享指引 + `singlePage.navigationBarFit`（基础库 ≥2.11.3）；skyline 兼容性无明示条款，但基础库 **v2.28.1（2022-12-05）发布日志**有「修复 框架 skyline 组件补全单页模式相关逻辑」——skyline 组件对单页模式有专门框架级处理（受支持组合的证据） | **开发者工具编译模式无法复现单页容器**（官方「特殊场景调试」文档不含 1154；编译模式场景值只改 `getLaunchOptionsSync().scene` 返回值）——单页容器渲染 MUST 真机朋友圈实链取证，模拟器通过不构成证据 |
| map 组件（轨迹渲染） | 基础库 map 组件（skyline 完全支持；polyline + marker + include-points） | **开发者工具暂不支持 map 调试（官方组件支持表明示）——渲染验证 MUST 真机预览，工具内渲染结果不构成证据**（2026-10-15 实证登记：b026 徒步路线块；polyline 点数无官方上限，超量卡顿为社区口径非官方——抽稀参数自测定档；`rendererOptions` 官方键清单不含 map 专项子键，写未知键被 lib 3.17.2 校验器拒） |

---

## 9. 换栈映射判据

换掉本栈时，被适配条款中**哪些要改、哪些不能改**：

| 条款 | 性质 | 换栈时 |
| --- | --- | --- |
| 死按钮禁止 / 动作出口完备（frontend-conventions §9 原则） | 硬要求 | **不变** |
| 事件与命中测试差异以真机为事实，模拟器通过不构成证据 | 硬要求 | **不变** |
| 手写消费 wire MUST 对齐序列化 casing 与省略语义并以 fixture 校验 | 硬要求 | **不变** |
| `bind:tap` + 冒泡守卫 + 导航节流 / tabBar 根节点 `pointer-events: auto` / 定位自声明 / `getTabBar` 同步成员调用+判空 | 形态 | **替换**为目标平台事件派发与容器机制 |
| 四件套 / scroll-view 局部滚动 / 禁 clip-path·伪元素 / `page` 选择器变量 / z-index 同层约束 / safe-area 让位 | 形态 | **替换**为目标渲染引擎等价物 |
| 相对路径 import / miniprogram_npm 或手写镜像收口 | 形态 | **替换**为构建链下的正常模块解析（引入构建链时本组自然失效） |
| `tsc --noEmit` + miniprogram-ci preview 测试通道 | 形态 | **替换**为目标平台静态检查与真机通道 |

---

## 10. WXML 编译域与表达式语法

WXML 模板语法域（开发者工具整包编译；2026-10-10 实证，模拟器通道）：

- `{{}}` 插值表达式只支持简单 JS 表达式（三元 / 逻辑 / 算术 / 字符串拼接）。**模板字符串（反引号 + `${}`）MUST NOT 用于 WXML 表达式**——编译期 Fatal `unexpected character inside expression`；带计数插值用拼接（`'已上传 ' + n + ' 份'`）。
- **单文件编译 Fatal 毒化整包**：全部页面 wxml 编译为一个 bundle，任一文件 Fatal → 所有页面零渲染（当前页黑屏且完全无响应），报错文件与受害页面可以无关——排障 MUST 先看 Console 编译诊断，MUST NOT 只盯当前页面。编译 Note（如 `avoid uppercase letters`）不阻塞渲染（同场实证）。
- **`data-*` 属性名 MUST 全小写**：dataset 键由连字符转驼峰（`data-v-idx` → `dataset.vIdx`），属性名中的大写字母被运行时静默转小写 → TS 侧按驼峰读取必然键错位，并触发编译 Note。
- 静态护栏形态（本栈无构建链，tsc 不解析 wxml，此类语法错无静态通道）：对全部 `.wxml` grep 两模式——反引号、`data-` 属性名含大写字母——命中即 fail；命令与挂载点属项目 overlay。

---

## 11. 开发者工具会话与自动化通道

工具链会话形态（对应 [SPECIFICATION §13.1](../references/SPECIFICATION.md#131-测试分层) 测试通道的落地面；2026-10-10 实证）：

- **模拟器 wx.request MAY 携带 `Origin: https://servicewechat.com`**（微信运行时固有 origin；与会话形态相关——经 CLI 重建的项目窗口观察到，真机 wx.request 无浏览器 Origin 语义）。本地 / 同栈后端如有 CSRF Origin 校验或 CORS 显式白名单，MUST 评估放行该 origin，否则全部非 GET RPC 被 403（实证：后端日志 `csrf guard rejected` + 同请求带 / 不带该 origin 403 / 200 对照复现）。白名单取值登记属项目 overlay。
- **miniprogram-automator 在 skyline 下元素查询受限**：仅页面顶层节点（scroll-view 之外）可查；scroll-view 内部与自定义组件内部节点不可见（实证 + 行业 skyline 适配记录一致）。可靠驱动面 = 导航（switchTab / navigateTo / redirect）+ `page.data()` 断言 + `page.callMethod` + 顶层元素；scroll-view 内交互 MUST 用像素点按或 callMethod 等价 handler 驱动，UI 弹层呈现另行截图 / 人工走查。
- **布局取证通道（2026-10-14 实证）**：元素查询受限不覆盖几何取证——`miniProgram.evaluate` 内跑 appservice 侧 `wx.createSelectorQuery()`，页面级与 **scroll-view 内部节点**均可查（子节点数量 + boundingClientRect 正常返回）；`miniProgram.systemInfo()` 亦可用，且 custom tabBar 不缩减 `windowHeight`（= screenHeight，页面视口即全屏，吸底让位完全由页面自理，见 §5）。布局类排障 SHOULD 先经此通道取几何、再以截图像素测量对照（可视边界疑点 MAY 用临时背景色区分「内容截断」与「被覆盖」）；上条 automator `page.$` 受限面不受此影响，两者结论 MUST NOT 混用。
- **实证登记（待复核）**：模拟器内 skyline scroll-view 对滚轮事件 MAY 不生效（多次滚轮零位移、拖拽手势可滚动且见回弹）——自动化滚动 MUST 验证像素确实变化后再认定到位。开发者工具 / 基础库升级时 MUST 复核，MAY 随版本修复转正或作废。
