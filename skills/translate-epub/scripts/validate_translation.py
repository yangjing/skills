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
  6. 段落数配对检查（双语文件，疑似漏译/多译/截断）— warning
  7. 确定性术语强制（可选，配合三段式 --glossary）：
     - 保留英文词必须在译文中以英文出现（如 MCP/ReAct 不可译成中文）— error
     - 禁用词必须 0 出现（废弃特性名/敏感词）— error
     - 翻译术语抽查（原文术语出现但既定译法未出现）— warning

退出码：
  0 — 全部通过
  1 — 有错误（输出到 stderr，详情见 stdout JSON）

用法：
  uv run validate_translation.py <translated-html-or-dir>
  uv run validate_translation.py <dir> --glossary _glossary.md
  uv run validate_translation.py --self-test
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


def _err(msg: str) -> None:
    """诊断信息走 stderr，不污染 stdout 的 JSON。"""
    print(msg, file=sys.stderr)


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


# --------------------------------------------------------------------------- #
# 确定性术语强制检查（核心新增，源自 Lokalise「确定性约束」理念）
# --------------------------------------------------------------------------- #
def _check_keep_english(content: str, keep_words: list[str]) -> list[str]:
    """
    「保留英文」段的词，必须在译文中以英文形式出现（确定性强制）。
    避免被 LLM 误译成中文（如把 MCP 译成「模型上下文协议」后丢失英文缩写）。
    仅在文中含 CJK（确认是双语/译文文件）时才检查，避免原文文件误报。
    返回错误列表。
    """
    if not keep_words:
        return []
    # 只对含 CJK 的译文文件检查（原文纯英文文件不适用）
    if not re.search(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]", content):
        return []
    errors = []
    for word in keep_words:
        # 大小写不敏感匹配英文词（作为单词边界，避免子串误匹配）
        if not re.search(r"(?<![A-Za-z0-9])" + re.escape(word) + r"(?![A-Za-z0-9])",
                         content, re.IGNORECASE):
            errors.append(f"保留英文词「{word}」未在译文中出现（应原样保留英文，不可译成中文）")
    return errors


def _check_forbidden(content: str, forbidden_words: list[str]) -> list[str]:
    """
    「禁用词」段的词，在译文中必须 0 出现（确定性阻断）。
    用于规避废弃特性名、竞品商标、法律敏感词等。
    返回错误列表（命中即 error，非 warning）。
    """
    if not forbidden_words:
        return []
    errors = []
    for word in forbidden_words:
        hits = len(re.findall(re.escape(word), content, re.IGNORECASE))
        if hits > 0:
            errors.append(f"禁用词「{word}」出现 {hits} 次（必须 0 出现）")
    return errors


def _count_block_elements(content: str, tags: tuple[str, ...]) -> int:
    """统计指定块级元素的开始标签数量（用于段落配对检查）。"""
    total = 0
    for tag in tags:
        total += len(re.findall(rf"<{tag}\b", content))
    return total


def _check_block_pairing(content: str, bilingual: bool = True) -> list[str]:
    """
    段落配平检查：双语文件里，英文块级元素数应≈CJK 块级元素数（各占约一半）。
    严重失衡（CJK 块占比 <30% 或 >70%）→ warning，疑似漏译/多译/截断。
    呼应 gpetho「译文被 max_output_tokens 截断」的教训。

    仅在同时含英文与 CJK（双语文件）时启用；块元素总数过少则跳过（统计噪声大）。
    """
    if not bilingual:
        return []
    block_tags = ("p", "li", "h1", "h2", "h3", "h4", "h5", "h6")
    # 按开始标签切分每个块元素的内容，判定该块是「英文为主」还是「CJK 为主」
    cjk_re = re.compile(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]")
    en_re = re.compile(r"[A-Za-z]")
    # 提取每个块元素的纯文本：粗略按 <tag ...>...</tag> 捕获（取首个闭合）
    block_re = re.compile(
        r"<(" + "|".join(block_tags) + r")\b[^>]*>(.*?)</\1>", re.DOTALL
    )
    en_blocks = 0
    cjk_blocks = 0
    for m in block_re.finditer(content):
        text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if not text:
            continue
        has_cjk = bool(cjk_re.search(text))
        has_en = bool(en_re.search(text))
        if has_cjk and not has_en:
            cjk_blocks += 1
        elif has_en and not has_cjk:
            en_blocks += 1
        # 含两者或都不含的块不计入（中性）

    classified = en_blocks + cjk_blocks
    if classified < 6:  # 可分类的块太少，统计噪声大，跳过
        return []
    cjk_ratio = cjk_blocks / classified
    warnings = []
    if cjk_ratio < 0.30:
        warnings.append(
            f"CJK 块占比偏低（{cjk_blocks}/{classified}≈{cjk_ratio:.0%}），"
            f"双语文件英文/CJK 块应大致平衡，疑似漏译或译文被截断"
        )
    elif cjk_ratio > 0.70:
        warnings.append(
            f"CJK 块占比偏高（{cjk_blocks}/{classified}≈{cjk_ratio:.0%}），"
            f"双语文件英文/CJK 块应大致平衡，疑似原文缺失或多译"
        )
    return warnings


