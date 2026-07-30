#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
check_glossary.py — 验证读书笔记的术语一致性与保留英文词使用。

针对 ebook-ai-notes 产出的笔记目录（含 _glossary.md 全书术语表 + 各章 *.md），
检查三类问题（对应网络最佳实践 Lokalise「确定性约束」理念，把术语合规从
「prompt 概率服从」升级为「脚本确定性检查」）：

  1. 译法一致性（error）：各章笔记「本章术语」表里，同一英文术语的中文译法
     必须与 _glossary.md「翻译术语」段一致。不一致 = 译法漂移。
  2. 保留英文检查（warning）：_glossary.md「保留英文」段的词，在笔记正文应
     以英文出现；若被完全中文化（如 MCP 只出现「模型上下文协议」而无英文），提示。
  3. 译法漂移检测（warning）：同一英文术语在不同章笔记出现多个不同中文译法，
     列出冲突项供裁决回写 _glossary.md。

退出码：
  0 — 无 error（warning 不影响退出码，但会输出）
  1 — 有 error（译法与术语库不一致）

用法：
  uv run check_glossary.py <notes-dir>                  # 默认 <notes-dir>/_glossary.md
  uv run check_glossary.py <notes-dir> --glossary X.md
  uv run check_glossary.py --self-test
  uv run check_glossary.py --help
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _err(msg: str) -> None:
    """诊断信息走 stderr，不污染 stdout 的 JSON。"""
    print(msg, file=sys.stderr)


# --------------------------------------------------------------------------- #
# 三段式术语库解析（与 translate-epub/validate_translation.py 对齐的格式基准）
# --------------------------------------------------------------------------- #
def _parse_three_section_glossary(text: str) -> dict:
    """按 ## 小节标题切分三段式术语库。返回 {translate, keep_english, forbidden}。"""
    sections = re.split(r"^##\s+", text, flags=re.MULTILINE)
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
    # 旧格式（无三段标题）：全文表格当 translate
    if not result["translate"] and not result["keep_english"] and not result["forbidden"]:
        result["translate"] = _parse_table_rows(text)
    return result


