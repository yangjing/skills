#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
check-links.py — 校验仓库内 Markdown 相对链接与章节锚点的有效性（项目中立版本）。

PEP 723 自包含脚本，零第三方依赖——门禁不该因为装不上包而失效，故 `python3` 直跑等价。

用法（从仓库根目录运行）：

    uv run <path-to-this-skill>/scripts/check-links.py
    uv run <path-to-this-skill>/scripts/check-links.py --self-test   # 校验 gate 本身的检出能力

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

  DOC_GOV_NO_ANCHOR_CHECK=1
      关闭 `#anchor` 章节锚点校验（只校验文件是否存在）。默认开启：SSOT 体系由链接
      承载，改一个章节标题就能静默制造一批死锚点，而这类漂移只在有人点开时才暴露。
      docsite 子树本就整树跳过，故自动生成锚点的误报面不在扫描范围内。

  DOC_GOV_CANDIDATE_ALLOWLIST
      CANDIDATE 白名单文件路径（相对 DOC_GOV_ROOT 或绝对路径）；未设置时默认
      `<ROOT>/.doc-gov-candidate-allowlist`（不存在则不启用）。
      逐行登记人工甄别后确认无需处理的 `src → token` 对，行格式与脚本输出一致
      （可直接粘贴 CANDIDATE 行，`CANDIDATE` 前缀与反引号可有可无）：

          CANDIDATE  docs/specs/README.md  →  `conceptual-entity-model.md`

      `#` 开头的行视为注释。白名单只压制 CANDIDATE 输出，不影响 BROKEN 判定。
      条目防腐由脚本自动承担：一轮扫描中未被消费的条目（引用已消失，或目标已落地、
      豁免变多余）会以 `STALE` 报出提醒回删（非阻断）。

除 markdown `[text](path)` 链接外，额外做两类反引号纯文本引用校验，二者严重性不同：

  - `` `ADR-NNNN` `` 编号——按 DOC_GOV_ADR_DIR 目录下是否存在对应 `NNNN-*.md` 文件校验，
    计入 BROKEN（硬失败，影响退出码）。此类引用格式单一、误报率低。
  - `` `foo.md` `` / `` `docs/a/b.md` `` 文件名或路径——含路径分隔符时依次按仓库根 /
    引用来源目录 / **末段对齐**（token 路径段与仓内某 `.md` 相对路径尾部段完全一致
    且命中唯一，如 `` `specs/x/main.md` `` → `docs/specs/x/main.md`）三种方式解析；
    纯文件名在全仓按 basename 查找。计入 CANDIDATE（非阻断，不影响退出码），因为
    同样的写法既可能是过期引用，也可能是"该文件届时会有"的前瞻性提及（如 overlay
    登记的 TODO 落地路径）或纯粹的举例性文字（如 SPECIFICATION.md 用 `` `xx.md` ``
    说明命名模式）——无法仅凭文本形态可靠区分，需人工判断，因此不当作硬 gate。
    经人工甄别确认无需处理的条目可登记进 CANDIDATE 白名单（见
    DOC_GOV_CANDIDATE_ALLOWLIST），登记后不再重报，保证新增候选不被存量噪声淹没。

不处理无扩展名的裸 slug / 标题提及（如"TCF workflow mapping"），也不处理未加任何
反引号 / 链接标记的纯文本路径提及——两者都无法可靠区分"应为文件名"与普通文字，
贸然匹配会引入更大误报面。

输出：
  - BROKEN <src.md>  →  <dead-target>（硬失败：markdown 链接原始 URL、失效 #anchor，
    或反引号 ADR 引用）
  - CANDIDATE <src.md>  →  <token>（非阻断：反引号 .md 文件名/路径引用，需人工复核）
  - 返回码：0 = 无 BROKEN（可能仍有 CANDIDATE）；1 = 存在 BROKEN；2 = 用法错误或自检失败

章节锚点校验（`#anchor`）按 GitHub slug 规则，三条易错规则各自都会造成**假阳性**
（把有效锚点报成死链），故均有 self-test 钉住：

  1. markdown 链接 MUST 在删标点之前折叠成其文字，否则 `[x](y)` 会变成 `xy`。
  2. 空格 MUST **逐个**转连字符，MUST NOT 折叠连续空格。标题里的 `/` `+` `=` 这类
     标点被删后会留下相邻的两个空格，GitHub 据此产出双连字符——
     `## 5. SlaPolicy / ScheduleDefinition` 的真实锚点是 `#5-slapolicy--scheduledefinition`。
  3. 重复标题按出现顺序追加 `-1` / `-2` 后缀。

