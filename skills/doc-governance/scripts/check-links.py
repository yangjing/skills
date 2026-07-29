#!/usr/bin/env python3
"""
check-links.py — 校验仓库内 Markdown 相对链接的有效性（项目中立版本）。

用法（从仓库根目录运行）：

    python3 <path-to-this-skill>/scripts/check-links.py

默认扫描（项目中立，按"常见 Markdown 摆放位置"匹配）：
  - docs/**/*.md
  - README.md / CLAUDE.md / AGENTS.md（仓根及一、二级子目录，含 monorepo 的
    apps/<app>/ 与 packages/<pkg>/）
  - 全大写或常见全小写命名的根级 *.md（CHANGELOG.md / SECURITY.md / ROADMAP.md 等）

跳过：
  - 通用噪声目录：.git / node_modules / target / dist / build / out
                .next / .turbo / .vercel / .cache / pnpm-store / .pnpm-store
  - 常见构建产物：doc_build / site / _site / .docusaurus / .vitepress
  - skill 内部树：.agents / .claude（不参与外部审计）
  - **docsite 子树（自动检测）**：包含 `rspress.config.*` / `mkdocs.{yml,yaml}` /
    `docusaurus.config.*` / `astro.config.*` 等配置文件的目录，整个子树跳过。
    这些静态站点的 build 命令（rspress build / mkdocs build --strict / 等）会做
    更严格的 ext-less 链接 + 路由 + base 校验,本脚本不重复实现。

环境变量配置：

  DOC_GOV_ROOT
      扫描根目录，默认当前目录（`.`）。

  DOC_GOV_INCLUDE
      自定义 INCLUDE 正则（分号 `;` 分隔多模式 — 不可用 `|`，避免与正则 alternation 冲突）。
      设置后**完全替换**默认 INCLUDE。
      示例：`'^docs/.*\\.md$;^(CLAUDE|README|AGENTS)\\.md$'`

  DOC_GOV_INCLUDE_EXTRA
      在默认 INCLUDE 之上**追加**模式（分号 `;` 分隔）。与 DOC_GOV_INCLUDE 互斥；
      设置 DOC_GOV_INCLUDE 时本变量被忽略。

  DOC_GOV_SKIP_DIRS
      自定义跳过目录（逗号 `,` 分隔）。设置后**完全替换**默认 SKIP_DIRS。

  DOC_GOV_SKIP_DIRS_EXTRA
      在默认 SKIP_DIRS 之上**追加**条目（逗号分隔）。

  DOC_GOV_SITE_CONFIGS
      自定义触发"docsite 自动跳过"的配置文件名（逗号分隔）。设置后**完全替换**默认集。
      默认集：rspress.config.{ts,js,mjs,cjs}, mkdocs.{yml,yaml},
              docusaurus.config.{ts,js,mjs,cjs}, astro.config.{ts,mjs,js}

  DOC_GOV_SITE_CONFIGS_EXTRA
      在默认 docsite 配置文件集之上**追加**条目（逗号分隔）。

  DOC_GOV_NO_SITE_AUTOSKIP=1
      关闭 docsite 自动跳过。打开后这些站点 *.md 会被纳入扫描，但 ext-less 链接
      会被报为 broken（除非你也通过 DOC_GOV_INCLUDE 限制扫描范围）。

  DOC_GOV_VERBOSE=1
      跳过 docsite 子树时打印 `# skip docsite: <rel>` 到 stderr。

  DOC_GOV_ADR_DIR
      ADR 目录（相对 DOC_GOV_ROOT），默认 `docs/adr`。用于校验反引号 `ADR-NNNN`
      引用是否有对应的 `NNNN-*.md` 文件。

  DOC_GOV_HISTORICAL_PREFIXES
      历史留档路径前缀（相对 DOC_GOV_ROOT，逗号分隔），默认 `docs/exec-plans/archived`。
      这些路径下的文件跳过 ADR / .md 反引号引用校验——历史留档是冻结文本，内部引用
      指向早期规划中从未真正建过的目录结构，校验它们既不可行也无实际意义。仍会正常
      参与 markdown `[text](path)` 链接校验（该项从未在这些文件里报过误报）。

  DOC_GOV_HISTORICAL_PREFIXES_EXTRA
      在默认历史留档前缀之上**追加**条目（逗号分隔）。

除 markdown `[text](path)` 链接外，额外做两类反引号纯文本引用校验，二者严重性不同：

  - `` `ADR-NNNN` `` 编号——按 DOC_GOV_ADR_DIR 目录下是否存在对应 `NNNN-*.md` 文件校验，
    计入 BROKEN（硬失败，影响退出码）。此类引用格式单一、误报率低。
  - `` `foo.md` `` / `` `docs/a/b.md` `` 文件名或路径——含路径分隔符时按仓库根 / 引用
    来源目录两种方式解析；纯文件名在全仓（跳过 SKIP_DIRS）按 basename 查找。计入
    CANDIDATE（非阻断，不影响退出码），因为同样的写法既可能是过期引用，也可能是
    "该文件届时会有"的前瞻性提及（如 overlay 登记的 TODO 落地路径）或纯粹的举例性
    文字（如 SPECIFICATION.md 用 `` `xx.md` `` 说明命名模式）——无法仅凭文本形态可靠
    区分，需人工判断，因此不当作硬 gate。

不处理无扩展名的裸 slug / 标题提及（如"TCF workflow mapping"），也不处理未加任何
反引号 / 链接标记的纯文本路径提及——两者都无法可靠区分"应为文件名"与普通文字，
贸然匹配会引入更大误报面。

输出：
  - BROKEN <src.md>  →  <dead-target>（硬失败：markdown 链接原始 URL，或反引号 ADR 引用）
  - CANDIDATE <src.md>  →  <token>（非阻断：反引号 .md 文件名/路径引用，需人工复核）
  - 返回码：0 = 无 BROKEN（可能仍有 CANDIDATE）；1 = 存在 BROKEN

设计意图（结果驱动）：
  - 检查相对链接、反引号 `ADR-NNNN` 引用（含 #anchor 时只校验文件部分）
  - 反引号 `.md` 引用单列 CANDIDATE 档，不与真正的硬失败混在一起拖垮 gate
  - 历史留档（DOC_GOV_HISTORICAL_PREFIXES）跳过新增的两类反引号校验
  - 不发起 http(s) 请求（不验外网链接）
  - 不解析 Markdown 锚点合法性（避免误报某些静态站点自动生成锚点）
  - 不解析 ext-less 链接（避免重复 docsite 工具链的工作）
  - 项目中立：默认匹配常见路径，特定项目通过环境变量覆盖 / 追加
"""

