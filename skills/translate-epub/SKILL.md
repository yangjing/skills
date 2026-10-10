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
  uv run scripts/inspect_epub.py --self-test                  # 内置自测
  ```
- **`scripts/validate_translation.py`** — 验证翻译后的 HTML：XHTML 标签栈配平、`<ul>` 子元素合法性、译文标签是否复用原文结构、残留旧标记检测、段落数配平。**配合三段式 `--glossary` 启用确定性术语强制**：保留英文词必须出现（error）、禁用词必须 0 出现（error）、术语译法抽查（warning）。**每章翻译后必跑。**
  ```bash
  uv run scripts/validate_translation.py <translated-html-path>
  uv run scripts/validate_translation.py <dir> --glossary _glossary.md
  uv run scripts/validate_translation.py --self-test
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
- **翻译范围**：全书 / 仅正文 / 先翻一章试效果（长书务必先试一章）。⚠️ 「仅正文」易踩坑：所谓「正文文件」之外的前置/后置页往往含有读者可见的正文内容，不可一律跳过——
  - **前置页**（Title_Pages / 版权页 / 献辞 / Contributors 作者简介 / 目录页 toc.xhtml）通常含大量正文，应一并翻译，除非用户明确说「版权页不翻」。
  - **索引页**（Index，按字母排列的术语索引）才是真正该跳过的。
  - 因此问用户时，把范围说成「正文 + 版权/献辞/作者简介/目录页，跳过索引」比笼统的「仅正文」更准确，避免漏译读者会看到的页面。

### 2. 探查源文件，建立全景
```bash
uv run scripts/inspect_epub.py "<ebook-path>"
```
读 JSON 结果，确认：源语言、章节清单（按阅读顺序）、TOC 路径、`html_root`（正文 HTML 所在目录）。据此规划翻译批次。

**留意 `hints` 与 `book_title`**：若 `book_title` 为 `null` 且 hint 提示「书名缺失/占位符（Untitled）」，说明源 EPUB 元数据有缺陷——阅读器书架会显示 Untitled。记下此事，在步骤 6 一并修正（不要等到打包后才发现书名是 Untitled）。

### 3. 建立术语库（全书翻译前必做，单一真相源）

先通读全书（或各章已有读书笔记/目录），提取术语，产出 `_glossary.md`。**用三段式结构**，`validate_translation.py --glossary` 据此做确定性检查：

```markdown
# 全书术语表（Glossary）
> 单一真相源。翻译前先建此库并冻结为只读快照分发各章；
> 遇新术语记入候选，全部译完后裁决合并回写。
> 三类（validate_translation.py 据此确定性检查）：翻译 / 保留英文 / 禁用

## 翻译术语（English → Chinese）
| 英文 | 中文译法 | 简释 | 首现 |
|---|---|---|---|
| agent | 智能体 | 感知-决策-行动达成目标的自主软件实体 | 第1章 |
| persona | 人设 | 智能体的角色与行为约束 | 第1章 |

## 保留英文（不翻译）
> 机器强制段，默认留空（见下方录入规则）；仅收录确认在所有含中文文件中必现的词。

（空）

## 禁用词（通常为空）
```

**录入规则**：
- **代码标识符 / API 名 / 框架名 / 协议名不翻译**，落库方式二选一：默认放「翻译术语」表**恒等行**（英文＝译法，如 `| MCP | MCP | 保留 |`），只在词出现的文件被抽查，不会跨章误报；**「保留英文」机器强制段默认留空**——keep 检查对每个含中文的文件（双语模式下目录页也含中文）做「词必须出现」的词边界检查，只有确认某词在**所有**待验证文件必现时才可入该段，否则必然在部分文件误报 error（实测 LLM/MCP/prompt/token/API/RAG/Claude/OpenAI/ReAct 九个候选词没有一个在全书所有文件出现）。
- **通用概念首次出现用「中文（英文）」并陈**，后续只用中文。
- **裁决跨章节不一致的译法**，全书采用唯一译法。
- **体例约定一并前置定死**（否则批次间漂移，事后要全书归一）：Listing 译「清单」、NOTE/Tip 译「注/提示」、图/表/章节引用格式（Figure 2.3→图 2.3、chapter 4→第 4 章）、标题译文不重复编号。
- **格式硬规则**：三段 `##` 标题（翻译术语 / 保留英文 / 禁用词）必须在场——验证器按 `##` 标题正则匹配切分；三段缺失时降级为「全文表格当翻译术语」，附录表（如裁决记录）的历史译法列会覆盖主表译法，产生误报警告并静默跳过强制检查（实录事故）。其他 `##` 段（裁决记录、维护约定）放在三段之后，且标题**不得含「翻译术语 / 保留英文 / 禁用」字样**，否则会被误匹配并覆盖对应解析结果。
- 维护约定：翻译新章节前先核对本表；遇新术语先记候选，全部译完裁决回写。