CJK MUST 计入 alnum（`str.isalnum()` 对中文返回 True），否则中文标题的 slug 会全部
算错并产出一屏假阳性。假阳性的 gate 最终会被绕过，所以这不是可选的健壮性修饰。

设计意图（结果驱动）：
  - 检查相对链接、`#anchor` 章节锚点、反引号 `ADR-NNNN` 引用
  - 反引号 `.md` 引用单列 CANDIDATE 档，不与真正的硬失败混在一起拖垮 gate
  - 历史留档（DOC_GOV_HISTORICAL_PREFIXES）跳过两类反引号校验与 `#anchor` 校验，
    但仍校验链接文件存在性——留档里的锚点指向写就当时的目标结构，目标改名不使留档出错
  - 主流程每次运行前跑一遍 self-test：slug 规则一旦写错，结论就不可信——不是漏报
    就是一屏假阳性，两者都比没有 gate 更糟。自检失败 MUST 阻断，MUST NOT 降级为警告
  - 不发起 http(s) 请求（不验外网链接）
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
ANCHOR_CHECK = os.environ.get("DOC_GOV_NO_ANCHOR_CHECK", "").strip() not in ("1", "true", "yes")

LINK_RE = re.compile(r"(?<!\!)\[([^\]]+)\]\(([^)]+)\)")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
BACKTICK_RE = re.compile(r"`([^`\n]+)`")
# 锚定反引号内容开头：避免 `<skill-name>.overlay.md`、`*-architecture.md` 这类占位符 /
# glob 模式被截断误配为字面文件名（截断后的 "overlay.md"/"architecture.md" 并非真实引用）。
#
# 已知限制（CJK 词边界盲区）：末尾 `\b` 在 ASCII→CJK 边界处不匹配——当反引号 `.md`
# 路径紧跟中文字符时（如 `` `foo/bar.md`` 中文 ''），`\b` 失配导致整条引用被跳过，
# 不进入 CANDIDATE。受影响的引用不会误报，但也不会被检出为失效引用。当前全仓
# CLAUDE.md / AGENTS.md 的此类引用经人工核验均有效；若将来 CJK 路径引用频繁出现，
# 考虑放宽为 ``(?=\.md$|[^\w])`` 并补 self-test。
MD_TOKEN_RE = re.compile(r"^([\w][\w./-]*\.md)\b")
ADR_TOKEN_RE = re.compile(r"\bADR-(\d{4})\b")


HEADING_RE = re.compile(r"^#{1,6}\s")
MD_LINK_INLINE_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def slugify(heading: str) -> str:
    """标题 → GitHub 锚点 slug。三步顺序不可调换（见模块 docstring 的三条易错规则）。"""
    s = re.sub(r"^#+\s*", "", heading)
    s = MD_LINK_INLINE_RE.sub(r"\1", s)          # 1. 先折叠链接为其文字，再删标点
    s = s.lower()
    # CJK 经 str.isalnum() 判为 alnum，故中文标题得以保留。
    s = "".join(ch for ch in s if ch.isalnum() or ch.isspace() or ch in "_-")
    s = re.sub(r"\s", "-", s)                    # 2. 逐个替换，MUST NOT 折叠连续空格
    return re.sub(r"-+$", "", s)


_SLUG_CACHE: dict[Path, set[str]] = {}


def file_slugs(abs_path: Path) -> set[str]:
    """目标文件的全部标题 slug；重复者按 GitHub 规则追加 -1 / -2。跳过围栏代码块内的 `#`。"""
    cached = _SLUG_CACHE.get(abs_path)
    if cached is not None:
        return cached
    try:
        text = abs_path.read_text(encoding="utf-8")
    except Exception:
        text = ""
    slugs: set[str] = set()
    seen: dict[str, int] = {}
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not HEADING_RE.match(line):
            continue
        base = slugify(line)
        n = seen.get(base, 0)
        seen[base] = n + 1
        slugs.add(base if n == 0 else f"{base}-{n}")
    _SLUG_CACHE[abs_path] = slugs
    return slugs


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


def _link_visible_text(text: str) -> str:
    """围栏代码块整段剔除、行内代码段替换为空格——两处的 [text](url) 是示例而非链接。"""
    kept: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        kept.append(INLINE_CODE_RE.sub(" ", line))
    return "\n".join(kept)