from __future__ import annotations

import os
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Iterable

ROOT = Path(os.environ.get("DOC_GOV_ROOT", ".")).resolve()

DEFAULT_INCLUDE_PATTERNS: list[str] = [
    r"^docs/.*\.md$",
    r"^(CLAUDE|README|AGENTS|CONTRIBUTING|CHANGELOG|SECURITY|ROADMAP|NOTICE|LICENSE)\.md$",
    # 一级子目录（deploy/AGENTS.md）与二级子目录（monorepo 的 apps/<app>/AGENTS.md、
    # packages/<pkg>/README.md）都要覆盖——漏掉二级会让 workspace 成员文档整批脱离校验面。
    r"^[a-z][a-z0-9_-]*(?:/[a-z0-9][a-z0-9._-]*)?/(CLAUDE|README|AGENTS|CONTRIBUTING)\.md$",
]

DEFAULT_SKIP_DIRS: set[str] = {
    ".git",
    "node_modules",
    "target",
    "dist",
    "build",
    "out",
    ".next",
    ".turbo",
    ".vercel",
    ".cache",
    "pnpm-store",
    ".pnpm-store",
    "doc_build",
    "site",
    "_site",
    ".docusaurus",
    ".vitepress",
    ".agents",
    ".claude",
}

DEFAULT_SITE_CONFIG_FILES: set[str] = {
    "rspress.config.ts", "rspress.config.js", "rspress.config.mjs", "rspress.config.cjs",
    "mkdocs.yml", "mkdocs.yaml",
    "docusaurus.config.ts", "docusaurus.config.js", "docusaurus.config.mjs", "docusaurus.config.cjs",
    "astro.config.ts", "astro.config.mjs", "astro.config.js",
}

DEFAULT_HISTORICAL_PREFIXES: set[str] = {
    "docs/exec-plans/archived",
}


def _compile_patterns(parts: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(p.strip()) for p in parts if p.strip()]


def _load_include_patterns() -> list[re.Pattern[str]]:
    override = os.environ.get("DOC_GOV_INCLUDE", "").strip()
    if override:
        return _compile_patterns(override.split(";"))
    parts = list(DEFAULT_INCLUDE_PATTERNS)
    extra = os.environ.get("DOC_GOV_INCLUDE_EXTRA", "").strip()
    if extra:
        parts.extend(extra.split(";"))
    return _compile_patterns(parts)


