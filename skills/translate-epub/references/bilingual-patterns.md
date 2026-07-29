# 双语翻译 HTML 模式详解

> 本文件是 SKILL.md「Translation rules」的补充，详述各类元素的双语转换正确模式。
> 翻译时按元素类型对号入座。核心原则：**译文复用原文标签结构与 CSS class，作为独立兄弟元素
> 紧跟原文之后**。

---

## 1. 标题（h1 / h2 / h3）

原文标题含章节编号（可能嵌在 `<span>` 里）。译文用**同标签同 class**的独立元素，紧跟原文。

```html
<!-- 原文 -->
<h2 class=" readable-text-h2"><span class="num-string">1.1</span> Defining agents</h2>
<!-- 译文（同 h2 + 同 class，去掉编号 span，纯文本） -->
<h2 class=" readable-text-h2">定义智能体</h2>
```

```html
<!-- 章标题 -->
<h1 class=" readable-text-h1"><span class="chapter-title-numbering"><span class="num-string">1</span> </span><span class="chapter-title-text">The rise of AI agents</span></h1>
<h1 class=" readable-text-h1">AI 智能体的崛起</h1>
```

特殊：`<h3 class="introduction-header">`（"本章覆盖"标题）同样复用该 class。

---

## 2. 正文段落（p）

原文 `<p>` 可能有 class（如 `intended-text`）或无 class。译文用**相同标签**。

```html
<!-- 无 class -->
<p>By themselves, LLM-based apps can generate responses.</p>
<p>就其本身而言，基于 LLM 的应用可以生成回复。</p>

<!-- 有 class（译文同样带 class） -->
<p class="intended-text">This book is about building agents.</p>
<p class="intended-text">本书讲述如何构建智能体。</p>
```

原文段落内含 `<em>`（斜体强调）时，译文也用 `<em>` 包裹对应中文词：
```html
<p>The concept of an <em>agent</em> is not new.</p>
<p>「<em>智能体</em>」（agent）这个概念并不新鲜。</p>
```

---

## 3. 图注（h5.figure-container-h5）

图注原文结构是 `<h5 class=" figure-container-h5"><span class="">原文</span></h5>`。
译文**复用完整嵌套结构**（h5 + span），紧跟原文 h5 之后。

```html
<h5 class=" figure-container-h5"><span class="">Figure 1.1 Common patterns for communicating with an LLM.</span></h5>
<h5 class=" figure-container-h5"><span class="">图 1.1 与 LLM 通信的常见模式。</span></h5>
```

**图注含 `<code>` 时**：译文 span 内保留 `<code>` 英文原样：
```html
<h5 class=" figure-container-h5"><span class="">The agent calls <code>list_tools</code> to discover tools.</span></h5>
<h5 class=" figure-container-h5"><span class="">智能体调用 <code>list_tools</code> 来发现工具。</span></h5>
```

> 图片本身（`<img>`）不翻译——这里只译图注文字。

---

## 4. 表标题（h5.browsable-container-h5）

```html
<h5 class=" browsable-container-h5">Table 1.1 The four LLM interaction patterns</h5>
<h5 class=" browsable-container-h5">表 1.1 四种 LLM 交互模式</h5>
```

---

## 5. 列表项（li）

译文用同标签 `<li class="readable-text">`（去掉 id），**插回同一 `<ul>` 内、紧跟原文 li 之后**，
形成「原文 li → 译文 li → 原文 li → 译文 li」交替。

```html
<ul>
  <li class="readable-text" id="p2">Defining agents and agentic thinking</li>
  <li class="readable-text">定义智能体与智能体式思维</li>
  <li class="readable-text" id="p3">Introducing the Model Context Protocol</li>
  <li class="readable-text">引入模型上下文协议</li>
</ul>
```

**列表项含 `<em>`/`<strong>` 时**：译文复用相同强调标签：
```html
<li class="readable-text" id="p102"><em>Specialization—</em>A single agent loaded with every tool tends to perform worse.</li>
<li class="readable-text"><em>专业化</em>——一个被塞满所有工具的单一智能体往往表现更差。</li>
```

> ⚠️ 列表项译文必须是 `<li>`，不能是 `<p>`（`<ul>` 只能包含 `<li>`，否则 XHTML 非法）。

---

## 6. 表格（table）

**原表格完全不动**。在其 `</table>` 之后（同一容器 div 内）追加一个**完整的新表格**，
结构、colgroup、thead/tbody、所有 CSS class 都与原表格相同，仅单元格内容为译文。

```html
<div class="browsable-container browsable-table-container">
  <h5 class=" browsable-container-h5">Table 1.1 ...</h5>
  <h5 class=" browsable-container-h5">表 1.1 ...</h5>

  <table>                              <!-- 原表格（不动） -->
    <colgroup>...</colgroup>
    <thead><tr><th class="..."><p class="_TableHead">Pattern</p></th>...</tr></thead>
    <tbody><tr><td class="..."><p class="_TableBody">Direct LLM chat</p></td>...</tr></tbody>
  </table>

  <table>                              <!-- 译文表格（相同结构 + 相同 class） -->
    <colgroup>...</colgroup>
    <thead><tr><th class="..."><p class="_TableHead">模式</p></th>...</tr></thead>
    <tbody><tr><td class="..."><p class="_TableBody">直接与 LLM 聊天</p></td>...</tr></tbody>
  </table>
</div>
```

**表格内的 `<code>`（如工具函数名）保留英文**，不译。

---

## 7. 导航文件

### toc.ncx
已译章节的 `<text>` 改为「英文 / 译文」格式：
```xml
<navLabel><text>1 The rise of AI agents / AI 智能体的崛起</text></navLabel>
<navLabel><text>1.1 Defining agents / 定义智能体</text></navLabel>
```

### contents.html（目录页）
已译章节的链接文本同样改为「英文 / 译文」：
```html
<p><strong><a href="../Text/chapter-1.html"><em>1 The rise of AI agents / AI 智能体的崛起</em></a></strong></p>
```

---

## 反模式（必须避免）

| 反模式 | 问题 |
|---|---|
| 译文用内联 `<span class="zh-translation">` 塞进原文标签内 | 不换行，与原文同行 |
| 标题译文用 `<p>` 而非 `<h2>` | 丢失标题样式 |
| 列表项译文用 `<p>` 放进 `<ul>` | XHTML 非法（ul 只能有 li） |
| 表格译文塞进原表格单元格 | 破坏原文表格 |
| 自造 CSS class（如 `zh-translation`） | 违反复用原则，样式不一致 |
| 译文元素保留原文的 `id` | id 重复，HTML 非法 |
| 全角引号 `“”` 出现在 HTML 属性 | 属性解析失败 |