def extract_links(md: Path) -> list[str]:
    try:
        text = (ROOT / md).read_text(encoding="utf-8")
    except Exception:
        return []
    return [m.group(2).strip() for m in LINK_RE.finditer(_link_visible_text(text))]


def resolve_target(src: Path, url: str) -> tuple[Path | None, str]:
    """→ (目标绝对路径, anchor)。外链与非文件协议返回 (None, "")。

    纯 `#anchor` 解析为**源文件自身**——同文件锚点一样会因标题改名而失效，
    不校验就是漏报。
    """
    if url.startswith(("http://", "https://", "mailto:", "tel:", "data:")):
        return None, ""
    if url.startswith("file://"):
        url = url[len("file://"):]
    path, _, anchor = url.partition("#")
    anchor = urllib.parse.unquote(anchor.split("?", 1)[0]) if anchor else ""
    path = path.split("?", 1)[0]
    if not path:
        return (ROOT / src).resolve(strict=False), anchor
    path = urllib.parse.unquote(path)
    if path.startswith("/"):
        target = ROOT / path.lstrip("/")
    else:
        target = (ROOT / src).parent / path
    try:
        return target.resolve(strict=False), anchor
    except Exception:
        return target, anchor


_DOCSITE_CACHE: dict[Path, bool] = {}


def _in_docsite(abs_path: Path) -> bool:
    """目标是否落在 docsite 子树内。静态站点自动生成锚点（ext-less 路由、插件注入的
    heading id），按源文件标题算 slug 会误报，故这些目标只校验文件存在性。"""
    if not SITE_AUTOSKIP:
        return False
    cur = abs_path.parent
    while True:
        cached = _DOCSITE_CACHE.get(cur)
        if cached is None:
            cached = _is_docsite(cur)
            _DOCSITE_CACHE[cur] = cached
        if cached:
            return True
        if cur == ROOT or cur.parent == cur:
            return False
        cur = cur.parent


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
_MD_PATH_INDEX: list[Path] | None = None


def _target_index() -> tuple[dict[str, list[Path]], list[Path]]:
    """全仓引用目标索引：(basename → 路径列表, 全部 `.md` 相对路径列表)；只建一次。

    与扫描源不同：`.agents` 从 SKIP_DIRS 里豁免——skill 内部树不参与外部审计（不作为
    扫描源），但它是合法的引用目标（如 CLAUDE.md 引 sdd references）。`.claude` 保持
    跳过：多为 `.agents` 的 symlink 镜像，纳入只会制造重复命中。
    """
    global _BASENAME_INDEX, _MD_PATH_INDEX
    if _BASENAME_INDEX is not None and _MD_PATH_INDEX is not None:
        return _BASENAME_INDEX, _MD_PATH_INDEX
    basename: dict[str, list[Path]] = {}
    md_paths: list[Path] = []
    skip = {d for d in SKIP_DIRS if d != ".agents"}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            rel = (Path(dirpath) / fn).relative_to(ROOT)
            basename.setdefault(fn, []).append(rel)
            if fn.endswith(".md"):
                md_paths.append(rel)
    _BASENAME_INDEX = basename
    _MD_PATH_INDEX = md_paths
    return _BASENAME_INDEX, _MD_PATH_INDEX


def _segments_match_tail(path_parts: tuple[str, ...], token_segments: tuple[str, ...]) -> bool:
    """token 路径段与目标相对路径的尾部段逐段一致（`a/b.md` 匹配 `docs/x/a/b.md`）。"""
    return len(path_parts) > len(token_segments) and path_parts[-len(token_segments):] == token_segments


def _suffix_resolve(token: str) -> bool:
    """末段对齐解析：命中**唯一**才视为可解析；命中多个 = 简写有歧义，留给人工判断。"""
    _, md_paths = _target_index()
    tseg = tuple(token.split("/"))
    matches = [p for p in md_paths if _segments_match_tail(p.parts, tseg)]
    return len(matches) == 1


def resolve_md_token(src: Path, token: str) -> bool:
    """反引号内 `.md` 文件名 / 路径引用是否存在。含路径分隔符时依次按仓库根 / 引用来源
    目录 / 末段对齐（唯一命中）三种方式解析；纯文件名时在全仓 basename 索引中查找。"""
    if "/" in token:
        for base in (ROOT, (ROOT / src).parent):
            try:
                if (base / token).resolve(strict=False).exists():
                    return True
            except Exception:
                continue
        return _suffix_resolve(token)
    return token in _target_index()[0]


