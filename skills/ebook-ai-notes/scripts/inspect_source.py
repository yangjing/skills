#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "beautifulsoup4>=4.12",
#     "lxml>=5.0",
#     "pymupdf4llm>=0.0.17",
# ]
# ///
"""
inspect_source.py — 探查电子书源文件，输出结构化 JSON 清单。

支持三种输入：
  1. .epub 文件            （会解压到临时目录）
  2. 已解压的 epub 目录    （含 mimetype 或 OEBPS/）
  3. .pdf 文件             （用 PyMuPDF4LLM；扫描件提示用 RapidOCR）

输出（stdout）：JSON，含 file_type / extracted_dir / toc_path / chapters /
images_count / total_lines_or_pages / hints 等字段。诊断信息走 stderr。

用法：
  uv run inspect_source.py <ebook-path> [--workdir DIR]
  uv run inspect_source.py --help
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


# --------------------------------------------------------------------------- #
# 工具函数
# --------------------------------------------------------------------------- #
def _err(msg: str) -> None:
    """诊断信息走 stderr，不污染 stdout 的 JSON。"""
    print(msg, file=sys.stderr)


def _text_lines(html_path: Path) -> int:
    """统计 HTML 文件行数（用于评估提取工作量）。"""
    try:
        with html_path.open("r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


# --------------------------------------------------------------------------- #
# EPUB 处理
# --------------------------------------------------------------------------- #
def _is_epub_dir(p: Path) -> bool:
    return (p / "mimetype").exists() or (p / "META-INF").exists() or (p / "OEBPS").exists()


def _parse_opf_spine(extracted: Path) -> tuple[list[Path], Path | None]:
    """
    解析 EPUB 的 content.opf，按 spine（阅读顺序）返回正文 HTML 路径列表。
    返回 (chapters, opf_path)。失败时回退为按文件名排序的 html 文件。
    需要 BeautifulSoup + lxml。
    """
    from bs4 import BeautifulSoup  # 延迟导入，epub 才需要

    # 定位 .opf 文件（通常在 OEBPS/content.opf，但不保证）
    opf_files = list(extracted.rglob("*.opf"))
    if not opf_files:
        # 回退：收集所有 .html/.xhtml，按路径排序
        htmls = sorted(
            list(extracted.rglob("*.html")) + list(extracted.rglob("*.xhtml"))
            + list(extracted.rglob("*.htm"))
        )
        # 过滤掉明显的导航/版权页，但仍保留 contents/toc 以便 agent 判断
        return htmls, None

    opf_path = opf_files[0]
    opf_dir = opf_path.parent
    try:
        soup = BeautifulSoup(opf_path.read_text(encoding="utf-8", errors="replace"), "xml")
    except Exception:  # noqa: BLE001 — 解析失败回退
        htmls = sorted(extracted.rglob("*.html"))
        return htmls, opf_path

    # manifest: id -> href
    manifest: dict[str, str] = {}
    for item in soup.find_all("item"):
        iid = item.get("id")
        href = item.get("href")
        if iid and href:
            manifest[iid] = href

    # spine: 按 idref 顺序
    ordered: list[Path] = []
    for itemref in soup.find_all("itemref"):
        idref = itemref.get("idref")
        if not idref or idref not in manifest:
            continue
        href = manifest[idref]
        # href 相对于 opf_dir；解析为绝对路径（可能是 url-encoded）
        candidate = (opf_dir / href).resolve()
        if candidate.exists() and candidate.suffix.lower() in {".html", ".xhtml", ".htm"}:
            ordered.append(candidate)

    if not ordered:  # spine 解析失败回退
        ordered = sorted(extracted.rglob("*.html"))
    return ordered, opf_path


def _find_epub_toc(extracted: Path) -> str | None:
    """定位目录文件：优先 toc.ncx，其次 contents/nav 等 html。"""
    for name in ("toc.ncx", "nav.xhtml", "contents.html", "contents.xhtml",
                 "toc.html", "nav.html"):
        hits = list(extracted.rglob(name))
        if hits:
            return str(hits[0].relative_to(extracted))
    return None


def inspect_epub(path: Path, workdir: Path | None) -> dict:
    """处理 .epub 文件或已解压目录。"""
    # 1. 解压（若需要）
    if path.is_file() and path.suffix.lower() == ".epub":
        extract_root = (workdir or Path(tempfile.mkdtemp(prefix="ebook_inspect_")))
        extracted = (extract_root / path.stem)
        if extracted.exists():
            shutil.rmtree(extracted)  # 幂等：清掉旧解压结果
        try:
            with zipfile.ZipFile(path) as zf:
                zf.extractall(extracted)
        except zipfile.BadZipFile as e:
            print(f"Error: '{path}' 不是有效的 epub/zip 文件：{e}", file=sys.stderr)
            sys.exit(2)
        # resolve() 统一为真实路径（macOS 上 /var 是 /private/var 的符号链接，
        # 与 _parse_opf_spine 内部 candidate.resolve() 的基准对齐，否则 relative_to 会失败）
        extracted = extracted.resolve()
        _err(f"[epub] 已解压到 {extracted}")
    elif path.is_dir() and _is_epub_dir(path):
        extracted = path.resolve()
    else:
        print(f"Error: 无法识别的 epub 输入：{path}", file=sys.stderr)
        sys.exit(2)

    # 2. 解析 spine 顺序 + TOC
    chapters, opf_path = _parse_opf_spine(extracted)
    toc_path = _find_epub_toc(extracted)

    # 3. 统计图片
    images = list(extracted.rglob("*.png")) + list(extracted.rglob("*.jpg")) \
        + list(extracted.rglob("*.jpeg")) + list(extracted.rglob("*.gif")) \
        + list(extracted.rglob("*.svg"))

    # 4. 组装 chapters 清单（过滤掉纯图片/封面页之外的无文本页由 agent 判断）
    chapter_list = [
        {
            "path": str(c.relative_to(extracted)),
            "lines": _text_lines(c),
        }
        for c in chapters
    ]

    hints = []
    if not chapter_list:
        hints.append("未找到章节 HTML，请检查 epub 结构或手动指定。")
    if len(chapter_list) > 40:
        hints.append(f"章节数较多（{len(chapter_list)}），建议分批并行提取。")
    if not toc_path:
        hints.append("未自动定位到目录文件，可能需从正文首页人工识别章节结构。")

    return {
        "file_type": "epub",
        "source": str(path),
        "extracted_dir": str(extracted),
        "opf_path": str(opf_path.relative_to(extracted)) if opf_path else None,
        "toc_path": toc_path,
        "html_root_hint": _guess_html_root(extracted),
        "chapters": chapter_list,
        "images_count": len(images),
        "total_lines": sum(c["lines"] for c in chapter_list),
        "hints": hints,
    }


def _guess_html_root(extracted: Path) -> str | None:
    """猜测正文 HTML 所在目录（常见 OEBPS/Text），帮助 agent 快速定位。"""
    for sub in ("OEBPS/Text", "OEBPS", "EPUB", "text", "Text", "content", "html"):
        d = extracted / sub
        if d.is_dir() and (list(d.glob("*.html")) or list(d.glob("*.xhtml"))):
            return str(d.relative_to(extracted))
    return None


# --------------------------------------------------------------------------- #
# PDF 处理
# --------------------------------------------------------------------------- #
def inspect_pdf(path: Path) -> dict:
    """处理 .pdf 文件：用 PyMuPDF4LLM 的底层 pymupdf 获取 TOC 与文本量。"""
    import pymupdf  # PyMuPDF4LLM 的依赖，pip install pymupdf4llm 会带上

    try:
        doc = pymupdf.open(path)
    except Exception as e:  # noqa: BLE001
        print(f"Error: 无法打开 PDF '{path}'：{e}", file=sys.stderr)
        sys.exit(2)

    # 1. 内嵌书签 (TOC)：[[level, title, page(1-based)], ...]
    toc = doc.get_toc(simple=True)

    # 2. 统计每页文本量，判断是否扫描件
    page_infos = []
    total_chars = 0
    for i, page in enumerate(doc):
        text = page.get_text("text") or ""
        chars = len(text.strip())
        total_chars += chars
        page_infos.append({"page": i + 1, "chars": chars})

    page_count = doc.page_count
    avg_chars = total_chars / page_count if page_count else 0
    doc.close()

    # 扫描件判定：平均每页可提取字符极少
    needs_ocr = page_count > 0 and avg_chars < 50
    hints = []
    if needs_ocr:
        hints.append(
            "检测为扫描件（几乎无文本层）。建议用 RapidOCR 做中文 OCR 兜底"
            "（uv run --with rapidocr python -c '...'）；Tesseract 中文准确率差，不推荐。"
        )
    if not toc:
        hints.append(
            "PDF 无内嵌书签 (TOC)，需从正文（前言、目录页）人工识别章节边界。"
            "可先提取前若干页文本定位目录页。"
        )
    else:
        # 用 TOC 切分章节范围
        hints.append(
            "已从 PDF 书签提取章节结构，可按 page 范围用 pymupdf4llm.to_markdown(...) 分章提取。"
            "注意：文本层 PDF 务必传 use_ocr=False（默认 use_ocr=True 会用 Tesseract，慢且中文不准）。"
        )

    chapters = [
        {"level": lvl, "title": title, "start_page": pg}
        for lvl, title, pg in toc
    ]

    return {
        "file_type": "pdf",
        "source": str(path),
        "page_count": page_count,
        "total_chars": total_chars,
        "avg_chars_per_page": round(avg_chars, 1),
        "needs_ocr": needs_ocr,
        "has_toc": bool(toc),
        "chapters": chapters,
        "hints": hints,
    }


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="inspect_source.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="探查电子书源文件（epub / 已解压 epub 目录 / pdf），输出结构化 JSON 清单。",
        epilog="""\
