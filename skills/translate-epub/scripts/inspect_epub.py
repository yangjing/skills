#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "beautifulsoup4>=4.12",
#     "lxml>=5.0",
# ]
# ///
"""
inspect_epub.py — 探查 EPUB 结构，为翻译规划输出结构化 JSON。

支持输入：
  1. .epub 文件            （解压到临时目录或 --workdir）
  2. 已解压的 epub 目录    （含 mimetype / META-INF / OEBPS）

输出（stdout）：JSON，含：
  book_title       — 从 <dc:title> 提取的主书名；缺省/占位（Untitled 等）为 None（hint 会提示修正）
  source_language  — 从 <dc:language> 推断的源语言（en/zh/ja/...）；None 表示需用户指定
  language_label   — 源语言的人类可读名称
  extracted_dir    — 解压后的根目录
  html_root        — 正文 HTML 所在目录（相对路径）
  opf_path / toc_path
  chapters[]       — 按 spine 阅读顺序的 HTML 清单 [{path, lines}]
  images_count
  tag_stats        — 各类块级元素标签数量统计（用于估算翻译工作量）
  hints[]          — 规划建议

诊断信息走 stderr。

用法：
  uv run inspect_epub.py <ebook-path> [--workdir DIR]
  uv run inspect_epub.py --help
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path


# 源语言推断表：常见 EPUB dc:language 值 → (代码, 可读名称)
_LANGUAGE_MAP = {
    "en": ("en", "英语"),
    "en-us": ("en", "美式英语"),
    "en-gb": ("en", "英式英语"),
    "zh": ("zh", "中文"),
    "zh-cn": ("zh", "简体中文"),
    "zh-tw": ("zh", "繁体中文"),
    "ja": ("ja", "日语"),
    "ko": ("ko", "韩语"),
    "fr": ("fr", "法语"),
    "de": ("de", "德语"),
    "es": ("es", "西班牙语"),
    "ru": ("ru", "俄语"),
}


def _err(msg: str) -> None:
    """诊断信息走 stderr，不污染 stdout 的 JSON。"""
    print(msg, file=sys.stderr)


def _is_epub_dir(p: Path) -> bool:
    return (p / "mimetype").exists() or (p / "META-INF").exists() or (p / "OEBPS").exists()


def _text_lines(html_path: Path) -> int:
    try:
        with html_path.open("r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


# --------------------------------------------------------------------------- #
# OPF / 语言检测
# --------------------------------------------------------------------------- #
def _detect_language(opf_path: Path | None, extracted: Path) -> tuple[str | None, str | None]:
    """从 content.opf 的 <dc:language> 推断源语言。返回 (code, label)。"""
    candidates = [opf_path] if opf_path else list(extracted.rglob("*.opf"))
    for opf in candidates:
        if not opf or not opf.exists():
            continue
        try:
            text = opf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = re.search(r"<dc:language[^>]*>\s*([a-zA-Z\-]+)\s*</dc:language>", text, re.IGNORECASE)
        if m:
            lang_raw = m.group(1).strip().lower()
            if lang_raw in _LANGUAGE_MAP:
                code, label = _LANGUAGE_MAP[lang_raw]
                return code, label
            return lang_raw, f"语言代码 {lang_raw}（需用户确认可读名称）"
    return None, None


# 书名缺省/占位值：命中其一说明 EPUB 元数据的书名未填写，打包前必须修正。
_PLACEHOLDER_TITLES = {"untitled", "unknown", "title", "no title", ""}


def _detect_title(opf_path: Path | None, extracted: Path) -> str | None:
    """从 content.opf 提取主书名（main title）。返回书名原文；缺省/占位时返回 None。

    EPUB 允许多个 <dc:title>，主书名由 <meta refines="#id" property="title-type">main</meta>
    标识；无此标识时取第一个。本函数优先取 title-type=main，否则取首个非空。
    任意候选命中占位符（Untitled/空等）一律视为书名缺失，返回 None——书名占位是
    常见 EPUB 缺陷，阅读器书架会显示 Untitled，必须提示修正。
    """
    candidates = [opf_path] if opf_path else list(extracted.rglob("*.opf"))
    for opf in candidates:
        if not opf or not opf.exists():
            continue
        try:
            text = opf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # 收集所有 <dc:title id="...">...</dc:title>，保留 id 与文本
        titles = re.findall(
            r'<dc:title(?:\s+id="([^"]*)")?[^>]*>\s*(.*?)\s*</dc:title>',
            text, re.IGNORECASE | re.DOTALL,
        )
        if not titles:
            continue
        # 找 title-type=main 的 refines 目标
        main_ids = set(re.findall(
            r'<opf:meta\s+property="title-type"\s+refines="#([^"]+)"\s*>main</opf:meta>',
            text, re.IGNORECASE,
        ))
        main_ids |= set(re.findall(
            r'<meta\s+property="title-type"\s+refines="#([^"]+)"\s*>main</meta>',
            text, re.IGNORECASE,
        ))
        # 优先 main 标记标题；占位符视为无效，回退到首个非占位标题
        chosen: str | None = None
        for tid, ttext in titles:
            if tid and tid in main_ids:
                chosen = ttext.strip()
                break
        if chosen and chosen.lower() in _PLACEHOLDER_TITLES:
            chosen = None
        if not chosen:
            for _tid, ttext in titles:
                cand = ttext.strip()
                if cand and cand.lower() not in _PLACEHOLDER_TITLES:
                    chosen = cand
                    break
        return chosen
    return None


def _parse_opf_spine(extracted: Path) -> tuple[list[Path], Path | None]:
    """解析 EPUB content.opf，按 spine 顺序返回正文 HTML 路径列表。"""
    from bs4 import BeautifulSoup

    opf_files = list(extracted.rglob("*.opf"))
    if not opf_files:
        htmls = sorted(
            list(extracted.rglob("*.html")) + list(extracted.rglob("*.xhtml"))
            + list(extracted.rglob("*.htm"))
        )
        return htmls, None

    opf_path = opf_files[0]
    opf_dir = opf_path.parent
    try:
        soup = BeautifulSoup(opf_path.read_text(encoding="utf-8", errors="replace"), "xml")
    except Exception:  # noqa: BLE001
        return sorted(extracted.rglob("*.html")), opf_path

    manifest: dict[str, str] = {}
    for item in soup.find_all("item"):
        iid = item.get("id")
        href = item.get("href")
        if iid and href:
            manifest[iid] = href

    ordered: list[Path] = []
    for itemref in soup.find_all("itemref"):
        idref = itemref.get("idref")
        if not idref or idref not in manifest:
            continue
        candidate = (opf_dir / manifest[idref]).resolve()
        if candidate.exists() and candidate.suffix.lower() in {".html", ".xhtml", ".htm"}:
            ordered.append(candidate)

    if not ordered:
        ordered = sorted(extracted.rglob("*.html"))
    return ordered, opf_path


def _find_epub_toc(extracted: Path) -> str | None:
    for name in ("toc.ncx", "nav.xhtml", "contents.html", "contents.xhtml",
                 "toc.html", "nav.html"):
        hits = list(extracted.rglob(name))
        if hits:
            return str(hits[0].relative_to(extracted))
    return None


def _guess_html_root(extracted: Path) -> str | None:
    for sub in ("OEBPS/Text", "OEBPS", "EPUB", "text", "Text", "content", "html"):
        d = extracted / sub
        if d.is_dir() and (list(d.glob("*.html")) or list(d.glob("*.xhtml"))):
            return str(d.relative_to(extracted))
    return None


def _tag_stats(html_files: list[Path]) -> dict[str, int]:
    """统计所有正文 HTML 中各类块级标签的数量（估算翻译工作量）。"""
    counter: Counter[str] = Counter()
    tag_re = re.compile(r"<(h[1-6]|p|li|td|th|table|img|code)\b")
    for hp in html_files:
        try:
            text = hp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in tag_re.finditer(text):
            counter[m.group(1)] += 1
    return dict(counter)


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def inspect_epub(path: Path, workdir: Path | None) -> dict:
    # 1. 解压（若需要）
    if path.is_file() and path.suffix.lower() == ".epub":
        extract_root = workdir or Path(tempfile.mkdtemp(prefix="epub_translate_"))
        extracted = extract_root / path.stem
        if extracted.exists():
            shutil.rmtree(extracted)
        try:
            with zipfile.ZipFile(path) as zf:
                zf.extractall(extracted)
        except zipfile.BadZipFile as e:
            print(f"Error: '{path}' 不是有效的 epub/zip 文件：{e}", file=sys.stderr)
            sys.exit(2)
        extracted = extracted.resolve()
        _err(f"[epub] 已解压到 {extracted}")
    elif path.is_dir() and _is_epub_dir(path):
        extracted = path.resolve()
    else:
        print(f"Error: 无法识别的 epub 输入：{path}", file=sys.stderr)
        sys.exit(2)

    # 2. spine 顺序 + TOC
    chapters, opf_path = _parse_opf_spine(extracted)
    toc_path = _find_epub_toc(extracted)

    # 3. 源语言 + 书名
    lang_code, lang_label = _detect_language(opf_path, extracted)
    book_title = _detect_title(opf_path, extracted)

    # 4. 图片
    images = []
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.svg"):
        images.extend(extracted.rglob(ext))

    # 5. 标签统计
    stats = _tag_stats(chapters)

    chapter_list = [
        {"path": str(c.relative_to(extracted)), "lines": _text_lines(c)}
        for c in chapters
    ]

    hints = []
    if not chapter_list:
        hints.append("未找到章节 HTML，请检查 epub 结构。")
    if len(chapter_list) > 30:
        hints.append(f"章节数较多（{len(chapter_list)}），建议先翻一章试效果再并行翻译其余。")
    if not lang_code:
        hints.append("未从元数据检测到源语言，需用 AskUserQuestion 让用户指定。")
    if not toc_path:
        hints.append("未自动定位到目录文件，可能需人工识别章节结构。")
    # 书名元数据缺陷：书名缺失/为占位符（如 Untitled）时，阅读器书架会显示 Untitled，
    # 打包前必须修正 content.opf 的 <dc:title> 与 toc.ncx 的 <docTitle>（见 SKILL 步骤 6）。
    if not book_title:
        hints.append(
            "⚠️ 元数据书名缺失或为占位符（Untitled 等）。Apple Books 等阅读器书架会显示 "
            "Untitled。打包前务必修正 content.opf 的 <dc:title> 与 toc.ncx 的 <docTitle>。"
        )

    return {
        "file_type": "epub",
        "source": str(path),
        "book_title": book_title,
        "source_language": lang_code,
        "language_label": lang_label,
        "extracted_dir": str(extracted),
        "opf_path": str(opf_path.relative_to(extracted)) if opf_path else None,
        "toc_path": toc_path,
        "html_root": _guess_html_root(extracted),
        "chapters": chapter_list,
        "images_count": len(images),
        "total_lines": sum(c["lines"] for c in chapter_list),
        "tag_stats": stats,
        "hints": hints,
    }


# --------------------------------------------------------------------------- #
# 自测（--self-test）
# --------------------------------------------------------------------------- #
def _self_test() -> None:
    """内置自测：断言核心逻辑函数行为正确，可选集成测真实 epub。"""
    import tempfile
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # 1. _is_epub_dir
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        check(_is_epub_dir(d) is False, "_is_epub_dir: 空目录应判 False")
        (d / "OEBPS").mkdir()
        check(_is_epub_dir(d) is True, "_is_epub_dir: 含 OEBPS 应判 True")

    # 2. _guess_html_root
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        check(_guess_html_root(d) is None, "_guess_html_root: 无 html 应返回 None")
        (d / "OEBPS" / "Text").mkdir(parents=True)
        (d / "OEBPS" / "Text" / "chapter-1.html").write_text("<html></html>")
        check(_guess_html_root(d) == "OEBPS/Text", "_guess_html_root: 应返回 OEBPS/Text")

    # 3. _detect_language：从 opf 的 dc:language 推断
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "content.opf").write_text(
            '<package xmlns="http://www.idpf.org/2007/opf">'
            '<dc:language>en-us</dc:language></package>'
        )
        code, label = _detect_language(Path(d / "content.opf"), d)
        check(code == "en", f"_detect_language: en-us 应推断 code=en，实际 {code}")
        check("英语" in (label or ""), f"_detect_language: label 应含'英语'，实际 {label}")

    # 4. _tag_stats：统计块级标签
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "a.html"
        f.write_text("<h1>t</h1><p>x</p><p>y</p><li>z</li><code>c</code>")
        stats = _tag_stats([f])
        check(stats.get("h1") == 1, f"_tag_stats: h1 应为 1，实际 {stats.get('h1')}")
        check(stats.get("p") == 2, f"_tag_stats: p 应为 2，实际 {stats.get('p')}")
        check(stats.get("code") == 1, f"_tag_stats: code 应为 1，实际 {stats.get('code')}")

    # 5. _parse_opf_spine：按 spine 顺序非文件名排序
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "OEBPS").mkdir()
        (d / "OEBPS" / "chapter-2.html").write_text("<html></html>")
        (d / "OEBPS" / "chapter-10.html").write_text("<html></html>")
        (d / "OEBPS" / "content.opf").write_text(
            '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf">'
            '<manifest><item id="c10" href="chapter-10.html"/>'
            '<item id="c2" href="chapter-2.html"/></manifest>'
            '<spine><itemref idref="c10"/><itemref idref="c2"/></spine>'
            '</package>'
        )
        chapters, opf_path = _parse_opf_spine(d.resolve())
        names = [c.name for c in chapters]
        check(names == ["chapter-10.html", "chapter-2.html"],
              f"_parse_opf_spine: 应按 spine 顺序 [chapter-10, chapter-2]，实际 {names}")

    # 6. 可选集成测：仓库内真实 epub
    repo_epub = Path(__file__).resolve().parents[4] / "ebooks" \
        / "ai-agents-action-intelligent-workflows-2nd" / "epub"
    if repo_epub.exists():
        try:
            result = inspect_epub(repo_epub, None)
            check(result.get("file_type") == "epub", "集成测: file_type 应为 epub")
            check(result.get("source_language") is not None,
                  "集成测: 应检测到 source_language")
            check("html_root" in result, "集成测: 应含 html_root 字段")
            check("tag_stats" in result and len(result["tag_stats"]) > 0,
                  "集成测: tag_stats 应非空")
        except SystemExit as e:
            failures.append(f"集成测: inspect_epub 异常退出码 {e.code}")

    if failures:
        _err("❌ 自测失败：")
        for f in failures:
            _err(f"  - {f}")
        sys.exit(1)
    _err(f"✓ 自测通过（{len(failures)} 失败）"
         + (f"；集成测 epub={repo_epub.name}" if repo_epub.exists() else "；跳过集成测（无真实 epub）"))


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="inspect_epub.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="探查 EPUB 结构，为翻译规划输出结构化 JSON（源语言/章节清单/标签统计）。",
        epilog="""\
