#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
build_epub.py — 把翻译后的解压 EPUB 目录打包成 .epub 文件。

EPUB 打包规则：
  - mimetype 文件必须 uncompressed 且作为 zip 的第一个条目
  - 其余文件正常 deflate 压缩

用法：
  uv run build_epub.py <source-dir> <output.epub>
  uv run build_epub.py --help

其中 <source-dir> 是包含 mimetype / META-INF / OEBPS 的解压目录。
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def build_epub(source_dir: Path, output: Path) -> None:
    if not (source_dir / "mimetype").exists():
        _err(f"Error: {source_dir} 下未找到 mimetype，不是有效的 EPUB 解压目录。")
        sys.exit(2)

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    with zipfile.ZipFile(output, "w") as zf:
        # 1. mimetype 必须第一个，且不压缩（stored）
        mimetype_path = source_dir / "mimetype"
        zf.write(mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED)

        # 2. 其余所有文件，正常压缩，排除 mimetype 自身
        for fp in sorted(source_dir.rglob("*")):
            if fp.is_file() and fp.name != "mimetype":
                arcname = fp.relative_to(source_dir).as_posix()
                zf.write(fp, arcname, compress_type=zipfile.ZIP_DEFLATED)

    _err(f"[build_epub] 已打包：{output}（{sum(1 for _ in source_dir.rglob('*') if _.is_file())} 个文件）")


def main() -> None:
    p = argparse.ArgumentParser(
        prog="build_epub.py",
        description="把翻译后的解压 EPUB 目录打包成 .epub（mimetype 不压缩且置首）。",
        epilog="""\
示例:
  uv run build_epub.py book-dual/epub book-dual.epub
""",
    )
    p.add_argument("source_dir", help="包含 mimetype/META-INF/OEBPS 的解压目录")
    p.add_argument("output", help="输出 .epub 文件路径")
    args = p.parse_args()

    source = Path(args.source_dir).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not source.is_dir():
        _err(f"Error: 源目录不存在：{source}")
        sys.exit(2)

    build_epub(source, output)


if __name__ == "__main__":
    main()
