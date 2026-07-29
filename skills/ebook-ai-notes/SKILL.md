---
name: ebook-ai-notes
description: >
  读取并精读电子书（epub / pdf），生成仿「微信读书 AI 大纲」风格的中文读书笔记。
  Use this skill when the user wants to read, summarize, or take notes on an ebook —
  e.g. "总结这本书"、"生成读书笔记/AI 大纲"、"精读这本 epub/pdf"、"提炼各章节要点"、
  "写一份全书概览"，even if they don't explicitly mention "大纲" or "笔记".
  Produces a README overview plus one structured note per chapter (速览/分节精要/术语表/金句).
---

<objective>
读取一本电子书（epub 或 pdf），生成一套「微信读书 AI 大纲」风格的中文读书笔记：
一个 README 总览 + 每章一份结构化笔记，忠实于原文、信息密度高、便于快速检索与回顾。
</objective>

## Prerequisites

- **uv**：所有脚本通过 `uv run` 运行，依赖由脚本内联声明（PEP 723），uv 会自动创建隔离环境安装。无需预装任何库。
  - 检查：`uv --version`
- 输出笔记默认中文（与本工作区 AGENTS.md 一致），专有名词与代码保留英文。

## Available scripts

- **`scripts/inspect_source.py`** — 探查源文件，输出结构化 JSON 清单（章节阅读顺序/页数、TOC 路径、图片数、扫描件检测）。
  ```bash
  uv run scripts/inspect_source.py <ebook-path>          # .epub / 已解压目录 / .pdf
  uv run scripts/inspect_source.py book.epub --workdir /tmp/extract
  ```
  数据走 stdout（JSON），诊断走 stderr。**第 1 步必跑。**

## Workflow

### 1. 探查源文件（建立全景）
```bash
uv run scripts/inspect_source.py "<ebook-path>"
```
读 JSON 结果，拿到 `chapters`（epub 按 spine 阅读顺序的 HTML 清单+行数 / pdf 按 TOC 的章节+起始页）、`toc_path`、`needs_ocr` 等。**据此规划提取批次**：行数/页数大的章节单列，小的可合并。

### 2. 读导航文件建立框架
先读导航类内容，建立全书骨架（不要直接扎进正文章节）：
- **epub**：读 `toc_path`（目录）、前言 `preface.html`、`about-this-book.html`（通常含「本书讲了什么 / 读者对象 / 各章速览 / 路线图」）。
- **pdf**：从脚本输出的 `chapters`（书签 TOC）建骨架；若无 TOC，先提取前言/目录页文本人工识别章节边界。

### 3. 通读采样，建立全书统一术语库（一致性基础，必做）
在分章提取**之前**，先建一份贯穿全书的术语库，作为后续所有提取与笔记的统一基准——否则同一术语被不同子代理翻译会漂移（如 persona 译「人设/人格」、handoff 译「交接/移交」、guardrail 中英混用）。

**采样速建（不做全章并行预扫，省 5-10 倍 token）**：
- 读每章的「**本章覆盖 + 前 1-2 个小节**」（术语密集区，无需整章），外加第 2 步已读的目录/前言/about-this-book。
- 拟出初版术语库，落盘为 `notes/<book-slug>/_glossary.md`（下划线前缀排序靠前）。

**`_glossary.md` 结构**：
```markdown
# 全书术语表（Glossary）
> 全书统一译法基准。各章笔记须与此一致；生成时如遇未收录术语，补录后回写本文件。

| 英文 | 统一中文译法 | 简释 | 首现章节 |
|---|---|---|---|
| agent | 智能体 | 感知-决策-行动达成目标的自主软件实体 | 第1章 |
| MCP (Model Context Protocol) | 模型上下文协议 | Anthropic 的工具连接开放标准 | 第1章 |
| persona | 人设 | 智能体的角色与行为约束（system prompt） | 第1章 |
```

**裁定原则**：
- 高频/核心/有歧义的术语**必须统一中文译法**（一书内只取一个译法，如 agent→智能体，不混用「代理」）。
- **行业通用专名保留英文不译**：API、token、RAG、Docker、JSON、HTTP、SDK、CoT、ReAct 等。
- 首字母缩写（MCP、LLM、HITL）首次出现给中文全称 + 缩写，后续用缩写。
- 每条标「首现章节」，便于读者回溯。

### 4. 分章节并行提取（关键提效点）
**逐章读正文并提取核心内容**。章节数多（>3）时，用并行子代理（Agent 工具）——一个子代理负责一章，在同一条消息里发起多个。

每个子代理的提取 prompt 须包含：
- 章节文件绝对路径（epub）/ 页码范围（pdf）
- **`_glossary.md` 的路径，并要求「统一使用术语库的译法；遇到术语库未收录的新术语，须现场补录并在返回结果中单独列出，由主流程回写 `_glossary.md`」（增量补全）**
- 要求「**完整读取该文件全文**，再按结构化格式提取」，**不要凭书名或记忆编造**
- 输出结构：章节标题+一句话主旨 / 本章覆盖 / 分节精要（含图表 Table·Figure 描述、关键代码片段）/ 本章术语（中英对照，须与 `_glossary.md` 一致）/ 金句观点（3-5 条）
- 全部用中文，**术语一律采用 `_glossary.md` 的统一译法**，专有名词与代码保留英文

### 5. 生成微信读书风格大纲（逐章笔记）
在用户指定目录（默认 `notes/<book-slug>/`）下，**每章一个 `.md` 文件**。每篇笔记用下面的统一结构（模板见下文）。术语须与 `_glossary.md` 一致。