def _load_set_env(override_var: str, extra_var: str, defaults: set[str]) -> set[str]:
    override = os.environ.get(override_var, "").strip()
    if override:
        return {s.strip() for s in override.split(",") if s.strip()}
    extra = os.environ.get(extra_var, "").strip()
    result = set(defaults)
    if extra:
        result.update(s.strip() for s in extra.split(",") if s.strip())
    return result


INCLUDE_PATTERNS = _load_include_patterns()
SKIP_DIRS = _load_set_env("DOC_GOV_SKIP_DIRS", "DOC_GOV_SKIP_DIRS_EXTRA", DEFAULT_SKIP_DIRS)
SITE_CONFIG_FILES = _load_set_env(
    "DOC_GOV_SITE_CONFIGS", "DOC_GOV_SITE_CONFIGS_EXTRA", DEFAULT_SITE_CONFIG_FILES
)
SITE_AUTOSKIP = os.environ.get("DOC_GOV_NO_SITE_AUTOSKIP", "").strip() not in ("1", "true", "yes")
VERBOSE = os.environ.get("DOC_GOV_VERBOSE", "").strip() in ("1", "true", "yes")
ADR_DIR = os.environ.get("DOC_GOV_ADR_DIR", "docs/adr").strip() or "docs/adr"
HISTORICAL_PREFIXES = {
    p.rstrip("/")
    for p in _load_set_env(
        "DOC_GOV_HISTORICAL_PREFIXES", "DOC_GOV_HISTORICAL_PREFIXES_EXTRA", DEFAULT_HISTORICAL_PREFIXES
    )
}

LINK_RE = re.compile(r"(?<!\!)\[([^\]]+)\]\(([^)]+)\)")
BACKTICK_RE = re.compile(r"`([^`\n]+)`")
# 锚定反引号内容开头：避免 `<skill-name>.overlay.md`、`*-architecture.md` 这类占位符 /
# glob 模式被截断误配为字面文件名（截断后的 "overlay.md"/"architecture.md" 并非真实引用）。
MD_TOKEN_RE = re.compile(r"^([\w][\w./-]*\.md)\b")
ADR_TOKEN_RE = re.compile(r"\bADR-(\d{4})\b")


def _is_docsite(dir_path: Path) -> bool:
    try:
        entries = os.listdir(dir_path)
    except OSError:
        return False
    return any(name in SITE_CONFIG_FILES for name in entries)


def _is_historical(md: Path) -> bool:
    s = str(md)
    return any(s == p or s.startswith(p + "/") for p in HISTORICAL_PREFIXES)


def iter_md_files() -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(ROOT):
        kept: list[str] = []
        for d in dirnames:
            if d in SKIP_DIRS:
                continue
            child = Path(dirpath) / d
            if SITE_AUTOSKIP and _is_docsite(child):
                if VERBOSE:
                    try:
                        rel = child.resolve().relative_to(ROOT)
                    except ValueError:
                        rel = child
                    print(f"# skip docsite: {rel}", file=sys.stderr)
                continue
            kept.append(d)
        dirnames[:] = kept

        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            p = (Path(dirpath) / fn).relative_to(ROOT)
            ps = str(p)
            if any(pat.match(ps) for pat in INCLUDE_PATTERNS):
                yield p


def extract_links(md: Path) -> list[str]:
    try:
        text = (ROOT / md).read_text(encoding="utf-8")
    except Exception:
        return []
    return [m.group(2).strip() for m in LINK_RE.finditer(text)]


def resolve_target(src: Path, url: str) -> Path | None:
    if url.startswith(("http://", "https://", "#", "mailto:", "tel:", "data:")):
        return None
    if url.startswith("file://"):
        url = url[len("file://"):]
    path = url.split("#", 1)[0].split("?", 1)[0]
    if not path:
        return None
    path = urllib.parse.unquote(path)
    if path.startswith("/"):
        target = ROOT / path.lstrip("/")
    else:
        target = (ROOT / src).parent / path
    try:
        return target.resolve(strict=False)
    except Exception:
        return target


def _read_text(md: Path) -> str:
    try:
        return (ROOT / md).read_text(encoding="utf-8")
    except Exception:
        return ""