术语库写在输出目录根：`<output-dir>/_glossary.md`。

### 4. 复制源目录结构

把源 EPUB 原样复制到输出目录（保留图片、CSS、元数据、OEBPS 结构）：
```bash
cp -R "<source-epub-dir>" "<output-dir>"
```
输出目录名 = 源目录名 + 后缀（`-dual` / `-zh` 等），与源目录并列。

### 5. 逐章翻译（核心）

对每个正文 HTML 文件，**逐个块级元素翻译**。译文必须复用原文标签结构——这是本 skill 最关键
的规则，详见下方「## Translation rules」与 `references/bilingual-patterns.md`。

**术语注入采用「只注入本段命中词」而非整库**：把整本 GLOSSARY 塞进每章 prompt 会产生噪声、降低遵循率（网络实践 Lokalise）。正确做法是让翻译过程先读 GLOSSARY 的「翻译术语」段（含恒等行），再逐段翻译时只用相关词。**并发翻译时术语库冻结为只读快照**，新术语写本地候选，全部译完由主流程裁决合并回写（防竞态）。

**并发子代理翻译的红线（写进每个子代理 prompt 并逐条强调，全部有实录教训）**：
1. **绝对禁止编辑术语库**——术语库由主流程统一维护，子代理只能读，新术语写进返回报告（实录：有子代理擅自改库并谎报「经用户授权」——授权状态只有主流程知道）。
2. **绝对禁止为凑验证而插入原文没有的内容**（实录：为满足 keep 检查在译文里补写 RAG/ReAct/API 桩）。按步骤 3 的设计「保留英文」段为空/恒等行，不存在需要凑的检查；若仍出现 error，**先怀疑检查配置与术语库设计，再怀疑译文**，仍不确定就上报主流程，而不是改译文。
3. **绝对禁止改动原文英文**（含弯引号、软连字符 `&shy;`、原文笔误）或删除原文内容。

翻译顺序建议：章标题 → 正文段落 → 列表项 → 图注 → 表标题 → 表格。每章翻完立即用
`validate_translation.py` 验证，全绿后再进下一章。

### 6. 更新导航文件与元数据（打包前必做，否则阅读器显示异常）

三类文件都要处理，缺一会出现「书架标题 Untitled」「目录页英文」「章节导航英文」等问题：

**(a) 元数据 `content.opf`** —— 决定阅读器书架显示的书名/语言：
- `<dc:title>`：若源 EPUB 是占位符（Untitled / 空）或要改书名，改为目标语言书名（如 `OpenClaw：生产级 AI`）。注意可能有多个 `<dc:title>`，主书名由 `<meta refines="#id" property="title-type">main</meta>` 标识，全部改或至少改 main 那个。
- `<dc:language>`：改为目标语言代码（简中 `zh`、繁中 `zh-TW`、日语 `ja`），让阅读器正确断字排版。
- 书名译法若未指定，用 AskUserQuestion 让用户拍板（书名会进书架、扉页、导航，定下来一次写对）。

**(b) 导航 `toc.ncx`** —— 决定阅读器目录导航：
- `<docTitle><text>`：全书标题，与 `content.opf` 的 `<dc:title>` 保持一致（极易漏，只改章节导航不改 docTitle 是常见疏漏）。
- 各 `<navLabel><text>`：章节标题改为「英文 / 译文」（双语）或仅译文。

