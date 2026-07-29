#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
validate_translation.py — 验证 EPUB 翻译后的 HTML 文件质量。

检查项：
  1. XHTML 标签栈配平（开闭匹配，无遗漏/多余）
  2. <ul>/<ol> 直接子元素全为 <li>（XHTML 合法性）
  3. 全角引号残留检测（HTML 属性内的 “ ” 应为半角）
  4. 自定义翻译标记残留检测（class="zh-translation" 等应已消除，译文应复用原文标签）
  5. 译文标签复用情况（原文元素与紧跟其后的译文元素标签是否一致）
  6. 术语一致性抽查（可选，配合 --glossary）

退出码：
  0 — 全部通过
  1 — 有错误（输出到 stderr，详情见 stdout JSON）

用法：
  uv run validate_translation.py <translated-html-or-dir>
  uv run validate_translation.py <dir> --glossary GLOSSARY.md
  uv run validate_translation.py --help
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# XHTML void / 自闭合元素
_VOID_TAGS = {"img", "br", "hr", "col", "meta", "link", "input", "area", "base", "embed", "source", "track", "wbr"}


def _parse_tag_stack(content: str) -> tuple[list[str], list[str]]:
    """严格标签栈解析。返回 (未闭合栈, 错误列表)。"""
    re_tag = re.compile(r"<(\/?)([a-zA-Z0-9]+)([^>]*?)(\/?)>")
    stack: list[str] = []
    errors: list[str] = []
    for m in re_tag.finditer(content):
        closing = m.group(1) == "/"
        tag = m.group(2).lower()
        self_close = m.group(4) == "/" or tag in _VOID_TAGS
        if closing:
            if stack and stack[-1] == tag:
                stack.pop()
            else:
                errors.append(f"多余 </{tag}> @pos{m.start()}")
        elif not self_close:
            stack.append(tag)
    return stack, errors


def _direct_children(inner: str) -> list[str]:
    """返回某容器的直接子元素标签名列表（用深度追踪，只取 depth=0）。"""
    re_tag = re.compile(r"<(\/?)([a-zA-Z0-9]+)([^>]*?)(\/?)>")
    depth = 0
    direct: list[str] = []
    for m in re_tag.finditer(inner):
        closing = m.group(1) == "/"
        tag = m.group(2).lower()
        self_close = m.group(4) == "/" or tag in _VOID_TAGS
        if closing:
            depth -= 1
        else:
            if depth == 0:
                direct.append(tag)
            if not self_close:
                depth += 1
    return direct


def _check_fullwidth_quotes(content: str) -> list[str]:
    """检测 HTML 属性内的全角引号。"""
    issues = []
    n = content.count("\u201c") + content.count("\u201d")
    if n > 0:
        issues.append(f"发现 {n} 个全角引号 “ ”，应修正为半角 \"（会破坏 HTML 属性解析）")
    return issues


def _check_custom_markers(content: str) -> list[str]:
    """检测应已消除的自定义翻译标记。"""
    issues = []
    markers = [
        (r'class="zh-translation"', 'class="zh-translation"（译文应复用原文标签，无需自定义 class）'),
        (r'class=' + chr(0x201c) + r'zh-translation', "全角引号包裹的 zh-translation class"),
    ]
    for pat, desc in markers:
        n = len(re.findall(pat, content))
        if n > 0:
            issues.append(f"残留自定义标记：{desc}（{n} 处）")
    return issues


