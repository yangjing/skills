#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
check-spec-conformance.py — SDD 规范符合性检查（项目中立）。

PEP 723 自包含脚本：依赖声明内嵌在上方 `# /// script` 块中，无需 venv 或 install。
本脚本刻意保持**零第三方依赖**——规范检查是门禁，门禁不该因为装不上包而失效。

检出五类**机械可判定**的违规。不做语义判断（「这条规则是否可验证」需要人或 agent
判断，不在本脚本范围）。

    C1  path:line 行号锚点        SDD SPECIFICATION §1.2
    C2  Agent 执行协议缺段        SDD sdd-overview §3.3
    C3  BCP 14 关键词小写         SDD 各分册头部「规范语言」
    C4  .overlay.md 命名违规      SDD sdd-overview §2.1
    C5  文档头缺 Status / Version SDD SPECIFICATION §4.1（文档控制字段）

用法：

    uv run scripts/check-spec-conformance.py                # 扫描本 skill 的 references/ 与 stacks/
    uv run scripts/check-spec-conformance.py --json         # 结构化输出
    uv run scripts/check-spec-conformance.py --self-test    # 校验规则本身的检出能力
    SDD_SCAN_ROOTS='docs/designs,docs/specs' uv run scripts/check-spec-conformance.py

零第三方依赖，故 `python3 scripts/check-spec-conformance.py` 等价可用——CI 或未装 uv
的环境直接用 python3 即可，无需为本脚本引入 uv。

**扫描面 MUST 限定为 SPECIFICATION §4.1.1 的 ①②③ 类规格体裁**（功能 / 系统规格、
总纲索引词表、技术设计与架构裁决）。以下体裁不受 C3 / C5 约束，MUST NOT 纳入扫描面：

    执行计划与归档、运营跟踪、UAT 执行记录、对外文稿、外部参考资料

把它们纳进来只会产出满屏假阳性——英文对外邮件里的 "must" 是普通英语不是 BCP 14，
执行计划与跟踪表也不承担文档控制字段义务。CLAUDE.md / AGENTS.md / 仓库根 README /
ADR 已内置豁免（见 c5_exempt），无需手工排除。

退出码：

    0  无违规
    1  发现违规
    2  配置或扫描面异常（扫描根不存在、收集到 0 个目标、self-test 失败）

环境变量：

    SDD_SCAN_ROOTS
        扫描根，逗号分隔，相对当前工作目录。三种形态：目录（递归收集 *.md）、
        文件（直接纳入）、glob（含 `*` / `?` / `[`，按 glob 展开）。
        默认为本 skill 的 references/ 与 stacks/。

        glob 用于两类扫描面：Agent 规则文档链（`apps/*/AGENTS.md`）与「仅顶层」
        （`docs/*.md` —— MUST NOT 递归，否则会把 exec-plans / uat 等非规格体裁卷进来）。

    SDD_STRICT_ROOTS=1
        任一扫描根未命中 markdown 时报错退出（默认只 WARN）。CI MUST 开启：
        一个写错的 glob（`apps/*/AGENT.md` 少个 S）会静默漏掉整批文件，而总数非零
        让结论看起来照常全绿——这正是「0 目标假绿」要防的形态。

    SDD_SKIP_DIRS
        跳过的目录名，逗号分隔。默认：
        .git,node_modules,target,dist,build,out,.next,.turbo,.cache,__pycache__

    SDD_CHECKS
        只跑指定检查，逗号分隔（如 'C1,C3'）。默认全跑。

    SDD_EXEMPT_GLOBS
        豁免路径 glob，逗号分隔。命中的文件跳过全部检查。用于历史留档 / 工作产物
        —— SDD §1.2 末层对它们豁免。例：'docs/exec-plans/archived/**,docs/uat/**'