示例:
  uv run inspect_epub.py book.epub
  uv run inspect_epub.py ./epub-dir        # 已解压的 epub 目录
  uv run inspect_epub.py book.epub --workdir /tmp/extract

输出（stdout JSON）字段:
  source_language, language_label, extracted_dir, opf_path, toc_path,
  html_root, chapters[{path,lines}], images_count, total_lines,
  tag_stats{h1-h6,p,li,td,th,table,img,code}, hints[]
""",
    )
    p.add_argument("path", nargs="?", help="EPUB 路径：.epub 文件或已解压的 epub 目录")
    p.add_argument(
        "--workdir",
        default=None,
        help="epub 解压目标目录（默认临时目录）。仅对 .epub 文件有效。",
    )
    p.add_argument(
        "--self-test",
        action="store_true",
        help="运行内置自测（纯逻辑函数 + 可选真实 epub 集成测），无需 path 参数。",
    )
    return p


def main() -> None:
    args = build_arg_parser().parse_args()

    if args.self_test:
        _self_test()
        return

    if not args.path:
        print("Error: 缺少 path 参数（或使用 --self-test 运行自测）", file=sys.stderr)
        sys.exit(2)

    path = Path(args.path).expanduser().resolve()
    if not path.exists():
        print(f"Error: 路径不存在：{path}", file=sys.stderr)
        sys.exit(2)

    if path.is_file():
        if path.suffix.lower() != ".epub":
            print(f"Error: 不支持的文件类型：{path.suffix}（仅支持 .epub）", file=sys.stderr)
            sys.exit(2)
        result = inspect_epub(path, Path(args.workdir).resolve() if args.workdir else None)
    elif path.is_dir():
        if not _is_epub_dir(path):
            print(f"Error: 目录不像 epub 结构（未找到 mimetype/META-INF/OEBPS）：{path}", file=sys.stderr)
            sys.exit(2)
        result = inspect_epub(path, None)
    else:
        print(f"Error: 既不是文件也不是目录：{path}", file=sys.stderr)
        sys.exit(2)

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