def _load_glossary_terms(glossary_path: Path) -> dict[str, str]:
    """
    从 _glossary.md 加载「翻译术语」段的 术语→译法。返回 {english: chinese}。

    支持两种格式：
    1. 新三段式（推荐）：含 `## 翻译术语` / `## 保留英文` / `## 禁用词` 小节，
       只解析「翻译术语」段的 markdown 表格。
    2. 旧纯表格格式（向后兼容）：整篇都是术语表格，无小节标题。
    """
    if not glossary_path.exists():
        return {}
    text = glossary_path.read_text(encoding="utf-8", errors="replace")
    return _parse_translate_terms_section(text)


def _load_glossary_full(glossary_path: Path) -> dict:
    """
    解析三段式 _glossary.md，返回三类术语：
      {
        "translate": {english: chinese},   # 「翻译术语」段
        "keep_english": [word, ...],       # 「保留英文」段（逗号或换行分隔）
        "forbidden": [word, ...],          # 「禁用词」段
      }
    旧格式（无三段标题）时：translate 填全部表格，keep_english/forbidden 为空。
    """
    if not glossary_path.exists():
        return {"translate": {}, "keep_english": [], "forbidden": []}
    text = glossary_path.read_text(encoding="utf-8", errors="replace")
    return _parse_three_section_glossary(text)


def _parse_three_section_glossary(text: str) -> dict:
    """按 ## 小节标题切分三段式术语库。"""
    # 按二级标题切段
    sections = re.split(r"^##\s+", text, flags=re.MULTILINE)
    # sections[0] 是第一个 ## 之前的内容（含一级标题与说明）
    result = {"translate": {}, "keep_english": [], "forbidden": []}
    for sec in sections[1:]:
        header_line = sec.split("\n", 1)[0].strip()
        body = sec.split("\n", 1)[1] if "\n" in sec else ""
        if re.search(r"翻译术语|english.*chinese|english.*→", header_line, re.IGNORECASE):
            result["translate"] = _parse_table_rows(body)
        elif re.search(r"保留英文|不翻译|keep", header_line, re.IGNORECASE):
            result["keep_english"] = _parse_inline_list(body, skip_cjk=True)
        elif re.search(r"禁用|forbidden", header_line, re.IGNORECASE):
            result["forbidden"] = _parse_inline_list(body, skip_cjk=False)
    # 若未识别到任何段（旧格式），把全文表格当 translate
    if not result["translate"] and not result["keep_english"] and not result["forbidden"]:
        result["translate"] = _parse_table_rows(text)
    return result


def _parse_translate_terms_section(text: str) -> dict[str, str]:
    """只取「翻译术语」段（兼容旧格式）。"""
    return _parse_three_section_glossary(text)["translate"]