def resolve_adr_token(num: str) -> bool:
    adr_dir = ROOT / ADR_DIR
    if not adr_dir.is_dir():
        return False
    prefix = f"{num}-"
    return any(p.name.startswith(prefix) for p in adr_dir.glob("*.md"))


_ALLOWLIST_LINE_RE = re.compile(r"^(?:CANDIDATE\s+)?(\S+)\s*→\s*`?([^`\s]+)`?$")


def _load_candidate_allowlist() -> set[tuple[str, str]]:
    """CANDIDATE 白名单：人工甄别后确认无需处理的 `(src, token)` 对，登记后不再重报。
    行格式与脚本输出一致（可直接粘贴 CANDIDATE 行）；`#` 开头为注释。"""
    raw = os.environ.get("DOC_GOV_CANDIDATE_ALLOWLIST", "").strip()
    p = Path(raw) if raw else ROOT / ".doc-gov-candidate-allowlist"
    if not p.is_absolute():
        p = ROOT / p
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    allowed: set[tuple[str, str]] = set()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _ALLOWLIST_LINE_RE.match(line)
        if m:
            allowed.add((m.group(1), m.group(2)))
    return allowed


def _stale_reason(src: str, token: str) -> str:
    """白名单条目未被消费的原因（供人工回删时参考）。"""
    src_path = ROOT / src
    if not src_path.exists():
        return "源文件已不存在"
    if resolve_md_token(Path(src), token):
        return "引用现已可解析（目标已落地），豁免多余"
    return "源文中已无此引用（已改写或改名）"


def self_test() -> int:
    """slug 规则写错的方向不是漏报就是一屏假阳性，两者都比没有 gate 更糟。

    下列用例对应真实犯过的错：折叠连续空格、漏 URL 解码、链接折叠顺序颠倒、
    CJK 被当作非 alnum 删掉。
    """
    import tempfile

    fails = 0

    def expect(cond: bool, msg: str) -> None:
        nonlocal fails
        if not cond:
            print(f"SELF-TEST FAIL: {msg}", file=sys.stderr)
            fails = 1

    # slug 规则逐条
    expect(slugify("## 真实章节 A") == "真实章节-a", "CJK 标题 slug 算错（CJK 未计入 alnum）")
    expect(slugify("## 5. SlaPolicy / ScheduleDefinition 参数目录")
           == "5-slapolicy--scheduledefinition-参数目录",
           "双连字符规则错（连续空格被折叠了）")
    expect(slugify("## 见 [x](y) 说明") == "见-x-说明", "markdown 链接未先折叠为其文字")
    expect(slugify("## 尾部标点。") == "尾部标点", "尾部标点未删或残留连字符")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "target.md").write_text(
            "# 标题一\n## 真实章节 A\n## 5. SlaPolicy / ScheduleDefinition 参数目录\n"
            "## 重名章节\n## 重名章节\n```\n## 代码块内的标题\n```\n",
            encoding="utf-8",
        )
        slugs = file_slugs(root / "target.md")
        expect("真实章节-a" in slugs, "未收集到普通标题 slug")
        expect("5-slapolicy--scheduledefinition-参数目录" in slugs, "未收集到双连字符 slug")
        expect("重名章节" in slugs and "重名章节-1" in slugs, "重名标题的 -N 后缀规则错")
        expect("代码块内的标题" not in slugs, "围栏代码块内的 # 被误当作标题")

    # 链接提取：围栏代码块 / 行内代码中的 [x](y) 是示例，MUST NOT 参与校验
    visible = _link_visible_text("[a](b.md)\n```text\n[c](d.md)\n```\n`[e](f.md)` 尾示例\n")
    expect("[a](b.md)" in visible, "正文链接被误剔除")
    expect("[c](d.md)" not in visible, "围栏代码块内的链接示例未被剔除")
    expect("[e](f.md)" not in visible, "行内代码中的链接示例未被剔除")

    # 末段对齐是纯函数，规则写错会把 stale 简写误判为可解析（漏报），钉住它。
    expect(_segments_match_tail(("docs", "specs", "x", "main.md"), ("x", "main.md")),
           "末段对齐应命中：尾部段逐段一致")
    expect(not _segments_match_tail(("docs", "specs", "hetu-x", "main.md"), ("x", "main.md")),
           "末段对齐不得跨段截配（hetu-x ≠ x）")
    expect(not _segments_match_tail(("x", "main.md"), ("x", "main.md")),
           "末段对齐要求目标路径更长（等长应已按仓根解析）")

    if fails:
        return 2
    print("OK: self-test 通过（CJK / 双连字符 / 链接折叠 / 重名 -N / 代码块跳过（标题与链接）/ 末段对齐 均正确）")
    return 0


