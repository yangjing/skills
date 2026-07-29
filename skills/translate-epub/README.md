# translate-epub

翻译 EPUB 电子书：先通读全书建立统一术语库，再逐章翻译，默认产出双语版本（译文显示在原文下方），也可仅保留译文，并可选打包成 `.epub`。

## 简介

输入一本 EPUB 电子书，产出与源结构镜像的输出目录（如 `book-dual/` / `book-zh/`），其中正文 HTML 已翻译，图片 / CSS / 元数据原样保留。译文复用原文的 HTML 标签结构与 CSS class，作为独立的兄弟元素紧跟原文之后，保证显示效果与原文一致。

核心特点：

- **默认双语**：译文显示在原文下方（目录后缀 `-dual`）。需「仅译文」时改为单语（后缀按语言：简中 `-zh`、繁中 `-zh-tw`、日语 `-ja`）。
- **术语统一**：全书先建 `GLOSSARY.md` 术语库（单一真相源），再分发翻译，避免同一术语在各章漂移。
- **结构忠实**：译文只换内容、不动标签与 class，渲染效果与原书一致。

## 适用场景

- "翻译这本 epub"、"把这本书译成中文"、"生成双语版电子书"、"翻译电子书"

即使你没有显式提到「epub」或「translate」，只要想翻译电子书，都可触发本 skill。

## 安装

```bash
# 安装到当前项目（默认 ./.agents/skills）
npx skills add <owner>/skills --skill translate-epub

# 全局安装到用户级目录
npx skills add <owner>/skills --skill translate-epub -g -y
```

## 依赖

- **[uv](https://docs.astral.sh/uv/)**：所有脚本通过 `uv run` 运行，依赖由脚本内联声明（PEP 723），uv 自动创建隔离环境安装，无需预装任何库。检查：`uv --version`。
- **译文语言必须由用户指定**；原文语言通常能从 EPUB 元数据自动判断，判断失败则询问用户。

## 使用说明

本 skill 面向 AI Agent 自动执行，核心流程：

1. **确认语言与输出模式**（必做）：译文语言、显示方式（默认双语）、是否打包 epub、翻译范围（长书先试一章）。
2. **探查源文件**：

   ```bash
   uv run skills/translate-epub/scripts/inspect_epub.py "<ebook-path>"
   ```

   输出结构化 JSON：源语言、章节清单（按 spine 阅读顺序 + 行数）、TOC 路径、图片数、文本元素标签统计。

3. **建立术语库**（全书翻译前必做）：通读全书提取术语，产出 `<output-dir>/GLOSSARY.md`（按主题域分组；代码标识符 / API / 框架 / 协议名保留英文；跨章节不一致的译法全书统一）。
4. **复制源目录结构**：`cp -R` 源 EPUB 到输出目录（后缀区分），保留图片 / CSS / 元数据 / OEBPS 结构。
5. **逐章翻译**：对每个正文 HTML 逐个块级元素翻译，译文复用原文标签与 class。每章翻完立即验证，全绿再进下一章。
6. **更新导航文件**：`toc.ncx`、`contents.html` 的已译章节改为双语或译文文本。
7. **验证 + 可选打包**：

   ```bash
   # 全书验证
   uv run skills/translate-epub/scripts/validate_translation.py "<output-dir>/OEBPS/Text/" --glossary GLOSSARY.md
   # 可选打包成 .epub
   uv run skills/translate-epub/scripts/build_epub.py "<output-dir>" "<output-dir>.epub"
   ```

各元素类型（标题 / 段落 / 图注 / 表格 / 列表 / 代码）的翻译正确模式与易踩的坑，详见 [`SKILL.md`](SKILL.md) 与 [`references/bilingual-patterns.md`](references/bilingual-patterns.md)。

## 关键特性

- **译文复用原文标签结构与 CSS class**：仅内容换语言，作为独立兄弟元素紧跟原文——不在原文内部、不内联、不换标签、不自造 class。
- **`<ul>` 只能含 `<li>`**：列表项译文必须是 `<li>`，放回同一 `<ul>` 内紧跟原文，否则 XHTML 非法、EPUB 阅读器渲染异常。
- **表格不拆单元格**：原表格不动，在其下方追加一个完整译文表格（相同结构 / colgroup / thead / tbody / class）。
- **验证门（每章必过）**：`validate_translation.py` 检查 XHTML 标签栈配平、`<ul>` 子元素合法性、无残留自定义标记、译文与原文标签一致、术语一致性抽查——全绿才算完成。

## 目录结构

```
translate-epub/
├── SKILL.md                          # 执行协议、翻译规则与完整 workflow
├── scripts/
│   ├── inspect_epub.py               # 探查 EPUB 结构，输出结构化 JSON
│   ├── validate_translation.py       # 验证译文 HTML（标签配平 / 列表合法 / 术语一致）
│   └── build_epub.py                 # 把翻译后的目录打包成 .epub
├── references/
│   └── bilingual-patterns.md         # 各元素类型的双语翻译 HTML 模式详解
└── evals/
    └── evals.json
```