示例:
  uv run inspect_source.py book.epub
  uv run inspect_source.py ./OEBPS/..        # 已解压的 epub 目录
  uv run inspect_source.py book.pdf
  uv run inspect_source.py book.epub --workdir /tmp/ebook_extract

输出（stdout JSON）字段:
  epub: file_type, source, extracted_dir, opf_path, toc_path,
        html_root_hint, chapters[{path,lines}], images_count, total_lines, hints
  pdf:  file_type, source, page_count, total_chars, avg_chars_per_page,
        needs_ocr, has_toc, chapters[{level,title,start_page}], hints
""",
    )
    p.add_argument("path", help="电子书路径：.epub / 已解压 epub 目录 / .pdf")
    p.add_argument(
        "--workdir",
        default=None,
        help="epub 解压目标目录（默认临时目录）。仅对 .epub 文件有效。",
    )
    return p


def main() -> None:
    args = build_arg_parser().parse_args()
    path = Path(args.path).expanduser().resolve()
    if not path.exists():
        print(f"Error: 路径不存在：{path}", file=sys.stderr)
        sys.exit(2)

    # 判别类型（统一 resolve()，规避 macOS /var → /private/var 符号链接导致的路径不一致）
    if path.is_file():
        if path.suffix.lower() == ".epub":
            result = inspect_epub(path.resolve(),
                                  Path(args.workdir).resolve() if args.workdir else None)
        elif path.suffix.lower() == ".pdf":
            result = inspect_pdf(path.resolve())
        else:
            print(f"Error: 不支持的文件类型：{path.suffix}（仅支持 .epub / .pdf）", file=sys.stderr)
            sys.exit(2)
    elif path.is_dir():
        if _is_epub_dir(path):
            result = inspect_epub(path.resolve(), None)
        else:
            print(f"Error: 目录不像 epub 结构（未找到 mimetype/META-INF/OEBPS）：{path}", file=sys.stderr)
            sys.exit(2)
    else:
        print(f"Error: 既不是文件也不是目录：{path}", file=sys.stderr)
        sys.exit(2)

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