**(c) 目录页 `toc.xhtml` / `contents.html`** —— 读者翻到的目录页本身，含全部章节/小节链接文本：
- 翻译页面主标题（如 "Table of Contents" → "目录"）。
- 翻译每个目录项的链接文本（译文作为兄弟节点追加，复用原文结构，去 id），不要只改 toc.ncx 而漏了目录页本体——目录页是读者最先看到、内容最密集的页面之一。

**批量生成/修复导航条目的四个实证坑（一次全踩过）**：
1. 文件名正则字符类必须含数字：`[a-z0-9-]+`——写成 `[a-z-]+` 配不上 chapter-2，会**静默漏掉大半条目**（只配中 appendix-a 这类纯字母名）。
2. 锚点 `id` 通常在外层 `<div>` 上、标题在内层 `<h2-4>`：「锚点元素的下一个兄弟」≠「标题的译文」（会抓到下一个块的正文）。正确做法：把**目录条目文本**与目标文件中的英文标题做**精确匹配**，取其同标签的含中文兄弟作译名，锚点仅用于消歧。
3. 对生成结果做修复时，禁止用「删到最后一个 ` / `」类正则做部分替换——混入文本含 `/` 时正则失配会**变成追加**，产生「标题 / 正文段 / 译名」三段式脏条目。修复一律**整条重建**：按 ` / ` 渐进切分（从最长前缀试起，兼容标题本身含斜杠），对每个前缀重新推导译名后整串替换。
4. 保留英文标题的译文不含中文（如 Reflexion→Reflexion），基于「含中文＝译文」的启发式会失配——这类条目需特例处理为「标题 / 原词」。

### 7. 验证 + 可选打包

```bash
# 全书验证
uv run scripts/validate_translation.py "<output-dir>/OEBPS/Text/" --glossary _glossary.md
# 可选打包
uv run scripts/build_epub.py "<output-dir>" "<output-dir>.epub"
```

### 8. 全书审校（翻译完所有章节后必做一轮）

逐章验证只保证「结构与术语」，抓不住语义级误译（实测全书审校另抓出 4 处 P1 误译 + 1 处漏译 + 11 处目录缺陷）。全书翻完后做一轮审校：

**(a) 程序化扫描**（客观、零成本，先跑）：
- 裁决废弃译法 grep：把术语库中已裁决废弃的译法（如「人工介入」「评论家」「当法官」「智能体人格」）逐个 grep，出现即人工核对语境。
- 中文译文行中的英文弯引号 `“”`（译文应使用「」；原文行的弯引号是合法的）。
- 译文行中的 Figure/Table/Listing/Chapter 英文引用残留。
- 关键术语跨章漂移：对已定译法 grep 疑似变体；**命中后必须核对英文原文语境再判定**——泛指义是正确翻译（如 agentic workflow 泛指义译「智能体工作流」≠ agent flow=智能体流；semantic circuit breaker=语义断路器是独立词条，与 circuit breaker=熔断器无关）。

**(b) 并行只读审校代理**：每代理负责 1-2 章（外加一个代理专审导航文件与目录页条目一致性），对照 EN/ZH 报告问题（`文件:行号 | 级别(P1误译漏译添加/P2术语/P3流畅) | EN摘录 | ZH摘录 | 说明 | 建议改法`），**不修改文件**；主流程逐条核实后统一修复、复验。每文件限报条数、宁缺毋滥，防止代理用风格偏好刷存在感。

**(c) 实证有效的误译捕获模式**（审校代理的重点检查项）：最高级断言被弱化（most X → 「最 X 之一」）；施受关系/主语错置（被动句、分词短语逻辑主语在译文里换人）；「把」字句主客颠倒；习语字面直译（highest-leverage→「杠杆率最高」、flatline→「躺平」）；漏译嵌套列表项；同一术语同章异名。

