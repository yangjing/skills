---
name: translate-epub
description: >
  翻译 EPUB 电子书：先通读全文建立统一术语库，再逐章翻译，默认产出双语版本（译文显示在
  原文下方），也可仅保留译文，并可选打包成 .epub。Use this skill when the user wants to
  translate an epub/ebook — e.g. "翻译这本 epub"、"把这本书译成中文"、"生成双语版电子书"、
  "翻译电子书", even if they don't explicitly mention "epub" or "translate". Produces a
  sibling directory (e.g. book-dual / book-zh) mirroring the source structure, with
  translated HTML files.
---

<objective>
把一本 EPUB 电子书翻译成目标语言，默认产出双语版本（原文 + 译文，译文在原文下方），也可按需
仅保留译文。译文必须复用原文的 HTML 标签结构与 CSS class（仅内容换成目标语言），保证显示
效果与原文一致。全书先建术语库再翻译，确保术语统一。
</objective>

## Prerequisites

- **uv**：所有脚本通过 `uv run` 运行，依赖由脚本内联声明（PEP 723），uv 自动创建隔离环境安装。
  - 检查：`uv --version`
- 原文语言通常能从 EPUB 元数据（`content.opf` 的 `<dc:language>`）自动判断；判断失败则用 AskUserQuestion 让用户指定。
- **译文语言必须由用户指定**；若未指定，用 AskUserQuestion 询问（见 Workflow 步骤 1）。

## Available scripts

- **`scripts/inspect_epub.py`** — 探查 EPUB 结构，输出结构化 JSON：源语言、章节清单（按 spine 阅读顺序 + 行数）、TOC 路径、图片数、文本元素标签统计。**第 1 步必跑。**
  ```bash
  uv run scripts/inspect_epub.py <ebook-path>                 # .epub 文件或已解压目录
  uv run scripts/inspect_epub.py <ebook-path> --workdir DIR   # 指定解压目录
  ```
- **`scripts/validate_translation.py`** — 验证翻译后的 HTML：XHTML 标签栈配平、`<ul>` 子元素合法性、译文标签是否复用原文结构、残留旧标记检测、术语一致性抽查。**每章翻译后必跑。**
  ```bash
  uv run scripts/validate_translation.py <translated-html-path>
  uv run scripts/validate_translation.py <dir> --glossary GLOSSARY.md
  ```
- **`scripts/build_epub.py`** — 把翻译后的解压目录打包成 .epub 文件（可选）。
  ```bash
  uv run scripts/build_epub.py <source-epub-or-dir> <output.epub>
  ```

## Workflow

### 1. 确认语言与输出模式（必做）

用 AskUserQuestion 确认（若用户未指定）：
- **译文语言**（必须）：如简体中文、繁体中文、日语等。
- **显示方式**：**默认双语显示**（译文在原文下方，目录后缀 `-dual`）。仅当用户明确要求「只要译文」「不要原文」时才改为仅译文（目录后缀按语言：简中 `-zh`、繁中 `-zh-tw`、日语 `-ja`）。无需为显示方式单独提问——按默认双语执行，除非用户另有说明。
- **是否打包 epub**（默认否，保留解压目录）。
- **翻译范围**：全书 / 仅正文 / 先翻一章试效果（长书务必先试一章）。

### 2. 探查源文件，建立全景
```bash
uv run scripts/inspect_epub.py "<ebook-path>"
```
读 JSON 结果，确认：源语言、章节清单（按阅读顺序）、TOC 路径、`html_root`（正文 HTML 所在目录）。据此规划翻译批次。

### 3. 建立术语库（全书翻译前必做，单一真相源）

先通读全书（或各章已有读书笔记/目录），提取术语，产出 `GLOSSARY.md`：
- **按主题域分组**（核心概念、框架/协议、代码标识符等）。
- **代码标识符 / API 名 / 框架名 / 协议名一律保留英文**（如 `MCP`、`ReAct`、`list_tools`、`Docker`）。
- **通用概念首次出现用「中文（英文）」并陈**，后续只用中文。
- **裁决跨章节不一致的译法**，全书采用唯一译法。
- 维护约定：翻译新章节前先核对本表；遇新术语先补表再用。

术语库写在输出目录根：`<output-dir>/GLOSSARY.md`。

### 4. 复制源目录结构

把源 EPUB 原样复制到输出目录（保留图片、CSS、元数据、OEBPS 结构）：
```bash
cp -R "<source-epub-dir>" "<output-dir>"
```
输出目录名 = 源目录名 + 后缀（`-dual` / `-zh` 等），与源目录并列。

### 5. 逐章翻译（核心）

对每个正文 HTML 文件，**逐个块级元素翻译**。译文必须复用原文标签结构——这是本 skill 最关键
的规则，详见下方「## Translation rules」与 `references/bilingual-patterns.md`。