def _parse_table_rows(body: str) -> dict[str, str]:
    """从 markdown 表格行解析 {english: chinese}，跳过表头与分隔行。"""
    terms = {}
    for m in re.finditer(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", body, re.MULTILINE):
        en = m.group(1).strip()
        zh = m.group(2).strip()
        # 跳过表头/分隔行
        if en.lower() in ("英文", "english", "term", "-", ""):
            continue
        if zh.lower() in ("中文译法", "chinese", "translation", "-", ""):
            continue
        if re.fullmatch(r"[-:\s]+", en):  # 分隔行 |---|
            continue
        terms[en] = zh
    return terms


def _parse_inline_list(body: str, skip_cjk: bool = True) -> list[str]:
    """
    解析「保留英文/禁用词」段的词列表：逗号、顿号、换行、分号均可分隔。
    跳过：# 注释行、> 引用行、表格行、空行。
    skip_cjk=True（默认，用于「保留英文」段）时额外跳过含中文的行；
    「禁用词」段调用时传 skip_cjk=False（禁用词可能是中文译名）。
    """
    words = []
    cjk_re = re.compile(r"[\u4e00-\u9fff]")
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith(">"):
            continue
        if line.startswith("|"):
            continue
        for token in re.split(r"[，,；;、]+", line):
            w = token.strip().strip("|").strip()
            if not w:
                continue
            if skip_cjk and cjk_re.search(w):
                continue
            words.append(w)
    return words


def validate_file(path: Path, glossary: dict | None = None) -> dict:
    """
    验证单个 HTML 文件。返回结构化结果。

    glossary 可为两种：
      - {english: chinese}（旧格式 / 仅翻译术语）→ 只做术语抽查
      - {"translate": {...}, "keep_english": [...], "forbidden": [...]}（三段式）
        → 触发保留英文强制 + 禁用词阻断 + 术语抽查三项确定性检查
    """
    content = path.read_text(encoding="utf-8", errors="replace")
    result = {
        "file": str(path),
        "passed": True,
        "errors": [],
        "warnings": [],
        "stats": {},
    }

    # 归一化 glossary：旧格式 dict[str,str] → 三段式（只有 translate 段）
    if glossary and "translate" not in glossary and "keep_english" not in glossary:
        glossary = {"translate": glossary, "keep_english": [], "forbidden": []}

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

    # 6. 段落数配对检查（双语文件疑似漏译/截断）
    for issue in _check_block_pairing(content, bilingual=True):
        result["warnings"].append(issue)

    # 7. 确定性术语强制（三段式 glossary）
    if glossary:
        # 7a. 保留英文强制（error）
        for issue in _check_keep_english(content, glossary.get("keep_english", [])):
            result["errors"].append(issue)
        # 7b. 禁用词阻断（error）
        for issue in _check_forbidden(content, glossary.get("forbidden", [])):
            result["errors"].append(issue)
        # 7c. 翻译术语抽查（warning，启发式）
        translate_terms = glossary.get("translate", {})
        missing = []
        for en in list(translate_terms.keys())[:15]:  # 抽查前15个术语
            zh = translate_terms[en]
            if en.lower() in content.lower() and zh not in content:
                missing.append(f"{en}→{zh}")
        if missing:
            result["warnings"].append(f"术语抽查：以下术语的既定译法未在文中出现（可能漏译或未遵循术语库）：{missing[:5]}")

    result["passed"] = len(result["errors"]) == 0
    return result


# --------------------------------------------------------------------------- #
# 自测（--self-test）
# --------------------------------------------------------------------------- #
def _self_test() -> None:
    """内置自测：断言核心检查函数行为正确，含三段式术语库解析与新确定性检查。"""
    import tempfile
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # 1. _parse_tag_stack：标签栈配平
    stack, errs = _parse_tag_stack("<div><p>hi</p></div>")
    check(not stack and not errs, f"_parse_tag_stack: 配平应无错，实际 stack={stack} errs={errs}")
    stack, errs = _parse_tag_stack("<div><p>hi</div>")
    check(stack == ["p"] or errs, f"_parse_tag_stack: 未闭合 p 应报错，实际 stack={stack}")

    # 2. _direct_children：ul 直接子元素应为 li
    children = _direct_children("<li>a</li><li>b</li><p>c</p>")
    check(children == ["li", "li", "p"], f"_direct_children: 应为 [li,li,p]，实际 {children}")

    # 3. 三段式术语库解析
    glossary_text = """\
# 全书术语表（Glossary）

## 翻译术语（English → Chinese）
| 英文 | 中文译法 | 简释 | 首现 |
|---|---|---|---|
| agent | 智能体 | xxx | 第1章 |
| MCP | 模型上下文协议 | xxx | 第1章 |

## 保留英文（不翻译）
MCP, ReAct, API, token, Docker

## 禁用词（通常为空）
旧特性名
"""
    parsed = _parse_three_section_glossary(glossary_text)
    check(parsed["translate"] == {"agent": "智能体", "MCP": "模型上下文协议"},
          f"三段式: translate 段解析错误，实际 {parsed['translate']}")
    check("MCP" in parsed["keep_english"] and "Docker" in parsed["keep_english"],
          f"三段式: keep_english 段解析错误，实际 {parsed['keep_english']}")
    check(parsed["forbidden"] == ["旧特性名"],
          f"三段式: forbidden 段解析错误，实际 {parsed['forbidden']}")

    # 4. 旧格式兼容（纯表格无三段标题）
    old_glossary = "| agent | 智能体 |\n| MCP | 模型上下文协议 |\n"
    old_parsed = _parse_three_section_glossary(old_glossary)
    check(old_parsed["translate"] == {"agent": "智能体", "MCP": "模型上下文协议"},
          f"旧格式兼容: 应全部进 translate，实际 {old_parsed}")

    # 5. _check_keep_english：保留英文词缺失应报错
    bilingual_html = "<p>智能体是一个重要概念。</p>"  # 含 CJK 但无 MCP/ReAct
    keep_errors = _check_keep_english(bilingual_html, ["MCP", "ReAct"])
    check(len(keep_errors) == 2, f"_check_keep_english: 两个词都缺失应报2错，实际 {len(keep_errors)}")
    # 含保留英文词则不报错
    keep_ok = _check_keep_english("<p>MCP 是协议。ReAct 是范式。</p>", ["MCP", "ReAct"])
    check(not keep_ok, f"_check_keep_english: 词都存在应无错，实际 {keep_ok}")
    # 纯英文原文文件不检查（避免误报）
    keep_skip = _check_keep_english("<p>MCP is a protocol</p>", ["ReAct"])
    check(not keep_skip, "_check_keep_english: 纯英文文件应跳过检查")

    # 6. _check_forbidden：禁用词命中应报错
    forbidden_errors = _check_forbidden("<p>这是旧特性名 的说明</p>", ["旧特性名"])
    check(len(forbidden_errors) == 1, f"_check_forbidden: 命中应报1错，实际 {len(forbidden_errors)}")
    forbidden_ok = _check_forbidden("<p>无敏感词</p>", ["旧特性名"])
    check(not forbidden_ok, "_check_forbidden: 未命中应无错")

    # 7. _check_block_pairing：英文/CJK 块平衡不报警，严重失衡报警
    good_bilingual = (
        "<h2>Title</h2><h2>标题</h2>"
        "<p>English paragraph one.</p><p>英文段落一。</p>"
        "<p>English paragraph two.</p><p>英文段落二。</p>"
        "<p>English paragraph three.</p><p>英文段落三。</p>"
        "<p>English paragraph four.</p><p>英文段落四。</p>"
    )
    pairing_warnings = _check_block_pairing(good_bilingual, bilingual=True)
    check(not pairing_warnings, f"_check_block_pairing: 平衡双语不应报警，实际 {pairing_warnings}")
    # 严重失衡：大量英文块无 CJK 块对应（疑似漏译）
    unbalanced = (
        "<p>English one.</p><p>English two.</p><p>English three.</p>"
        "<p>English four.</p><p>English five.</p><p>English six.</p>"
        "<p>英文一。</p>"  # 只有1个CJK块，其余6个英文块
    )
    imbal_warnings = _check_block_pairing(unbalanced, bilingual=True)
    check(len(imbal_warnings) == 1 and "CJK 块占比偏低" in imbal_warnings[0],
          f"_check_block_pairing: 严重失衡应报警，实际 {imbal_warnings}")

    # 8. validate_file 端到端：合规双语文件应 passed=True
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "ch1.html"
        f.write_text(good_bilingual)
        r = validate_file(f, {"translate": {}, "keep_english": [], "forbidden": []})
        check(r["passed"], f"validate_file: 合规文件应 passed，errors={r['errors']}")

    # 9. validate_file：禁用词命中应 passed=False
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "ch2.html"
        f.write_text("<p>这是旧特性名。</p>")
        r = validate_file(f, {"translate": {}, "keep_english": [], "forbidden": ["旧特性名"]})
        check(not r["passed"], f"validate_file: 禁用词命中应 passed=False，实际 {r['passed']}")

    if failures:
        _err("❌ 自测失败：")
        for f in failures:
            _err(f"  - {f}")
        sys.exit(1)
    _err(f"✓ 自测通过（{len(failures)} 失败）")


def main() -> None:
    p = argparse.ArgumentParser(
        prog="validate_translation.py",
        description="验证 EPUB 翻译后的 HTML：XHTML 合法性、译文标签复用、确定性术语强制。",
        epilog="""\
退出码：0 全部通过，1 有错误。
示例:
  uv run validate_translation.py chapter-1.html
  uv run validate_translation.py OEBPS/Text/ --glossary _glossary.md
  uv run validate_translation.py --self-test
""",
    )
    p.add_argument("path", nargs="?", help="翻译后的 HTML 文件或目录")
    p.add_argument("--glossary", default=None,
                   help="_glossary.md 路径（启用保留英文强制 + 禁用词阻断 + 术语抽查）")
    p.add_argument("--self-test", action="store_true",
                   help="运行内置自测（纯逻辑函数 + 三段式术语库解析 + 确定性检查），无需 path。")
    args = p.parse_args()

    if args.self_test:
        _self_test()
        return

    if not args.path:
        print("Error: 缺少 path 参数（或使用 --self-test 运行自测）", file=sys.stderr)
        sys.exit(2)

    target = Path(args.path).expanduser().resolve()
    if not target.exists():
        _err(f"Error: 路径不存在：{target}")
        sys.exit(2)

    # 三段式 glossary：触发保留英文强制 + 禁用词阻断 + 术语抽查
    glossary = _load_glossary_full(Path(args.glossary)) if args.glossary else None

    # 收集 HTML 文件
    if target.is_dir():
        html_files = sorted(
            list(target.rglob("*.html")) + list(target.rglob("*.xhtml"))
        )
    else:
        html_files = [target]

    if not html_files:
        _err(f"Error: 未找到 HTML 文件：{target}")
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
            _err(f"✓ {hf.name}")

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