### 6. 编写 README 总览
`notes/<book-slug>/README.md` 包含：这本书讲什么 / 核心贯穿概念 / 章节地图表 / 全书最值得带走的 N 个观点 / 技术栈速览 / 阅读建议 / **链接到 `_glossary.md` 作为全书术语表**。首尾章呼应（第 1 章导论 + 末章收官）是组织全书的好抓手。

## 笔记结构模板（微信读书 AI 大纲风格）

每章笔记统一为这 5 段，用 emoji 小标题增强可扫读性：

```markdown
# 第 N 章 · 章节标题（中英）

> <用引用块写一句话主旨：本章解决什么核心问题>

**本章覆盖**：<列点>

---

## 🔑 一句话精要
<全章最浓缩的一句话>

## 📑 分节精要
### N.1 小节标题（中英）
- <核心论点/概念/定义，要点形式，忠实原文>
- <重要的 Table N.x / Figure N.x：说明图表传达的核心信息>
- <关键代码片段：保留并注明 Listing 目的>
（每个小节都如此展开）

## 📚 本章术语
> 全书术语统一收录在 [`_glossary.md`](./_glossary.md)；此处只列本章核心术语，译法须与之一致。

| 英文 | 统一中文译法 |
|---|---|
| term | 译名 |

## 💎 金句 / 重要观点
1. **<加粗观点>**——<简短解释>
```

## Gotchas

- **epub 本质是 zip**：`.epub` 文件需解压才能读到 `OEBPS/Text/*.html`。脚本已处理；若手动操作用 `unzip`。HTML 容器结构与标签命名因出版社而异（Manning 用 `OEBPS/Text/chapter-N.html` + `<div class="readable-text" id="pNN">` 段落），**不要假设固定路径/标签，先看 inspect 输出再定**。
- **章节阅读顺序看 spine，不是文件名排序**：spine 定义在 `content.opf`，脚本已按 spine 排序。按文件名 `chapter-1,2,...,10,11` 排序会错（10 排在 2 前面）。
- **导航页与正文章节混在一起**：`title/copyright/contents/preface/about-*` 是导航页，正文是 `chapter-*`；笔记只覆盖正文章节，但前言/about-this-book 要先读以建框架。
- **图表（Figure/Table）是高密度信息，必须提取**：图说（`<h5 class="figure-container-h5">`）和表格（`<table>`）常含核心对比/定义，别只抓正文段落。代码示例（Listing）保留关键片段。
- **PDF 优先 PyMuPDF4LLM，CJK 支持好**：`pymupdf4llm` 输出 Markdown、重建阅读顺序、检测表格；章节切分用底层 `pymupdf.Document.get_toc()`（返回 `[[level, title, page], ...]`），配合 `to_markdown(pages=range(...))` 按章提取。实测中文 PDF（如《OSWorkflow 中文手册》）提取无乱码、中英混排正常。
- **⚠️ PDF 提取务必传 `use_ocr=False`（文本层 PDF）**：`pymupdf4llm.to_markdown()` 默认 `use_ocr=True`，会自动用 **Tesseract** 做 OCR 回退——既慢，又对中文不准（还会引入噪声）。inspect 判为 `needs_ocr=false`（有文本层）的书，一律用 `to_markdown(..., use_ocr=False)`，文本层提取质量已足够好。**只有 `needs_ocr=true`（真扫描件）才需 OCR**，且用 RapidOCR（ONNX 版 PaddleOCR，中文准确率接近 PaddleOCR 但更轻更快）而非 Tesseract。提取代码示例：
  ```python
  import pymupdf4llm
  md = pymupdf4llm.to_markdown("book.pdf", pages=list(range(start-1, end)), use_ocr=False, show_progress=False)
  ```
- **扫描件（pdf `needs_ocr: true`）用 RapidOCR 兜底，别用 Tesseract**：Tesseract 中文准确率差。RapidOCR 依赖较重，仅在确认无文本层时才做；做法是把页面渲染成图片再过 RapidOCR。
- **忠实原文，勿凭记忆/书名编造**：每条观点、术语、数据都要能在原文找到出处。先读代码/原文再下结论（与工作区 AGENTS.md 一致）。
- **章节数多时务必并行**：12 章串行读会很慢；用并行子代理（每代理一章），一条消息发多个 Agent 调用，能数倍提速。
- **术语一致性是全书级问题，不是单章问题**：同一术语在不同章被不同子代理提取，极易译法漂移（如 persona→人设/人格、handoff→交接/移交、guardrail 中英混用）。**必须先建 `_glossary.md` 再分发提取**，并在每个子代理 prompt 中注入术语库路径 + 「遇到新术语补录回写」要求。各章笔记的「本章术语」只是全书术语表的子集，译法必须与之一致。
- **macOS 路径符号链接陷阱**：macOS 上 `/var`、`/tmp` 是 `/private/var`、`/private/tmp` 的符号链接。`zipfile.extractall` 解压后得到的真实路径带 `/private` 前缀，而 `tempfile` 返回的不带，两者混用会让 `Path.relative_to()` 抛 ValueError。脚本已用 `.resolve()` 统一规避；手写处理 epub 的代码时务必对所有路径 resolve。

## Progressive disclosure

- 需要一份完整的笔记范文做 pattern-match 时，读取 **`references/example-note.md`**（基于一本真实技术书第 1 章精简而成，展示完整的 5 段结构与图表/代码/术语处理）。