def extract_backtick_md_refs(md: Path) -> list[str]:
    tokens: list[str] = []
    for bt in BACKTICK_RE.finditer(_read_text(md)):
        m = MD_TOKEN_RE.match(bt.group(1))
        if m:
            tokens.append(m.group(1))
    return tokens


def extract_backtick_adr_refs(md: Path) -> list[str]:
    nums: list[str] = []
    for bt in BACKTICK_RE.finditer(_read_text(md)):
        nums.extend(m.group(1) for m in ADR_TOKEN_RE.finditer(bt.group(1)))
    return nums


_BASENAME_INDEX: dict[str, list[Path]] | None = None


def _basename_index() -> dict[str, list[Path]]:
    """全仓（跳过 SKIP_DIRS）文件名 → 路径列表索引，供纯文件名反引号引用解析；只建一次。"""
    global _BASENAME_INDEX
    if _BASENAME_INDEX is not None:
        return _BASENAME_INDEX
    index: dict[str, list[Path]] = {}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            index.setdefault(fn, []).append((Path(dirpath) / fn).relative_to(ROOT))
    _BASENAME_INDEX = index
    return index


def resolve_md_token(src: Path, token: str) -> bool:
    """反引号内 `.md` 文件名 / 路径引用是否存在。含路径分隔符时按仓库根 / 引用来源目录
    两种方式解析；纯文件名时在全仓 basename 索引中查找。"""
    if "/" in token:
        for base in (ROOT, (ROOT / src).parent):
            try:
                if (base / token).resolve(strict=False).exists():
                    return True
            except Exception:
                continue
        return False
    return token in _basename_index()


def resolve_adr_token(num: str) -> bool:
    adr_dir = ROOT / ADR_DIR
    if not adr_dir.is_dir():
        return False
    prefix = f"{num}-"
    return any(p.name.startswith(prefix) for p in adr_dir.glob("*.md"))


USAGE = """\
Usage: python3 check-links.py            (run from repo root; no positional args)

Validate relative Markdown links, backtick `ADR-NNNN` refs, and backtick `*.md`
refs across the repository.
Configuration is via DOC_GOV_* environment variables only (see module docstring):
  DOC_GOV_ROOT, DOC_GOV_INCLUDE, DOC_GOV_INCLUDE_EXTRA,
  DOC_GOV_SKIP_DIRS, DOC_GOV_SKIP_DIRS_EXTRA,
  DOC_GOV_SITE_CONFIGS[_EXTRA], DOC_GOV_NO_SITE_AUTOSKIP, DOC_GOV_VERBOSE,
  DOC_GOV_ADR_DIR, DOC_GOV_HISTORICAL_PREFIXES[_EXTRA]

Output:
  BROKEN     <file>  →  <link>   (markdown links + ADR refs; hard failure)
  CANDIDATE  <file>  →  <token>  (backtick *.md refs; informational only)
Exit codes:  0 = no BROKEN (CANDIDATEs may remain) · 1 = BROKEN found · 2 = usage error
"""


def main() -> int:
    args = sys.argv[1:]
    if args:
        if args[0] in ("-h", "--help"):
            print(USAGE)
            return 0
        print(f"Error: unexpected argument {args[0]!r} — this script takes no "
              "positional arguments (configure via DOC_GOV_* env vars).\n",
              file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    broken: list[tuple[str, str]] = []
    candidates: list[tuple[str, str]] = []
    files = list(iter_md_files())
    for md in files:
        for url in extract_links(md):
            target = resolve_target(md, url)
            if target is None:
                continue
            if not target.exists():
                broken.append((str(md), url))
        if _is_historical(md):
            continue
        for num in extract_backtick_adr_refs(md):
            if not resolve_adr_token(num):
                broken.append((str(md), f"`ADR-{num}`"))
        for token in extract_backtick_md_refs(md):
            if not resolve_md_token(md, token):
                candidates.append((str(md), f"`{token}`"))

    exit_code = 0
    if broken:
        for src, url in broken:
            print(f"BROKEN  {src}  →  {url}")
        print(f"\nTotal broken: {len(broken)}  (scanned {len(files)} files)")
        exit_code = 1
    else:
        print(f"All links & ADR references OK across {len(files)} markdown files.")

    if candidates:
        print(f"\n候选待核实引用（不计入 broken、不影响退出码，需人工判断是否为过期引用 / "
              f"前瞻 TODO / 举例性文字）：")
        for src, token in candidates:
            print(f"CANDIDATE  {src}  →  {token}")
        print(f"Total candidates: {len(candidates)}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
