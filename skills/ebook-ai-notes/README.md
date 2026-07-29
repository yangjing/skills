# ebook-ai-notes

读取并精读电子书（epub / pdf），生成仿「微信读书 AI 大纲」风格的中文读书笔记。

## 简介

输入一本电子书（`.epub` 或 `.pdf`），产出一套结构化中文读书笔记：

- 一份 **README 总览**：这本书讲什么 / 核心贯穿概念 / 章节地图表 / 全书最值得带走的 N 个观点 / 阅读建议。
- **每章一份笔记**，统一为 5 段结构：一句话精要 · 分节精要（含图表 Table/Figure、关键代码片段）· 关键术语表（中英对照）· 金句观点。

笔记忠实于原文，信息密度高，便于快速检索与回顾——**不凭书名或记忆编造**，每条观点、术语、数据都能在原文找到出处。

## 适用场景

- "总结这本书"、"生成读书笔记 / AI 大纲"
- "精读这本 epub / pdf"、"提炼各章节要点"
- "写一份全书概览"

即使你没有显式提到「大纲」或「笔记」，只要想读透一本书，都可触发本 skill。

## 安装

```bash
# 安装到当前项目（默认 ./.agents/skills）
npx skills add <owner>/my-skills --skill ebook-ai-notes

# 全局安装到用户级目录
npx skills add <owner>/my-skills --skill ebook-ai-notes -g -y
```

## 依赖

- **[uv](https://docs.astral.sh/uv/)**：所有脚本通过 `uv run` 运行，依赖由脚本内联声明（PEP 723），uv 自动创建隔离环境安装，无需预装任何库。检查：`uv --version`。
- 笔记默认中文，专有名词与代码保留英文。

## 使用说明

本 skill 面向 AI Agent 自动执行，核心流程：

1. **探查源文件**（建立全景，必跑第 1 步）

   ```bash
   uv run skills/ebook-ai-notes/scripts/inspect_source.py "<ebook-path>"
   ```

   输出结构化 JSON（章节阅读顺序/页数、TOC 路径、图片数、扫描件检测），据此规划提取批次。支持 `.epub` / 已解压目录 / `.pdf`。

2. **读导航文件建立框架**：先读目录、前言、about-this-book 等导航内容，建立全书骨架。

3. **通读采样，建立全书统一术语库**（一致性基础，必做）：在分章提取**之前**采样各章术语密集区（本章覆盖 + 前 1-2 个小节），产出 `notes/<book-slug>/_glossary.md` 作为全书统一译法基准，避免同一术语在不同子代理间漂移（如 persona 译「人设/人格」、handoff 译「交接/移交」）。

4. **分章节提取**：逐章读正文并提取核心内容；章节数多（>3）时用并行子代理，每代理负责一章。子代理 prompt 注入术语库路径，要求统一采用术语库译法；遇未收录术语现场补录、回写 `_glossary.md`（增量补全）。

5. **生成逐章笔记**：在用户指定目录（默认 `notes/<book-slug>/`）下，每章一个 `.md` 文件，套用 5 段统一结构。本章术语须与 `_glossary.md` 一致。

6. **编写 README 总览**：组织全书骨架，首尾章呼应，并链接到 `_glossary.md` 作为全书术语表。

详细 prompt 模板、笔记结构、易错点见 [`SKILL.md`](SKILL.md)；一份完整笔记范文见 [`references/example-note.md`](references/example-note.md)。

## 关键特性

- **epub 本质是 zip**：脚本已处理解压与按 spine 阅读顺序排序（按文件名排序会错，如 `chapter-10` 排在 `chapter-2` 前）。
- **PDF 优先 PyMuPDF4LLM**：CJK 支持好，章节切分用 `get_toc()` + `to_markdown(pages=range(...))`。
- **文本层 PDF 必须传 `use_ocr=False`**：避免 Tesseract 对中文 OCR 既慢又不准；只有真扫描件（`needs_ocr: true`）才用 RapidOCR 兜底。
- **图表是高密度信息**：图说和表格常含核心对比/定义，必须提取。

## 目录结构

```
ebook-ai-notes/
├── SKILL.md                    # 执行协议与完整 workflow
├── scripts/
│   └── inspect_source.py       # 探查源文件，输出结构化 JSON 清单
├── references/
│   └── example-note.md         # 完整笔记范文（基于真实技术书第 1 章）
└── evals/
    └── evals.json
```