**(d) 已知误报模式**（审校时不要报，主流程核验时不要改）：版权页/机构名恒等行（原文＝译文）；嵌套列表的成组译文（原文 li 含嵌套 ul，译文 li 复刻同构嵌套）；纯公式段与原文重复；保留英文标题（Reflexion→Reflexion）；全角冒号结尾的短标签译文（「Bash：」）；代码/纯标识符列表项不译。

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
- **全角引号**：EPUB 里 HTML 属性若出现中文全角引号 `“”`，必须修正为半角 `"`，否则属性解析失败。验证器的「发现 N 个全角引号」**warning** 指的是正文文本里的弯引号——Manning 等出版社源文件正文本来就用弯引号，该 warning 属源文件固有，忽略；真正危险的是属性内全角引号（表现为 HTML 解析失败，而非此 warning）。原文文本的弯引号一律保留，译文用「」。
- **表格不拆单元格内译**：不要把译文塞进原表格单元格（会破坏原文表格）。而是在原表格后加一个完整译文表格。
- **图注含 `<code>` 时**：译文 `<h5><span>` 内保留 `<code>` 英文原样。
- **不要自造 CSS class**（如 `zh-translation`）：译文靠复用原文 class 获得样式，无需额外 CSS。若加了自定义 class，说明违反了复用原则。
- **id 去重**：译文元素复用原文标签时去掉 `id` 属性，避免与原文元素 id 重复。
- **不全量注入术语库**：把整本 GLOSSARY 塞进每章 prompt 会产生噪声、降低遵循率（网络实践 Lokalise）。只注入本段命中的词——先读 GLOSSARY 再逐段翻译，而非把全表贴进 prompt。
- **确定性强制优于 prompt 提示**：纯靠 prompt「请用这些词」是概率性服从，LLM 不总遵守（Lokalise 称 GPT-4 级也无法确定性地遵守 glossary）。必须用 `validate_translation.py --glossary` 做译后确定性检查：保留英文词（如 MCP/ReAct）必须出现（error）、禁用词必须 0 出现（error）。error 不能靠「模型应该会遵守」糊弄过去。
- **滚动上下文不够，术语库兜底**：仅靠「记住上一段译文」会让长距离术语漂移（gpetho 翻译 400 页专著时，缩写停用 30 页后模型丢线误译成反义词）。GLOSSARY 是长距离一致性的唯一可靠基准。
- **并发回写防竞态**：多章并行翻译时，术语库冻结为只读快照供各进程注入，新术语写各自本地候选（不中途改主库），全部译完由主流程裁决合并回写——避免多进程同时改同一文件。
- **译文段落插到原文 koboSpan 切碎的段落中间**（高危，脚本批量插入时易发）：Kobo 等阅读器会把一个逻辑段落切成多个 `<span class="koboSpan" id="kobo.N.1">` + `<span class="sentence-end">`。译文 `<p>` 必须**紧跟原文整个段落的闭合 `</p>` 之后**，绝不能插到某个 koboSpan 开标签与闭标签之间。典型损坏：`<span class="koboSpan" id="kobo.38.1"` 之后紧跟译文 `<p>`，把原文 span 切成两半，validate 报「多余 </p>」。脚本批量插入时，定位点必须用「原文块级元素的闭合标签」而非「段落内某个 span 的位置」。
- **子 agent / 脚本翻译须独立验证，勿轻信「已完成」报告**：子 agent 曾反复出现「报告完成但目标文件 0 行中文」的空转（只改了 /tmp 副本），或把译文插到错误位置。每个翻译任务完成后，主流程必须：(1) 直接读真实文件统计含中文行数（`grep -cP '[\p{Han}]'` 等价物），(2) 跑 `validate_translation.py` 确认 0 error，(3) 抽查译文确实在原文下方。完成判据用「含中文行数 > 阈值 + 结构 0 错误」而非「agent 说做完了」。此外还有两种已实发的失真：**谎报授权**（声称「经用户授权」编辑术语库，实际从未授权——授权状态只有主流程知道）与**虚构凑检查**（为消掉 error 在译文里插入原文没有的术语桩）。对策是步骤 5 的红线三条款 + 主流程对代理的一切声明独立核验。
- **审校/复核时先跑结构完整性脚本再下结论**：id 序列比对（原版 vs 双语版逐一相等）、原版文本节点零缺失（每个原文文本节点能在双语版找到）、原文元素→译文相邻配对。注意已知误报模式（见步骤 8d），脚本命中后先人工看语境再定性，不要按脚本盲改。

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
  _glossary.md                      # 术语库（单一真相源）
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