翻译顺序建议：章标题 → 正文段落 → 列表项 → 图注 → 表标题 → 表格。每章翻完立即用
`validate_translation.py` 验证，全绿后再进下一章。

### 6. 更新导航文件

- **`toc.ncx`**：把已译章节的 `<text>` 改为「英文 / 译文」（双语）或仅译文。
- **`contents.html` / 目录页**：同步更新已译章节的目录链接文本。

### 7. 验证 + 可选打包

```bash
# 全书验证
uv run scripts/validate_translation.py "<output-dir>/OEBPS/Text/" --glossary GLOSSARY.md
# 可选打包
uv run scripts/build_epub.py "<output-dir>" "<output-dir>.epub"
```

---

## Translation rules（关键，务必遵守）

### 核心原则：译文复用原文标签结构与 CSS class

译文必须用**与原文相同的 HTML 标签和 class**，仅把内容换成目标语言，作为**独立的兄弟元素**
紧跟原文之后（不在原文内部、不内联、不换用其他标签）。

✅ 正确（译文复用原文 `<h2 class="readable-text-h2">` 与 `<p>`）：
```html
<h2 class="readable-text-h2">1.1 Defining agents</h2>
<h2 class="readable-text-h2">1.1 定义智能体</h2>     <!-- 同标签同 class，独立成行 -->

<p>The concept of an agent is not new.</p>
<p>「智能体」这个概念并不新鲜。</p>              <!-- 同标签，独立段落 -->
```

❌ 错误（内联 span、换用 `<p>` 译标题、自造 class）：
```html
<h2>1.1 Defining agents <span class="zh-translation">定义智能体</span></h2>  <!-- 内联，不行 -->
<h2>1.1 Defining agents</h2><p class="zh-translation">定义智能体</p>          <!-- 标题用 p 译，不行 -->
```

### 各元素类型的处理

| 元素 | 原文标签示例 | 译文做法 |
|---|---|---|
| **标题** h1–h3 | `<h2 class="readable-text-h2">` | 同标签同 class 的独立元素，紧跟原文 |
| **正文段落** | `<p>` 或 `<p class="intended-text">` | 同标签同 class 的独立 `<p>` |
| **图注** h5 | `<h5 class="figure-container-h5"><span class="">原文</span></h5>` | 同结构 `<h5 class="figure-container-h5"><span class="">译文</span></h5>` |
| **表标题** h5 | `<h5 class="browsable-container-h5">Table 1.1 ...</h5>` | 同标签的独立 `<h5>` |
| **列表项** li | `<li class="readable-text">原文</li>` | 同标签的 `<li>`，**插回同一 `<ul>` 内、紧跟原文 li 之后**（原文→译文交替） |
| **表格** table | `<table>...原文单元格...</table>` | **原表格不动**，在其下方追加一个**完整的新表格**（相同结构、相同 colgroup/thead/tbody、相同 CSS class），单元格内容为译文 |
| **图片** img | `<img src="...">` | **不翻译**（图片本身无需处理） |
| **代码** `<code>` | `<code>list_tools</code>` | 保留英文，不译 |

### Gotchas（踩过的坑，务必规避）

- **`<ul>` 只能包含 `<li>`**：列表项译文必须是 `<li>`（不能是 `<p>`），且放回 `<ul>` 内。XHTML 非法会导致 EPUB 阅读器渲染异常。
- **全角引号**：EPUB 里 HTML 属性若出现中文全角引号 `“”`，必须修正为半角 `"`，否则属性解析失败。
- **表格不拆单元格内译**：不要把译文塞进原表格单元格（会破坏原文表格）。而是在原表格后加一个完整译文表格。
- **图注含 `<code>` 时**：译文 `<h5><span>` 内保留 `<code>` 英文原样。
- **不要自造 CSS class**（如 `zh-translation`）：译文靠复用原文 class 获得样式，无需额外 CSS。若加了自定义 class，说明违反了复用原则。
- **id 去重**：译文元素复用原文标签时去掉 `id` 属性，避免与原文元素 id 重复。

### 验证门（每章必过）

`validate_translation.py` 检查项全绿才算完成：
1. XHTML 标签栈配平（0 错误）
2. `<ul>` 直接子元素全为 `<li>`
3. 无残留自定义标记（如 `class="zh-translation"`）
4. 译文元素与原文元素标签一致（抽查）

---

## 输出目录结构

```
<source-dir>/                      # 原文（不动）
<source-dir>-dual/                 # 双语版输出
  GLOSSARY.md                      # 术语库（单一真相源）
  epub/                            # 完整 EPUB 结构（从源复制）
    OEBPS/
      Styles/stylesheet.css        # 原样（无需改 CSS）
      Text/
        chapter-1.html             # 双语：原文+译文
        ...
      Images/                      # 原样复制
      content.opf
      toc.ncx                      # 导航：已译章节改双语文本
```