USAGE = """\
Usage: python3 check-links.py            (run from repo root; no positional args)
       python3 check-links.py --self-test

Validate relative Markdown links, `#anchor` section anchors, backtick `ADR-NNNN`
refs, and backtick `*.md` refs across the repository.
Configuration is via DOC_GOV_* environment variables only (see module docstring):
  DOC_GOV_ROOT, DOC_GOV_INCLUDE, DOC_GOV_INCLUDE_EXTRA,
  DOC_GOV_SKIP_DIRS, DOC_GOV_SKIP_DIRS_EXTRA,
  DOC_GOV_SITE_CONFIGS[_EXTRA], DOC_GOV_NO_SITE_AUTOSKIP, DOC_GOV_VERBOSE,
  DOC_GOV_ADR_DIR, DOC_GOV_HISTORICAL_PREFIXES[_EXTRA], DOC_GOV_NO_ANCHOR_CHECK,
  DOC_GOV_CANDIDATE_ALLOWLIST

Output:
  BROKEN     <file>  →  <link>   (markdown links + anchors + ADR refs; hard failure)
  CANDIDATE  <file>  →  <token>  (backtick *.md refs; informational only)
  STALE      <file>  →  <token>  (allowlist entries not consumed this run; prune them)
Exit codes:  0 = no BROKEN (CANDIDATEs / STALE may remain) · 1 = BROKEN found
             2 = usage error or self-test failure
"""


def main() -> int:
    args = sys.argv[1:]
    if args:
        if args[0] in ("-h", "--help"):
            print(USAGE)
            return 0
        if args[0] == "--self-test":
            return self_test()
        print(f"Error: unexpected argument {args[0]!r} — this script takes no "
              "positional arguments (configure via DOC_GOV_* env vars).\n",
              file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2

    # 规则自检先行：slug 规则错了，本次结论就不可信。MUST NOT 降级成警告后继续。
    if ANCHOR_CHECK and self_test() != 0:
        print("ABORT: gate 自检未通过，本次结果不可信——先修 slugify 规则。", file=sys.stderr)
        return 2

    broken: list[tuple[str, str]] = []
    candidates: list[tuple[str, str]] = []
    allowlist = _load_candidate_allowlist()
    consumed: set[tuple[str, str]] = set()
    suppressed = 0
    files = list(iter_md_files())
    for md in files:
        for url in extract_links(md):
            target, anchor = resolve_target(md, url)
            if target is None:
                continue
            if not target.exists():
                broken.append((str(md), url))
                continue
            # 历史留档跳过锚点校验：其中的锚点指向的是**写就当时**的目标文档结构，
            # 目标标题后来改名并不使这份留档出错——修它等于篡改历史快照，不修又会
            # 永久红着。文件存在性仍照常校验（那是真实的可达性）。
            if (ANCHOR_CHECK and anchor and target.suffix == ".md"
                    and target.is_file() and not _in_docsite(target)
                    and not _is_historical(md)
                    and anchor not in file_slugs(target)):
                broken.append((str(md), url))
        if _is_historical(md):
            continue
        for num in extract_backtick_adr_refs(md):
            if not resolve_adr_token(num):
                broken.append((str(md), f"`ADR-{num}`"))
        for token in extract_backtick_md_refs(md):
            if resolve_md_token(md, token):
                continue
            if (str(md), token) in allowlist:
                consumed.add((str(md), token))
                suppressed += 1
                continue
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
              f"前瞻 TODO / 举例性文字；甄别后确认无需处理的请登记进 CANDIDATE 白名单）：")
        for src, token in candidates:
            print(f"CANDIDATE  {src}  →  {token}")
        print(f"Total candidates: {len(candidates)}")
    if suppressed:
        print(f"（另有 {suppressed} 条候选经白名单豁免，不再重报）")

    # 白名单防腐：一轮扫描下来未被消费的条目 = 引用已消失或豁免已多余，报 STALE 提醒
    # 回删（非阻断——过期条目不产生错误结论，只是噪声，但留着会让白名单失去可信度）。
    stale = sorted(allowlist - consumed)
    if stale:
        print(f"\n白名单过时条目（不影响退出码，请回删 .doc-gov-candidate-allowlist 对应行）：")
        for src, token in stale:
            print(f"STALE  {src}  →  `{token}`  （{_stale_reason(src, token)}）")
        print(f"Total stale: {len(stale)}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