def _check_translation_tag_reuse(content: str) -> tuple[int, int]:
    """
    检查译文元素是否复用了原文标签。
    启发式：找连续两个相同标签的兄弟元素，前者含英文、后者含目标语言 → 视为正确复用。
    返回 (正确配对数, 疑似问题数)。
    """
    # 找连续的同标签兄弟：<tag>...</tag>\s*<tag>...</tag>
    re_pair = re.compile(
        r"<(h[1-6]|p|li)\b[^>]*>([^<]*(?:<[^>]+>[^<]*)*)</\1>\s*<\1\b[^>]*>([^<]*(?:<[^>]+>[^<]*)*)</\1>",
        re.DOTALL,
    )
    correct = 0
    suspect = 0
    for m in re_pair.finditer(content):
        first_text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        second_text = re.sub(r"<[^>]+>", "", m.group(3)).strip()
        if not first_text or not second_text:
            continue
        first_has_cjk = bool(re.search(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]", first_text))
        second_has_cjk = bool(re.search(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]", second_text))
        # 原文(英文) + 译文(中日韩) 或反之
        if (first_has_cjk and not second_has_cjk) or (not first_has_cjk and second_has_cjk):
            correct += 1
    return correct, suspect


def _load_glossary_terms(glossary_path: Path) -> dict[str, str]:
    """从 GLOSSARY.md 的 markdown 表格加载 术语→译法。返回 {english: chinese}。"""
    terms = {}
    if not glossary_path.exists():
        return terms
    text = glossary_path.read_text(encoding="utf-8", errors="replace")
    # 匹配表格行 | english | chinese |
    for m in re.finditer(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", text, re.MULTILINE):
        en = m.group(1).strip()
        zh = m.group(2).strip()
        if en and zh and en.lower() not in ("英文", "english", "-"):
            terms[en] = zh
    return terms


def validate_file(path: Path, glossary: dict[str, str] | None = None) -> dict:
    """验证单个 HTML 文件。返回结构化结果。"""
    content = path.read_text(encoding="utf-8", errors="replace")
    result = {
        "file": str(path),
        "passed": True,
        "errors": [],
        "warnings": [],
        "stats": {},
    }

    # 1. 标签栈
    stack, errors = _parse_tag_stack(content)
    if stack:
        result["errors"].append(f"标签栈未闭合：{stack}")
    if errors:
        result["errors"].extend(errors[:5])  # 最多报5条
    result["stats"]["unclosed_stack"] = len(stack)
    result["stats"]["tag_errors"] = len(errors)

    # 2. ul/ol 子元素
    for container_re, container_name in [(r"<ul\b[^>]*>(.*?)</ul>", "ul"),
                                          (r"<ol\b[^>]*>(.*?)</ol>", "ol")]:
        for cm in re.finditer(container_re, content, re.DOTALL):
            children = _direct_children(cm.group(1))
            non_li = [c for c in children if c != "li"]
            if non_li:
                result["errors"].append(
                    f"<{container_name}> 含非法直接子元素：{non_li}（应全为 <li>）"
                )

    # 3. 全角引号
    for issue in _check_fullwidth_quotes(content):
        result["warnings"].append(issue)

    # 4. 自定义标记残留
    for issue in _check_custom_markers(content):
        result["errors"].append(issue)

    # 5. 译文标签复用
    correct, _ = _check_translation_tag_reuse(content)
    result["stats"]["reused_tag_pairs"] = correct

    # 6. 术语抽查（可选）
    if glossary:
        missing = []
        for en in list(glossary.keys())[:15]:  # 抽查前15个术语
            zh = glossary[en]
            # 若原文术语出现在文中，但译文译法未出现，可能是未遵循术语库
            # （启发式，可能有误报，只作 warning）
            if en.lower() in content.lower() and zh not in content:
                missing.append(f"{en}→{zh}")
        if missing:
            result["warnings"].append(f"术语抽查：以下术语的既定译法未在文中出现（可能漏译或未遵循术语库）：{missing[:5]}")

    result["passed"] = len(result["errors"]) == 0
    return result


def main() -> None:
    p = argparse.ArgumentParser(
        prog="validate_translation.py",
        description="验证 EPUB 翻译后的 HTML：XHTML 合法性、译文标签复用、术语一致性。",
        epilog="""\
退出码：0 全部通过，1 有错误。
示例:
  uv run validate_translation.py chapter-1.html
  uv run validate_translation.py OEBPS/Text/ --glossary GLOSSARY.md
""",
    )
    p.add_argument("path", help="翻译后的 HTML 文件或目录")
    p.add_argument("--glossary", default=None, help="GLOSSARY.md 路径（启用术语抽查）")
    args = p.parse_args()

    target = Path(args.path).expanduser().resolve()
    if not target.exists():
        print(f"Error: 路径不存在：{target}", file=sys.stderr)
        sys.exit(2)

    glossary = _load_glossary_terms(Path(args.glossary)) if args.glossary else None

    # 收集 HTML 文件
    if target.is_dir():
        html_files = sorted(
            list(target.rglob("*.html")) + list(target.rglob("*.xhtml"))
        )
    else:
        html_files = [target]

    if not html_files:
        print(f"Error: 未找到 HTML 文件：{target}", file=sys.stderr)
        sys.exit(2)

    all_results = []
    total_errors = 0
    for hf in html_files:
        r = validate_file(hf, glossary)
        all_results.append(r)
        if not r["passed"]:
            total_errors += 1
            _err(f"✗ {hf.name}: {len(r['errors'])} 错误")
            for e in r["errors"][:3]:
                _err(f"    {e}")
        else:
            print(f"✓ {hf.name}", file=sys.stderr)

    summary = {
        "total_files": len(html_files),
        "passed": len(html_files) - total_errors,
        "failed": total_errors,
        "results": all_results,
    }
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")

    sys.exit(1 if total_errors > 0 else 0)


if __name__ == "__main__":
    main()