设计取向：**假阳性比漏报更糟**。一个会误报的 gate 最终会被绕过，所以每条规则都
向「不报」倾斜：代码块内容、行内代码、链接目标、URL 一律不参与匹配。
"""

from __future__ import annotations

import fnmatch
import glob
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────────────────────────────

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ROOTS = [str(SKILL_DIR / "references"), str(SKILL_DIR / "stacks")]
DEFAULT_SKIP_DIRS = {
    ".git", "node_modules", "target", "dist", "build", "out",
    ".next", ".turbo", ".cache", "__pycache__",
}
ALL_CHECKS = ["C1", "C2", "C3", "C4", "C5"]
STRICT_ROOTS = os.environ.get("SDD_STRICT_ROOTS", "").strip() in ("1", "true", "yes")

# C1：path.<ext>:<line>，含全角变体。ext 覆盖源码 + 脚本 + 文档。
RE_LINE_ANCHOR = re.compile(
    r"[A-Za-z0-9_./-]+\.(?:rs|ts|tsx|js|jsx|sql|proto|toml|py|sh|md):\d+"
)
RE_LINE_ANCHOR_FW = re.compile(
    r"[A-Za-z0-9_./-]+．(?:rs|ts|tsx|js|jsx|sql|proto|toml|py|sh|md)：\d+"
)

# C2：Agent 执行协议节标题，以及六段各自的同义词组。
RE_PROTOCOL_HEADING = re.compile(r"^#{1,4}\s.*Agent\s*(执行|加载)?\s*协议")
PROTOCOL_SEGMENTS = {
    "Trigger": ["trigger"],
    "Load": ["load", "lookup"],
    "Apply": ["apply"],
    "Conflict/Stop": ["conflict", "stop"],
    "Output": ["output"],
    "MUST NOT": ["must not"],
}

# C3：BCP 14 关键词的小写形态。\b 词边界避免命中 "mustache" / "shoulder"。
RE_LOWER_BCP14 = re.compile(
    r"(?<![A-Za-z])(must not|shall not|should not|must|shall|should|may)(?![A-Za-z])"
)
# 只在「确实采用 BCP 14」的文件里查 C3，避免把普通英文散文当规范文档。
RE_UPPER_BCP14 = re.compile(r"(?<![A-Za-z])(MUST NOT|MUST|SHOULD NOT|SHOULD|MAY|SHALL)(?![A-Za-z])")

# C5：文档控制字段。兼容 YAML frontmatter 与 blockquote 头部两种载体。
# 载体规范（SPECIFICATION §4.1，2026-08-23 收紧）：正文文档控制字段 MUST 用 YAML frontmatter，
# blockquote 仅剩门面例外（承担控制字段义务的目录索引 README）合法。本检查只验字段
# 存在性、不验载体违规；blockquote 识别保留是为该例外与存量仓迁移期不产生假阳性。
# `\**` 吸收 markdown 强调标记：blockquote 头部写作 `> **Status**: active`，
# 冒号与关键词之间隔着 `**`，不吸收就会把合规头部全报成缺字段。
# 新鲜度字段的三种 casing（last_updated / last-updated / lastUpdated / LastUpdated）都要认——
# 只认其中一种会把用 YAML frontmatter 的整个文档树误报成缺字段。
RE_STATUS = re.compile(r"(^|\W)(Status|status)\**\s*[:：]")
RE_VERSION = re.compile(
    r"(^|\W)(Version|version|Last[_-]?Updated|last[_-]?updated|lastUpdated)\**\s*[:：]"
)


@dataclass
class Finding:
    check: str
    file: str
    line: int
    excerpt: str
    message: str


# ── 文本预处理 ────────────────────────────────────────────────────────────────

def strip_noise(line: str) -> str:
    """把不该参与匹配的片段替换为等长空白，保留列位置。

    剔除：行内代码 `...`、markdown 链接的目标部分 ](...)、裸 URL。
    """
    def blank(m: re.Match) -> str:
        return " " * len(m.group(0))

    line = re.sub(r"`[^`]*`", blank, line)
    line = re.sub(r"\]\([^)]*\)", blank, line)
    line = re.sub(r"https?://\S+", blank, line)
    return line


def iter_lines(text: str):
    """产出 (行号, 原始行, 去噪行)，跳过围栏代码块内部。"""
    in_fence = False
    for idx, raw in enumerate(text.splitlines(), start=1):
        if raw.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        yield idx, raw, strip_noise(raw)


# ── 五类检查 ──────────────────────────────────────────────────────────────────

def check_c1(path: str, text: str) -> list[Finding]:
    out = []
    for lineno, raw, clean in iter_lines(text):
        for rx in (RE_LINE_ANCHOR, RE_LINE_ANCHOR_FW):
            m = rx.search(clean)
            if m:
                out.append(Finding(
                    "C1", path, lineno, m.group(0),
                    "现行规范禁止 path:line 行号锚点（行号随重构漂移即失效）。"
                    "改用稳定符号锚点（模块路径 + 类型 / 函数 / RPC method / 表 / 约束名），"
                    "引用文档用标题锚点 #heading。判据 SPECIFICATION §1.2",
                ))
                break
    return out


def check_c2(path: str, text: str) -> list[Finding]:
    lines = text.splitlines()
    out = []
    for idx, raw in enumerate(lines):
        if not RE_PROTOCOL_HEADING.match(raw):
            continue
        # 取到下一个同级或更高级标题为止的区块。
        level = len(raw) - len(raw.lstrip("#"))
        body = []
        for nxt in lines[idx + 1:]:
            if nxt.startswith("#"):
                nxt_level = len(nxt) - len(nxt.lstrip("#"))
                if nxt_level <= level:
                    break
            body.append(nxt)
        blob = "\n".join(body).lower()
        missing = [
            name for name, aliases in PROTOCOL_SEGMENTS.items()
            if not any(a in blob for a in aliases)
        ]
        if missing:
            out.append(Finding(
                "C2", path, idx + 1, raw.strip(),
                f"Agent 执行协议缺段：{', '.join(missing)}。"
                "面向 Agent 自动执行 / 加载的规则 MUST 六段齐全"
                "（Trigger / Load 或 Lookup / Apply / Conflict 或 Stop / Output / MUST NOT）。"
                "判据 sdd-overview §3.3",
            ))
    return out


def check_c3(path: str, text: str) -> list[Finding]:
    # 文件不含大写 BCP 14 关键词 → 不是规范性文档，跳过（避免误报普通英文散文）。
    if not RE_UPPER_BCP14.search(text):
        return []
    out = []
    for lineno, raw, clean in iter_lines(text):
        m = RE_LOWER_BCP14.search(clean)
        if m:
            out.append(Finding(
                "C3", path, lineno, m.group(0),
                f"BCP 14 关键词 MUST 大写；小写 '{m.group(0)}' 不构成规范性语言，"
                "评审时无法与作者语气区分。若此处确为普通英文叙述，改写措辞避开该词",
            ))
    return out


def check_c4(path: str, text: str, reference_stems: set[str]) -> list[Finding]:
    name = Path(path).name
    if not name.endswith(".overlay.md"):
        return []
    out = []
    # 位置：overlay MUST NOT 落在 skill 内部。
    try:
        Path(path).resolve().relative_to(SKILL_DIR)
        out.append(Finding(
            "C4", path, 1, name,
            "overlay 文件 MUST NOT 放进 skill 目录内（references/ 或 stacks/）。"
            "MUST 置于 skill 安装目录同级或项目侧文档目录。判据 sdd-overview §2.1",
        ))
    except ValueError:
        pass
    # 命名：去掉 .overlay 后 MUST 对应一份真实分册。
    stem = name[: -len(".overlay.md")]
    if reference_stems and stem not in reference_stems and stem != "sdd":
        out.append(Finding(
            "C4", path, 1, name,
            f"'{stem}' 没有对应的 SDD 通用分册；无对应通用文档的项目文件 MUST NOT 加 .overlay。"
            f"现有分册：{', '.join(sorted(reference_stems))}。判据 sdd-overview §2.1",
        ))
    return out


def c5_exempt(path: str) -> bool:
    """文档控制字段只约束 SPECIFICATION §4.1.1 的 ①②③ 三类规格体裁。

    以下体裁不在其列，内置豁免——不豁免的话，一扩展到真实项目就是满屏假阳性：
      - Agent 规则文件（CLAUDE.md / AGENTS.md）：harness 按目录注入，非规格文档
      - 仓库根 README：项目门面，非规格目录索引（`docs/**/README.md` 仍受约束，属 ② 类）
      - ADR（`adr/NNNN-*.md`）：决策留痕体裁，日期随 Status 记录，无独立 LastUpdated
    """
    name = Path(path).name
    if name in {"CLAUDE.md", "AGENTS.md"}:
        return True
    parent = os.path.dirname(os.path.normpath(path))
    if name == "README.md" and parent in ("", ".", os.sep):
        return True
    if re.match(r"^\d{4}-", name) and f"{os.sep}adr{os.sep}" in f"{os.sep}{os.path.normpath(path)}":
        return True
    return False


def check_c5(path: str, text: str) -> list[Finding]:
    if c5_exempt(path):
        return []
    head = "\n".join(text.splitlines()[:15])
    missing = []
    if not RE_STATUS.search(head):
        missing.append("Status")
    if not RE_VERSION.search(head):
        missing.append("Version / LastUpdated")
    if missing:
        return [Finding(
            "C5", path, 1, (text.splitlines() or [""])[0][:80],
            f"文档头缺控制字段：{', '.join(missing)}（前 15 行内）。"
            "治理工具据此对文档目录做统一提取。判据 SPECIFICATION §4.1",
        )]
    return []


# ── 扫描 ──────────────────────────────────────────────────────────────────────

def expand_root(root: str, skip_dirs: set[str]) -> list[str]:
    """展开单个扫描根 → markdown 路径列表。三种形态：

      目录          递归收集 *.md
      文件          直接纳入
      glob（含 *）  按 glob 展开，命中的目录再递归、命中的 .md 直接纳入

    glob 是覆盖 Agent 规则文档链（`apps/*/AGENTS.md`）与「仅顶层」扫描面
    （`docs/*.md` MUST NOT 递归到 exec-plans / uat 等非规格体裁）所必需的。
    """
    out: list[str] = []

    def walk_dir(d: str) -> None:
        for dirpath, dirnames, filenames in os.walk(d):
            dirnames[:] = [x for x in dirnames if x not in skip_dirs]
            for fn in filenames:
                if fn.endswith(".md"):
                    out.append(os.path.join(dirpath, fn))

    if any(ch in root for ch in "*?["):
        for hit in sorted(glob.glob(root, recursive=True)):
            if os.path.isdir(hit):
                walk_dir(hit)
            elif hit.endswith(".md"):
                out.append(hit)
        return out

    p = Path(root)
    if not p.exists():
        print(f"ERROR: 扫描根不存在: {root}", file=sys.stderr)
        sys.exit(2)
    if p.is_file():
        if p.suffix == ".md":
            out.append(str(p))
        return out
    walk_dir(str(p))
    return out


def collect_targets(roots: list[str], skip_dirs: set[str], strict: bool) -> list[str]:
    """收集全部目标，并对**每个扫描根**做命中断言。

    逐根断言而非只看总数：一个写错的 glob（`apps/*/AGENT.md` 少个 S）会静默漏掉
    整批文件，而总数非零让结论看起来照常全绿——这正是「0 目标假绿」要防的形态。
    """
    found: list[str] = []
    for root in roots:
        hits = expand_root(root, skip_dirs)
        if not hits:
            msg = f"扫描根未命中任何 markdown: {root}"
            if strict:
                print(f"ERROR: {msg}（SDD_STRICT_ROOTS=1 下视为扫描面异常）", file=sys.stderr)
                sys.exit(2)
            print(f"WARN: {msg}", file=sys.stderr)
        found.extend(hits)
    return found


def run(roots: list[str], checks: list[str], skip_dirs: set[str],
        exempt: list[str], strict: bool = False) -> list[Finding]:
    targets = collect_targets(roots, skip_dirs, strict)
    targets = [
        t for t in targets
        if not any(fnmatch.fnmatch(t, g) or fnmatch.fnmatch(t.lstrip("./"), g)
                   for g in exempt)
    ]
    if not targets:
        print("ERROR: 收集到 0 个 markdown 目标，扫描面异常（0 目标假绿）", file=sys.stderr)
        sys.exit(2)

    ref_dir = SKILL_DIR / "references"
    reference_stems = {
        f.stem for f in ref_dir.glob("*.md")
    } if ref_dir.is_dir() else set()

    findings: list[Finding] = []
    for t in sorted(set(targets)):
        try:
            text = Path(t).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"WARN: 跳过不可读文件 {t}: {exc}", file=sys.stderr)
            continue
        if "C1" in checks:
            findings += check_c1(t, text)
        if "C2" in checks:
            findings += check_c2(t, text)
        if "C3" in checks:
            findings += check_c3(t, text)
        if "C4" in checks:
            findings += check_c4(t, text, reference_stems)
        if "C5" in checks:
            findings += check_c5(t, text)
    return findings


# ── self-test ─────────────────────────────────────────────────────────────────

def self_test(quiet: bool = False) -> int:
    """规则写错的方向都是假阳性或漏报，两者都比没有 gate 更糟。逐条钉住。

    quiet=True 时不向 stdout 打成功消息——`--json` 下 stdout MUST 只有 JSON，
    否则调用方的 `jq` / `json.load` 会在第一行就崩。
    """
    import tempfile

    fails = 0

    def expect(cond: bool, msg: str):
        nonlocal fails
        if not cond:
            print(f"SELF-TEST FAIL: {msg}", file=sys.stderr)
            fails = 1

    # C1
    hit = check_c1("t.md", "见 crates/foo/src/lib.rs:42 的实现")
    expect(len(hit) == 1, "C1 未检出行号锚点")
    expect(not check_c1("t.md", "见 `crates/foo/src/lib.rs:42`"), "C1 误报行内代码中的行号")
    expect(not check_c1("t.md", "```\nlib.rs:42\n```"), "C1 误报代码块中的行号")
    expect(len(check_c1("t.md", "见 lib．rs：42")) == 1, "C1 未检出全角变体")

    # C2
    full = ("## 0. Agent 执行协议\n1. Trigger: x\n2. Load: y\n3. Apply: z\n"
            "4. Conflict / Stop: w\n5. Output: v\n6. MUST NOT: u\n")
    expect(not check_c2("t.md", full), "C2 误报了六段齐全的协议")
    partial = "## 0. Agent 执行协议\n1. Trigger: x\n2. Load: y\n"
    got = check_c2("t.md", partial)
    expect(len(got) == 1 and "Apply" in got[0].message, "C2 未检出缺段")
    lookup_variant = ("## 0. Agent 执行协议\n1. Trigger: x\n2. Lookup: y\n3. Apply: z\n"
                      "4. Stop: w\n5. Output: v\n6. MUST NOT: u\n")
    expect(not check_c2("t.md", lookup_variant), "C2 未接受 Lookup / Stop 同义词")
    expect(not check_c2("t.md", "## 1. 别的标题\n没有协议\n"), "C2 对非协议节误报")

    # C3
    expect(len(check_c3("t.md", "MUST 用 X\n调用方 must 用 Y\n")) == 1, "C3 未检出小写关键词")
    expect(not check_c3("t.md", "调用方 must 用 Y\n"), "C3 在非 BCP14 文档上误报")
    expect(not check_c3("t.md", "MUST 用 X\n见 `must` 字面量\n"), "C3 误报行内代码")
    expect(not check_c3("t.md", "MUST 用 X\nmustache 模板\n"), "C3 误报 mustache（词边界失效）")

    # C5
    expect(not check_c5("t.md", "# T\n> **Status**: active · **Version**: v1\n"), "C5 误报合规头部")
    expect(len(check_c5("t.md", "# T\n正文\n")) == 1, "C5 未检出缺失控制字段")
    expect(not check_c5("t.md", "---\nstatus: active\nlast-updated: 2026-01-01\n---\n"),
           "C5 未接受 YAML frontmatter 形态")
    # 下划线 casing 曾漏认，导致整个 YAML frontmatter 文档树被误报。
    expect(not check_c5("t.md", "---\nstatus: active\nlast_updated: 2026-01-01\n---\n"),
           "C5 未接受 last_updated 下划线写法")
    expect(not check_c5("t.md", "---\nstatus: active\nlastUpdated: 2026-01-01\n---\n"),
           "C5 未接受 lastUpdated 驼峰写法")
    # 体裁豁免：不豁免的话，一扩展到真实项目就是满屏假阳性。
    expect(not check_c5("CLAUDE.md", "# rules\n"), "C5 未豁免 Agent 规则文件")
    expect(not check_c5("apps/web/AGENTS.md", "# rules\n"), "C5 未豁免子目录 AGENTS.md")
    expect(not check_c5("README.md", "# project\n"), "C5 未豁免仓库根 README")
    expect(not check_c5("docs/adr/0007-per-service-trust-root.md", "# ADR-0007\n"),
           "C5 未豁免 ADR 体裁")
    expect(len(check_c5("docs/specs/README.md", "# 索引\n正文\n")) == 1,
           "C5 误豁免了 docs 下的 README（② 类总纲 MUST 有控制字段）")
    expect(len(check_c5("docs/designs/x.md", "# 设计\n正文\n")) == 1,
           "C5 漏报了普通设计文档")

    # C4
    with tempfile.TemporaryDirectory() as td:
        bad = os.path.join(td, "nonexistent-doc.overlay.md")
        Path(bad).write_text("x", encoding="utf-8")
        got = check_c4(bad, "x", {"naming-conventions", "i18n-conventions"})
        expect(len(got) == 1, "C4 未检出无对应分册的 .overlay 命名")
        ok = os.path.join(td, "naming-conventions.overlay.md")
        Path(ok).write_text("x", encoding="utf-8")
        expect(not check_c4(ok, "x", {"naming-conventions"}), "C4 误报合规 overlay 命名")
        expect(not check_c4(os.path.join(td, "plain.md"), "x", {"a"}), "C4 对非 overlay 文件误报")

    # 扫描面展开：glob 写错会静默漏扫，比规则写错更难察觉。
    with tempfile.TemporaryDirectory() as td:
        for rel in ("docs/a.md", "docs/sub/b.md", "apps/web/AGENTS.md",
                    "apps/api/AGENTS.md", "CLAUDE.md"):
            f = Path(td) / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("# t\n", encoding="utf-8")
        cwd = os.getcwd()
        try:
            os.chdir(td)
            top = expand_root("docs/*.md", set())
            expect([os.path.normpath(x) for x in top] == [os.path.normpath("docs/a.md")],
                   "glob `docs/*.md` 递归到了子目录（顶层扫描面被污染）")
            agents = sorted(os.path.normpath(x) for x in expand_root("apps/*/AGENTS.md", set()))
            expect(agents == [os.path.normpath("apps/api/AGENTS.md"),
                              os.path.normpath("apps/web/AGENTS.md")],
                   "glob `apps/*/AGENTS.md` 未展开出 Agent 规则文档链")
            expect(len(expand_root("docs", set())) == 2, "目录扫描根未递归收集")
            expect(len(expand_root("CLAUDE.md", set())) == 1, "文件扫描根未纳入")
            expect(expand_root("apps/*/AGENT.md", set()) == [],
                   "写错的 glob 竟然命中了文件")
        finally:
            os.chdir(cwd)

    if fails:
        return 2
    if not quiet:
        print("OK: self-test 通过（C1-C5 检出 + 扫描面展开均正确，"
              "代码块 / 行内代码 / 词边界 / 同义词 / 顶层 glob 无误报）")
    return 0


# ── 入口 ──────────────────────────────────────────────────────────────────────

def main() -> int:
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(__doc__)
        return 0
    if "--self-test" in args:
        return self_test()

    as_json = "--json" in args
    show_all = "--all" in args

    roots = [r.strip() for r in os.environ.get("SDD_SCAN_ROOTS", "").split(",") if r.strip()]
    roots = roots or DEFAULT_ROOTS
    skip = {s.strip() for s in os.environ.get("SDD_SKIP_DIRS", "").split(",") if s.strip()}
    skip = skip or DEFAULT_SKIP_DIRS
    checks = [c.strip().upper() for c in os.environ.get("SDD_CHECKS", "").split(",") if c.strip()]
    checks = checks or ALL_CHECKS
    unknown = [c for c in checks if c not in ALL_CHECKS]
    if unknown:
        print(f"ERROR: SDD_CHECKS 含未知检查项 {unknown}；可选：{', '.join(ALL_CHECKS)}",
              file=sys.stderr)
        return 2
    exempt = [g.strip() for g in os.environ.get("SDD_EXEMPT_GLOBS", "").split(",") if g.strip()]

    # 规则自检先行：规则错了，结论就不可信。
    if self_test(quiet=as_json) != 0:
        print("ABORT: gate 自检未通过，本次结果不可信", file=sys.stderr)
        return 2

    findings = run(roots, checks, skip, exempt, strict=STRICT_ROOTS)

    if as_json:
        print(json.dumps({
            "findings": [asdict(f) for f in findings],
            "summary": {"total": len(findings),
                        "by_check": {c: sum(1 for f in findings if f.check == c)
                                     for c in ALL_CHECKS}},
        }, ensure_ascii=False, indent=2))
        return 1 if findings else 0

    if not findings:
        print(f"OK: 扫描 {', '.join(roots)} 无 SDD 规范符合性违规（检查项：{', '.join(checks)}）")
        return 0

    limit = len(findings) if show_all else min(len(findings), 50)
    print(f"发现 {len(findings)} 处 SDD 规范符合性违规：\n", file=sys.stderr)
    for f in findings[:limit]:
        print(f"  [{f.check}] {f.file}:{f.line}", file=sys.stderr)
        print(f"        {f.excerpt.strip()[:100]}", file=sys.stderr)
        print(f"        → {f.message}\n", file=sys.stderr)
    if limit < len(findings):
        print(f"  …另有 {len(findings) - limit} 处，用 --all 查看全部\n", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
