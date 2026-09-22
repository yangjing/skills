---
status: active
version: v4  # 2026-09-01 增 §4 桥 promise 落定与原生资源生命周期 / 补 §6 交互与布局形态 / §8 换栈表扩；v3 2026-08-30 增 §7
---

# 栈适配层：React Native + iOS

> **适配对象**：[`../references/frontend-conventions.md`](../references/frontend-conventions.md)（全册——RN 壳层下的形态替换）+ [`../references/SPECIFICATION.md` §13.1](../references/SPECIFICATION.md#131-测试分层)（测试分层落地形态：jest 单测 + 模拟器冒烟 + 产物级实证）
> **规范语言**：BCP 14（RFC 2119/8174）
> **本层职责**：RN / Hermes / Metro / Xcode 构建链的生态细则。**MUST NOT 写项目路径、包名、设备名**（属项目 overlay）；**MUST NOT 复制 references 条款正文**（违反 SSOT，改为链接）

## 0. Agent 执行协议

1. **Trigger**：项目含 React Native 端（iOS 壳），且命中 frontend-conventions 或 [SPECIFICATION §13.1](../references/SPECIFICATION.md#131-测试分层) 时，MUST 一并加载本文。
2. **Load**：只读命中节；MUST NOT 预读全文。
3. **Apply**：职责边界与硬要求以 `references/` 为准，本文只覆盖 RN / iOS 构建链的具体形态；路径、版本钉版、模拟器设备与磁盘纪律以项目 overlay 为准。
4. **Conflict / Stop**：本文与 `references/` 原则冲突时，MUST 以 `references/` 为准并报告本文需修订；项目实现与本文冲突时，MUST 以实现为事实并停止报告。
5. **Output**：交付说明 MUST 点名依据的适配节号与跑过的门禁（tsc / jest / lint / format:check / xcodebuild / pod install）。
6. **MUST NOT**：MUST NOT 把本文条款当作 Web 或其它原生端的依据；MUST NOT 混入非目标架构切片的构建产物。

---

## 1. 本栈采纳的结论

对应 [frontend-conventions §1](../references/frontend-conventions.md#1-采纳的结论)。下表只记**本栈做出的选择**：

| 主题 | 本栈采纳 |
| --- | --- |
| 形态 | 单 RN 代码库出 iOS 壳；Metro bundler + Hermes 引擎 |
| 原生内核 | Swift / FFI 侧实现，RN 经 `.m` 桥（`RCT_EXTERN_METHOD`）导出调用 |
| 构建架构 | Apple Silicon 宿主 **arm64 单架构**：xcodebuild 显式 `-destination 'generic/platform=iOS Simulator' ARCHS=arm64 ONLY_ACTIVE_ARCH=YES` + `EXCLUDED_ARCHS=x86_64`；依赖产物（XCFramework 等）可再生、MUST NOT 入库，拉取同口径只取 arm64 变体 |
| 测试 | jest 单测（Hermes 语义）+ 模拟器冒烟；模拟器不可用时降级**产物级实证**（对构建产物断言，MUST NOT 宣称运行时验证） |
| lint / format | oxc 系（oxlint / oxfmt）替换模板默认 ESLint + Prettier；配置单源复用仓根 |

### 1.1 官方文档

- React Native：[官方文档](https://reactnative.dev/docs/getting-started)
- Hermes：[引擎文档](https://hermesengine.dev/)
- `react-native-get-random-values`（随机 polyfill 事实标准，入口文件副作用 import）：[GitHub](https://github.com/LinusU/react-native-get-random-values)
- Xcode build settings：[Xcode Build Setting Reference](https://developer.apple.com/documentation/xcode/build-settings-reference)

---

## 2. Hermes 运行时约束

- Hermes 可能缺 `globalThis.crypto.getRandomValues`（MUST NOT 依赖「较新 RN 内置 Web Crypto」的认知）——随机依赖 MUST 显式注入 polyfill（如 `react-native-get-random-values`），且入口文件 MUST 先于业务 import。
- 纯逻辑库的随机 fallback MUST NOT 静默确定性降级——确定性字节兜底会输出可复现的「随机」值，属安全缺陷；且 node / jest 环境有 crypto、单测测不出，随机族 MUST 以真机 / 模拟器实跑冒烟覆盖。

---

## 3. Monorepo 装配形态

- **双 React 崩溃**：共享包裸 `import react` 向上解析命中另一份 react（如仓根 node_modules）→ 运行时 `Cannot read property 'useState' of null`（官方口径：单 app 内 React 多版本必然运行时报错）。app 的 Metro resolver MUST 把 react 系列重定向到 app 自身 node_modules，且全仓 react 版本 MUST 单一钉版——可经根 package.json `resolutions` / `overrides` 强制。
- Metro 对 pnpm 默认软链隔离结构支持不全（pnpm 官方将 React Native 列为需 hoisted `node_modules` 的典型场景）。两种已验证形态**任选其一**并在项目 overlay 登记，MUST NOT 未实证混搭：① RN app 独立于 workspace、用自带锁版的包管理器安装（npm 等），workspace 显式排除；② 全仓 pnpm 切 hoisted 安装策略（`.npmrc` `node-linker=hoisted` 或 `pnpm-workspace.yaml` `nodeLinker: hoisted`）。

### 3.1 lint / format 工具链形态

- RN 官方模板默认携带 ESLint（`.eslintrc.js` extends `@react-native`）+ Prettier（`.prettierrc.js`）局部配置。替换为 oxc 系（oxlint / oxfmt）时两者**整删**，MUST NOT 另放局部 `.oxlintrc.json` / `.oxfmtrc.json`——两工具从子目录向上查找配置，monorepo 下自动复用仓根单源，局部第二份配置必与仓根漂移。
- RN app 的 devDependencies MUST 自带 oxlint / oxfmt，版本与仓根对齐（独立安装形态下仓根二进制不可达；版本漂移则两处格式化输出可能分叉）。
- 工具链迁移批 MUST 保持零格式 diff：切换前先 `oxfmt --check` 实证目标源码全绿（模板 prettier 风格与 oxfmt 通常可零 diff 达成），MUST NOT 让迁移混入海量格式重排。
- 存量 `eslint-disable` 注释族零 diff 保留——oxlint 识别该注释族（含 `react-hooks/` 等 eslint 惯例前缀别名）：命中已启用规则时抑制**实际生效**（如 `react/exhaustive-deps` 默认启用），未启用规则名静默无害。删除这类注释会立刻暴露被抑制的告警，MUST NOT 当死注释清理。
- scripts：`lint` = `oxlint .`，补齐 `format` = `oxfmt --write .` / `format:check` = `oxfmt --check .`（模板无 format script）；monorepo 门禁链路 MUST 同批切换——门禁 script 内联的 `eslint` 调用（如 `exec eslint <paths>`）是残留高发点，依赖移除后门禁必失败。
- 规则集语义：oxlint 启用集与 `@react-native/eslint-config` 不等价（如 RN 特有规则 `react-native/no-inline-styles` 无对应，hooks 族规则反而默认启用）——迁移后规则面以仓根 oxlint 配置为准，lint 覆盖变宽变窄都属预期而非回归。

---

## 4. 原生桥一致性

- `.m` 桥导出面是手工维护的平行清单：tsc 不查 `.m`、构建门禁只验编译——导出面漂移的失败形态 = 端内 `TypeError: undefined is not a function`（**构建全绿**）。
- 新增 / 变更内核方法 MUST 同步桥导出；桥面与协议面（IDL / manifest）的一致性 MUST 有机械校验（生成器或对拍），MUST NOT 依赖手工同步。
- 壳层 MUST 为页面级内容装配 ErrorBoundary（resetKey 随路由切换重置）——单页崩溃 MUST NOT 白屏整 app。
- **桥 promise MUST 兜底落定**（对应 [frontend-conventions §9.3](../references/frontend-conventions.md#93-异步落定与定时器生命周期)）：iOS 系统回调存在机型性不达（实证形态：语音识别 `finish` 后 final callback 不达——partial 正常回流但终态缺失）——收尾方 MUST 提供超时兜底出口，以已回流的部分结果落定。
- **长驻原生资源单例复用 + 会话代次守卫**：引擎级资源（audio engine / 识别器类）每次新建 = 旧实例僵尸化，新会话输入通道拿不到数据（实证形态：第二次会话起恒报「无语音」类系统错误）——MUST 模块级单例复用 + 会话级重入防御（新会话前 cancel 旧任务、重装输入 tap、状态读写收敛主队列）；异步回调 MUST 携带会话代次（epoch），stale 回调全静默——旧会话的取消回调 MUST NOT 拆掉新会话资源或污染新会话状态。

### 4.1 JSI 直绑通道工程形态（hetu-chiji r422 回流，2026-09-09）

- **装载时序**（react-native-quick-crypto `install()` 先例同款）：JS 侧入口（Metro 首行 polyfill 后）调 `RCT_EXPORT_BLOCKING_SYNCHRONOUS_METHOD(installXxx)` → `(RCTCxxBridge *)bridge` runtime cast → `HostObject` 挂 global 属性（幂等：已在则 true）；bridgeless / 模块缺失 no-op 回 false，通道选择层据此回退（fail-closed 语义归通道单源函数）。
- **零拷贝类型边界**：出参 = `Runtime::createArrayBuffer(std::make_shared<MutableBuffer>)`（自定义 MutableBuffer 包 native 堆缓冲，析构回 C ABI `free_buffer`——**真零拷贝**，无拷贝构造）；入参 ArrayBuffer 直取 data()，TypedArray MUST 经 buffer+byteOffset+length 视图（bare `asUint8Array` 陷阱）；字符串出参 `String::createFromUtf8` 后即释放源缓冲。
- **C++ 编译坑位（Xcode 26 / RN 新架构头）**：头文件裸 `jsi::` MUST 全限定 `facebook::jsi::`（不同传递包含层级下命名空间查找不稳）；`std::vector<jsi::PropNameID>` braced-init 拷贝构造已删（Pointer 移动独占）——用 `push_back`；podspec 现代分支需 `s.dependency 'React'`（jsi / RCTBridge+Private 头）。
- **失败形态登记**：JSI 安装失败无异常抛出（silent false）——消费面 MUST 经通道单源函数 fail-closed（throw 中文引导重装文案），MUST NOT 散落 `globalThis.Xxx` 直取；错误串经 C ABI `take_last_error` → `JSError`（串释放勿漏）。
- 受阻经验：无（本批一次落地）；参照实现 = hetu-chiji `apps/chiji-rn/ios/ChijiBridgeModule/ChijiJSIHostObject.mm`。

---

## 5. 测试通道形态（对应 [SPECIFICATION §13.1](../references/SPECIFICATION.md#131-测试分层)）

- iOS 模拟器程序化文本注入（idb / HID）受输入法态（自动大写 / 自动纠正）污染——注入前 MUST 清理模拟器输入法；判读以截图 / dump 为准。
- 同机多模拟器栈（iOS CoreSimulator 与 HarmonyOS Emulator 等）MUST 串行联调（磁盘约束）；启停与缓存清理命令由项目 overlay 登记。

---

## 6. 交互与布局形态

- **ScrollView 自带默认 `flexGrow: 1`（双向坑）**：其一，非列表位滚动面（横向装饰滚动行）在纵向布局里吃掉全部剩余高度，`minHeight` 拦不住（实证形态：横向胶囊行与后续卡片间数倍空白）——MUST 显式 `flexGrow: 0`；其二（反向），主列表滚动面的 `contentContainerStyle` MUST 保底 `flexGrow: 1` 且 MUST NOT `flex: 1`（压缩到视口高 = 判定不可滚）。两向同源：flex 默认值不区分「装饰滚动行」与「主滚动面」，意图 MUST 显式声明。
- **Pressable 默认保留区小**：按压后手指拖出组件边界即触发 `onPressOut`——「拖出取消」类手势（上滑取消等）来不及呈现取消提示即被误触发。长按拖动取消类交互 MUST 扩 `pressRetentionOffset` 保留区（取值属项目 overlay）。
- **Modal 无系统关闭位**：iOS Modal 非 slide-to-dismiss、遮罩点击默认不关闭——弹层显式取消出口（[frontend-conventions §9.1](../references/frontend-conventions.md#91-操作出口完备)）在 RN 侧 MUST 自带按钮位，MUST NOT 指望系统手势。

---

## 7. 表单与键盘形态（对应 [frontend-conventions §8](../references/frontend-conventions.md#8-表单交互与敏感值跨端通用)）

- **`InputAccessoryView` 在全屏 Modal / 新架构下不透出**（真机两轮实证；导航栏「完成」钮在键盘场景不显眼）——键盘收起 MUST 自绘浮条：监听键盘显隐取高度，`position: absolute` 贴键盘上沿渲染工具条，键盘不可见零渲染。
- **iOS 数字键盘（decimal-pad 类）无 return key、系统无收起位**——显式收起通道 = 自绘浮条 + `keyboardDismissMode="on-drag"`（下滑滚动收起，iOS 惯例）。
- **兄弟 Modal 层级互盖**：Modal 宿主内再开日期滚轮 Modal（兄弟节点）时点按无反应、父 Modal 关闭后子 Modal 才露出——多字段表单 MUST 页面化（独立二级页，返回回列表页），选择器成为普通页上的单层 Modal；MUST NOT 在表单 Modal 内再开选择器 Modal。
- **键盘避让容器**：共享容器组件统一装配——`KeyboardAvoidingView`（iOS `behavior="padding"`）+ `keyboardShouldPersistTaps="handled"` + 键盘显隐监听对聚焦输入框 `measureInWindow` 判遮挡量滚动（聚焦框坐标由框架 API 现取，零逐框接线）。新表单 MUST 消费共享容器，MUST NOT 逐屏手写避让（存量手写面随接触面迁移，不强制回改）。
- **日期选择**：社区 datetimepicker（`display="spinner"` 滚轮 + 取消 / 确定工具行，draft 滚动、确定回写并关闭，对应 frontend-conventions §8.3）。
- **键盘布局属性 = `keyboardType`**（对应 frontend-conventions §8.2）：数值字段 `number-pad` / `decimal-pad`；字符过滤（`maxLength` + 过滤函数）只拦非法输入，MUST NOT 视为键盘布局切换。

---

## 8. 换栈映射判据

换掉本栈时，被适配条款中**哪些要改、哪些不能改**：

| 条款 | 性质 | 换栈时 |
| --- | --- | --- |
| 随机源缺失 MUST 显式失败或显式注入，MUST NOT 静默确定性降级 | 硬要求 | **不变** |
| 桥面与协议面一致性 MUST 有机械校验 | 硬要求 | **不变** |
| 桥 promise 兜底落定 / 长驻原生资源单例复用 + 会话代次守卫（frontend-conventions §9.3 原则） | 硬要求 | **不变** |
| 页面级 ErrorBoundary（崩溃不殃及整 app） | 硬要求 | **不变** |
| 键盘在场时聚焦框与提交动作可见可达（frontend-conventions §8.2 原则） | 硬要求 | **不变** |
| `InputAccessoryView` 不透出 → 自绘浮条 / 兄弟 Modal 互盖 → 表单页面化 / KAV + measureInWindow 避让容器 / datetimepicker spinner | 形态 | **替换**为目标平台等价物（自绘件、页面路由、避让 API、选择器） |
| ScrollView `flexGrow` 双向显式声明 / `pressRetentionOffset` 保留区 / Modal 自带取消出口 | 形态 | **替换**为目标平台等价物（滚动容器默认值、按压保留区 API、模态关闭惯例） |
| Metro / Hermes / `.m` RCT 桥 / arm64 构建参数 / xcodebuild + CocoaPods | 形态 | **替换**为目标构建链与运行时 |
| oxc 系 lint / format 工具链与配置单源复用 | 形态 | **替换**为目标语言 / 构建链的 lint / format 工具 |