def _parse_table_rows(body: str) -> dict[str, str]:
    """从 markdown 表格行解析 {english: chinese}，跳过表头与分隔行。"""
    terms = {}
    for m in re.finditer(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", body, re.MULTILINE):
        en = m.group(1).strip()
        zh = m.group(2).strip()
        if en.lower() in ("英文", "english", "term", "-", ""):
            continue
        if zh.lower() in ("中文译法", "chinese", "translation", "-", ""):
            continue
        if re.fullmatch(r"[-:\s]+", en):
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


# --------------------------------------------------------------------------- #
# 笔记解析：提取每章笔记的「本章术语」表
# --------------------------------------------------------------------------- #
def _extract_chapter_terms(note_path: Path) -> dict[str, str]:
    """
    从单章笔记提取「本章术语」表（## 📚 本章术语 段下的表格）。
    返回 {english: chinese}。若无该段返回空 dict。
    """
    try:
        text = note_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    # 定位「本章术语」小节（到下一个 ## 或文件末尾）
    m = re.search(r"##\s*📚\s*本章术语(.*?)(?=^##\s|\Z)", text, re.DOTALL | re.MULTILINE)
    if not m:
        return {}
    section = m.group(1)
    return _parse_table_rows(section)


def _check_consistency(
    glossary_translate: dict[str, str],
    chapter_terms_by_file: dict[Path, dict[str, str]],
) -> list[dict]:
    """
    检查 1：各章术语译法与 _glossary.md 一致性。
    返回冲突列表 [{file, term, expected, actual}]（error）。
    """
    conflicts = []
    for fpath, terms in chapter_terms_by_file.items():
        for en, zh in terms.items():
            # 在术语库中查同一英文（精确匹配，大小写不敏感）
            canonical = _lookup_case_insensitive(glossary_translate, en)
            if canonical is not None and canonical != zh:
                conflicts.append({
                    "file": fpath.name,
                    "term": en,
                    "expected": canonical,
                    "actual": zh,
                })
    return conflicts


def _lookup_case_insensitive(d: dict[str, str], key: str) -> str | None:
    """大小写不敏感查找 dict 的 key，返回 value。"""
    key_lower = key.lower()
    for k, v in d.items():
        if k.lower() == key_lower:
            return v
    return None


def _check_drift(chapter_terms_by_file: dict[Path, dict[str, str]]) -> list[dict]:
    """
    检查 3：同一英文术语在不同章笔记出现多个不同中文译法（漂移）。
    返回 [{term, translations: {zh: [files]}}]（warning）。
    """
    # 聚合：term -> {zh_translation: [file_names]}
    term_translations: dict[str, dict[str, list[str]]] = {}
    for fpath, terms in chapter_terms_by_file.items():
        for en, zh in terms.items():
            en_key = en.lower()
            term_translations.setdefault(en_key, {"_display": en})
            term_translations[en_key].setdefault(zh, [])
            term_translations[en_key][zh].append(fpath.name)
    drifts = []
    for en_key, transls in term_translations.items():
        # 只看 zh 译法（排除 _display 元数据键）
        zh_variants = {k: v for k, v in transls.items() if k != "_display"}
        if len(zh_variants) > 1:
            drifts.append({
                "term": transls["_display"],
                "translations": zh_variants,
            })
    return drifts


def _check_keep_english_in_notes(
    notes_dir: Path,
    keep_words: list[str],
    exclude: set[Path],
) -> list[dict]:
    """
    检查 2：保留英文词在笔记正文应以英文出现。
    扫描所有 .md（排除 _glossary.md），若某词在全文从未以英文形式出现 → warning。
    返回 [{word, note_count_scanned}]。
    """
    if not keep_words:
        return []
    all_notes = [p for p in notes_dir.glob("*.md") if p not in exclude]
    combined = ""
    for n in all_notes:
        try:
            combined += n.read_text(encoding="utf-8", errors="replace") + "\n"
        except OSError:
            continue
    missing = []
    for word in keep_words:
        if not re.search(r"(?<![A-Za-z0-9])" + re.escape(word) + r"(?![A-Za-z0-9])",
                         combined, re.IGNORECASE):
            missing.append({"word": word, "note_count": len(all_notes)})
    return missing


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def run_checks(notes_dir: Path, glossary_path: Path) -> dict:
    """对笔记目录运行全部检查，返回结构化结果。"""
    glossary_text = glossary_path.read_text(encoding="utf-8", errors="replace")
    parsed = _parse_three_section_glossary(glossary_text)
    glossary_translate = parsed["translate"]
    keep_english = parsed["keep_english"]

    # 收集各章笔记（排除 README、_glossary.md 自身、下划线开头的元文件）
    note_files = [
        p for p in sorted(notes_dir.glob("*.md"))
        if p.name != glossary_path.name
        and not p.name.startswith("_")
        and p.name.upper() != "README.MD"
    ]

    chapter_terms = {p: _extract_chapter_terms(p) for p in note_files}

    consistency_conflicts = _check_consistency(glossary_translate, chapter_terms)
    drifts = _check_drift(chapter_terms)
    keep_english_missing = _check_keep_english_in_notes(
        notes_dir, keep_english, exclude={glossary_path}
    )

    return {
        "notes_dir": str(notes_dir),
        "glossary": str(glossary_path),
        "glossary_terms_count": len(glossary_translate),
        "keep_english_count": len(keep_english),
        "notes_scanned": len(note_files),
        "errors": {
            "consistency_conflicts": consistency_conflicts,
        },
        "warnings": {
            "term_drifts": drifts,
            "keep_english_missing": keep_english_missing,
        },
        "passed": len(consistency_conflicts) == 0,
    }


# --------------------------------------------------------------------------- #
# 自测（--self-test）
# --------------------------------------------------------------------------- #
def _self_test() -> None:
    """内置自测：断言解析与检查逻辑正确，含三段式术语库与漂移检测。"""
    import tempfile
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # 1. 三段式术语库解析
    glossary_text = """\
# 全书术语表（Glossary）

## 翻译术语（English → Chinese）
| 英文 | 中文译法 | 简释 | 首现 |
|---|---|---|---|
| agent | 智能体 | xxx | 第1章 |
| persona | 人设 | xxx | 第1章 |

## 保留英文（不翻译）
MCP, ReAct, Docker
"""
    parsed = _parse_three_section_glossary(glossary_text)
    check(parsed["translate"] == {"agent": "智能体", "persona": "人设"},
          f"三段式解析: translate 错误，实际 {parsed['translate']}")
    check("MCP" in parsed["keep_english"],
          f"三段式解析: keep_english 应含 MCP，实际 {parsed['keep_english']}")

    # 1b. _parse_inline_list 健壮性：保留英文段含说明文字/分类注释不应误解析
    keep_body = """> 协议名、框架名一律保留英文。
# 协议类（注释行应跳过）
MCP
A2A
这是中文说明应跳过
Docker, Node.js
"""
    keep_words = _parse_inline_list(keep_body)
    check(keep_words == ["MCP", "A2A", "Docker", "Node.js"],
          f"_parse_inline_list: 应跳过引用行/注释/中文，实际 {keep_words}")

    # 2. 笔记术语表提取
    note_text = """\
# 第 1 章 · 智能体的崛起

## 📚 本章术语
> 全书术语统一收录在 _glossary.md

| 英文 | 统一中文译法 |
|---|---|
| agent | 智能体 |
| MCP | 模型上下文协议 |

## 💎 金句
xxx
"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write(note_text)
        note_path = Path(tf.name)
    try:
        terms = _extract_chapter_terms(note_path)
        check(terms.get("agent") == "智能体", f"笔记术语提取: agent 应=智能体，实际 {terms}")
        check(terms.get("MCP") == "模型上下文协议", f"笔记术语提取: MCP 错误，实际 {terms}")
    finally:
        note_path.unlink()

    # 3. 一致性检查：笔记译法与术语库冲突应报错
    glossary_translate = {"agent": "智能体", "persona": "人设"}
    chapter_terms_conflict = {
        Path("ch1.md"): {"agent": "智能体"},      # 一致
        Path("ch2.md"): {"persona": "人格"},       # 冲突！术语库是人设
    }
    conflicts = _check_consistency(glossary_translate, chapter_terms_conflict)
    check(len(conflicts) == 1 and conflicts[0]["term"] == "persona",
          f"一致性检查: 应报 1 个 persona 冲突，实际 {conflicts}")
    check(conflicts[0]["expected"] == "人设" and conflicts[0]["actual"] == "人格",
          f"一致性检查: 冲突字段错误，实际 {conflicts[0]}")

    # 4. 漂移检测：同一术语多译法
    chapter_terms_drift = {
        Path("ch1.md"): {"handoff": "交接"},
        Path("ch2.md"): {"handoff": "移交"},
        Path("ch3.md"): {"agent": "智能体"},
    }
    drifts = _check_drift(chapter_terms_drift)
    check(len(drifts) == 1 and drifts[0]["term"] == "handoff",
          f"漂移检测: 应报 handoff 1 处漂移，实际 {drifts}")
    check(len(drifts[0]["translations"]) == 2,
          f"漂移检测: handoff 应有 2 种译法，实际 {drifts[0]['translations']}")

    # 5. 大小写不敏感：MCP 与 mcp 视为同一术语
    chapter_terms_case = {Path("ch1.md"): {"MCP": "模型上下文协议"}}
    conflicts_case = _check_consistency({"mcp": "模型上下文协议"}, chapter_terms_case)
    check(not conflicts_case, f"大小写不敏感: MCP vs mcp 应无冲突，实际 {conflicts_case}")

    if failures:
        _err("❌ 自测失败：")
        for f in failures:
            _err(f"  - {f}")
        sys.exit(1)
    _err(f"✓ 自测通过（{len(failures)} 失败）")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="check_glossary.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="验证读书笔记的术语一致性、保留英文词使用、译法漂移。",
        epilog="""\
退出码：0 无 error，1 有 error（译法与 _glossary.md 不一致）。
示例:
  uv run check_glossary.py notes/my-book/
  uv run check_glossary.py notes/my-book/ --glossary notes/my-book/_glossary.md
  uv run check_glossary.py --self-test
""",
    )
    p.add_argument("notes_dir", nargs="?", help="笔记目录（含 _glossary.md 与各章 *.md）")
    p.add_argument("--glossary", default=None,
                   help="术语库路径（默认 <notes_dir>/_glossary.md）")
    p.add_argument("--self-test", action="store_true",
                   help="运行内置自测，无需 notes_dir 参数。")
    return p


def main() -> None:
    args = build_arg_parser().parse_args()

    if args.self_test:
        _self_test()
        return

    if not args.notes_dir:
        _err("Error: 缺少 notes_dir 参数（或使用 --self-test 运行自测）")
        sys.exit(2)

    notes_dir = Path(args.notes_dir).expanduser().resolve()
    if not notes_dir.is_dir():
        _err(f"Error: 笔记目录不存在：{notes_dir}")
        sys.exit(2)

    glossary_path = (
        Path(args.glossary).expanduser().resolve()
        if args.glossary
        else notes_dir / "_glossary.md"
    )
    if not glossary_path.exists():
        _err(f"Error: 术语库不存在：{glossary_path}")
        sys.exit(2)

    result = run_checks(notes_dir, glossary_path)

    # 诊断输出（stderr）
    _err(f"扫描 {result['notes_scanned']} 个笔记，术语库含 "
         f"{result['glossary_terms_count']} 条翻译术语 / "
         f"{result['keep_english_count']} 个保留英文词")

    errors = result["errors"]
    warnings = result["warnings"]

    if errors["consistency_conflicts"]:
        _err(f"❌ 译法不一致（{len(errors['consistency_conflicts'])} 处，须与 _glossary.md 对齐）：")
        for c in errors["consistency_conflicts"][:10]:
            _err(f"  {c['file']}: 「{c['term']}」术语库={c['expected']}，笔记={c['actual']}")

    if warnings["term_drifts"]:
        _err(f"⚠️  译法漂移（{len(warnings['term_drifts'])} 个术语有多译法，建议裁决回写 _glossary.md）：")
        for d in warnings["term_drifts"][:10]:
            transls = "; ".join(f"{zh}(@{','.join(files)})" for zh, files in d["translations"].items())
            _err(f"  「{d['term']}」: {transls}")

    if warnings["keep_english_missing"]:
        _err(f"⚠️  保留英文词未在笔记出现（{len(warnings['keep_english_missing'])} 个，"
             f"可能被中文化，建议保留英文）：")
        for m in warnings["keep_english_missing"][:10]:
            _err(f"  「{m['word']}」（已扫 {m['note_count']} 个笔记均未出现）")

    if result["passed"]:
        _err("✓ 无 error（warning 不影响）")
    else:
        _err("✗ 有 error，请修正后重跑")

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
