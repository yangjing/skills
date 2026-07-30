#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
sync.py — 把源仓库中的 skill 同步到本仓库（分发快照）。

本仓库是 skill 的「分发快照」，真相源在各业务仓库。源 skill 在业务仓库里迭代后，
跑本脚本把最新内容覆盖到本仓库 skills/ 下。

【映射表】不在代码里写死，由本地配置文件管理（每人各异，不入 git）：
  sync.local.csv   两列：name,src  （src 支持 ~ 与 $ENV 展开）
配套样本见 sync.local.example.csv。

【四种模式】
  uv run scripts/sync.py                 # 同步配置中全部 skill（默认）
  uv run scripts/sync.py fusions ebook   # 仅同步配置中指定 skill（按 name 过滤，可多个）
  uv run scripts/sync.py --src <path>    # 临时同步未登记的源（可多次：--src a --src b）
  uv run scripts/sync.py --check         # 仅检测漂移，不改文件（CI 友好；漂移返回 1）
  uv run scripts/sync.py --list          # 列出配置中的映射

【同步规则】（迁移自旧 sync.sh，保证等价）
  - 复制源到 skills/<name>/，已存在则覆盖（dirs_exist_ok=True）
  - 排除 README.md：本仓库的每个 skill README.md 是人工为分发写的，源里没有，不覆盖
  - 排除 __pycache__：Python 运行缓存，不应进分发快照
  - 不删本仓库独有文件（无 --delete 语义）
  - 幂等：内容无变化时不产生改动，git diff 干净
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
from pathlib import Path

# ─── 定位仓库根目录（脚本无论从哪调用都能定位）──────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
CONFIG_PATH = REPO_ROOT / "sync.local.csv"
EXAMPLE_PATH = REPO_ROOT / "sync.local.example.csv"

# 复制时跳过这些名字：README.md 是本仓库人工写的分发说明（源里没有）；
# __pycache__ 是 Python 运行缓存。
EXCLUDE_NAMES = {"README.md", "__pycache__"}

# ─── 终端颜色 ──────────────────────────────────────────────────────
if sys.stdout.isatty():
    C_GREEN = "\033[32m"; C_YELLOW = "\033[33m"; C_RED = "\033[31m"
    C_CYAN = "\033[36m"; C_DIM = "\033[2m"; C_RESET = "\033[0m"
else:
    C_GREEN = C_YELLOW = C_RED = C_CYAN = C_DIM = C_RESET = ""


def log(msg: str) -> None:
    print(f"{C_CYAN}▸{C_RESET} {msg}")


def ok(msg: str) -> None:
    print(f"  {C_GREEN}✓{C_RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {C_YELLOW}!{C_RESET} {msg}")


def err(msg: str) -> None:
    print(f"  {C_RED}✗{C_RESET} {msg}", file=sys.stderr)


# ─── 配置加载 ──────────────────────────────────────────────────────
def expand_src(raw: str) -> str:
    """展开 src 中的 ~ 与环境变量，返回绝对路径字符串。"""
    return os.path.expanduser(os.path.expandvars(raw))


def load_config() -> list[tuple[str, str]]:
    """读取 sync.local.csv，返回 [(name, expanded_src), ...]。

    缺文件或空配置时返回 [] 并在 stderr 给出指引（不抛异常，调用方按需处理）。
    """
    if not CONFIG_PATH.exists():
        err(f"配置文件不存在: {CONFIG_PATH}")
        print(f"    {C_DIM}skill 映射每人各异，不入 git。请从样本复制并改成本机路径：{C_RESET}",
              file=sys.stderr)
        print(f"    {C_DIM}cp {EXAMPLE_PATH.name} {CONFIG_PATH.name}  # 然后编辑里面的 src 路径{C_RESET}",
              file=sys.stderr)
        print(f"    {C_DIM}或用 --src <path> 临时同步一个未登记的源。{C_RESET}", file=sys.stderr)
        return []

    rows: list[tuple[str, str]] = []
    with CONFIG_PATH.open(newline="", encoding="utf-8") as fh:
        # 注意：手动按行读取而非 csv.reader，便于在 csv 解析前跳过注释行与空行。
        # csv.reader 会在遇到含逗号的字段时切分，注释里的逗号会干扰判断。
        header_seen = False
        for line in fh:
            stripped = line.strip()
            # 跳过空行与注释行（# 须在行首，避免误伤含 # 的路径）
            if not stripped or stripped.startswith("#"):
                continue
            row = next(csv.reader([line]))
            # 跳过表头（首数据行若形如 name,src 视为表头）
            if not header_seen:
                if [c.strip().lower() for c in row[:2]] == ["name", "src"]:
                    header_seen = True
                    continue
                header_seen = True
            if len(row) < 2:
                err(f"配置行格式错误（应为 name,src 两列）: {row}")
                continue
            name = row[0].strip()
            src = expand_src(row[1].strip())
            if name:
                rows.append((name, src))
    return rows


# ─── 复制 / 漂移检测的核心 ─────────────────────────────────────────
def should_skip(name: str) -> bool:
    return name in EXCLUDE_NAMES


def copy_skill(src: Path, dst: Path) -> None:
    """把 src 复制到 dst（覆盖），跳过 README.md 与 __pycache__。

    用 copytree(dirs_exist_ok=True) + 自定义 ignore 实现等价于
    rsync -a --exclude README.md --exclude __pycache__。
    """
    dst.mkdir(parents=True, exist_ok=True)

    def _ignore(_dir: Path, names: list[str]) -> list[str]:
        return [n for n in names if should_skip(n)]

    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=_ignore)


def dirs_equal(a: Path, b: Path) -> bool:
    """比较两目录树内容是否一致（排除 README.md / __pycache__）。"""
    def _walk(p: Path) -> dict[str, Path]:
        out: dict[str, Path] = {}
        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if not should_skip(d)]
            for f in files:
                if should_skip(f):
                    continue
                fp = Path(root) / f
                out[str(fp.relative_to(p))] = fp
        return out

    ma, mb = _walk(a), _walk(b)
    if set(ma) != set(mb):
        return False
    for rel, fa in ma.items():
        if fa.read_bytes() != mb[rel].read_bytes():
            return False
    return True


def diff_listing(a: Path, b: Path) -> list[str]:
    """列出两目录的差异条目（排除 README.md / __pycache__），供漂移报告展示。"""
    def _walk(p: Path) -> dict[str, Path]:
        out: dict[str, Path] = {}
        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if not should_skip(d)]
            for f in files:
                if should_skip(f):
                    continue
                fp = Path(root) / f
                out[str(fp.relative_to(p))] = fp
        return out

    ma, mb = _walk(a), _walk(b)
    lines: list[str] = []
    for rel in sorted(set(ma) | set(mb)):
        if rel not in mb:
            lines.append(f"仅在源:     {a / rel}")
        elif rel not in ma:
            lines.append(f"仅在仓库:   {b / rel}")
        elif ma[rel].read_bytes() != mb[rel].read_bytes():
            lines.append(f"内容不同:   {b / rel}")
    return lines


def hint_src_missing(src: Path) -> None:
    """源目录缺失时打印定位提示。"""
    err(f"源目录不存在: {src}")
    print(f"    {C_DIM}该 skill 的源在另一业务仓库。请核对 sync.local.csv 中该行的 src 路径，{C_RESET}",
          file=sys.stderr)
    print(f"    {C_DIM}src 支持 ~ 与 $ENV 展开（如 ~/hylxos/.agents/skills/fusions）。{C_RESET}",
          file=sys.stderr)


# ─── 各模式实现 ────────────────────────────────────────────────────
def mode_list(config: list[tuple[str, str]]) -> int:
    if not config:
        warn("配置为空（或文件缺失）。")
        return 0
    print(f"{C_DIM}{'SKILL':<18}  SOURCE{C_RESET}")
    print("-" * 60)
    for name, src in config:
        print(f"{name:<18}  {src}")
    return 0


def select_targets(config: list[tuple[str, str]], names: list[str]) -> list[tuple[str, str]]:
    """按 name 过滤配置，对未知 name 报错。"""
    known = {n for n, _ in config}
    out: list[tuple[str, str]] = []
    for want in names:
        match = [(n, s) for n, s in config if n == want]
        if not match:
            err(f"未知 skill: {want}（配置中未登记；用 --list 查看，或用 --src <path> 临时同步）")
            sys.exit(2)
        out.extend(match)
    return out


def run_check(targets: list[tuple[str, str]]) -> int:
    log("检测漂移（源 → 本仓库，排除 README.md / __pycache__）…")
    drifted = False
    for name, src_raw in targets:
        src = Path(src_raw)
        dst = SKILLS_DIR / name
        if not src.is_dir():
            hint_src_missing(src)
            drifted = True
            continue
        if not dst.is_dir():
            err(f"本仓库缺目录: {dst}")
            drifted = True
            continue
        if dirs_equal(src, dst):
            ok(f"{name}: 一致")
        else:
            warn(f"{name}: 已漂移")
            for line in diff_listing(src, dst):
                print(f"      {line}")
            drifted = True
    print()
    if drifted:
        err("存在漂移，跑 uv run scripts/sync.py 同步。")
        return 1
    ok("无漂移，所有 skill 与源一致。")
    return 0


def run_sync(targets: list[tuple[str, str]]) -> int:
    log(f"同步 {len(targets)} 个 skill 到 {SKILLS_DIR}")
    had_error = False
    for name, src_raw in targets:
        src = Path(src_raw)
        dst = SKILLS_DIR / name
        if not src.is_dir():
            hint_src_missing(src)
            had_error = True
            continue
        copy_skill(src, dst)
        ok(f"{name}  ←  {src}")
    print()
    if had_error:
        err("部分 skill 同步失败，见上。")
        return 4
    ok("同步完成。下一步：")
    print(f"  {C_DIM}1.{C_RESET} 检查改动: {C_DIM}git status{C_RESET}")
    print(f"  {C_DIM}2.{C_RESET} 如源 skill 内容有变，相应更新 "
          f"{C_DIM}skills/<name>/README.md{C_RESET}")
    print(f"  {C_DIM}3.{C_RESET} 提交推送: {C_DIM}git add -A && git commit{C_RESET}"
          "（skills.sh 会在用户下次安装时自动取到新版）")
    return 0


def run_src(sources: list[str], check: bool) -> int:
    """临时同步一个或多个未登记的源，dest 名取自源目录名。

    逐个处理，收集登记建议统一打印；任一失败则退出码非 0。
    """
    suggestions: list[str] = []
    had_error = False
    for src_raw in sources:
        src = Path(expand_src(src_raw))
        if not src.is_dir():
            hint_src_missing(src)
            had_error = True
            continue
        name = src.name
        dst = SKILLS_DIR / name
        log(f"临时{'检测' if check else '同步'}（未登记源）: {name}  ←  {src}")
        if check:
            if not dst.is_dir():
                err(f"本仓库缺目录: {dst}")
                had_error = True
                continue
            if dirs_equal(src, dst):
                ok(f"{name}: 一致")
            else:
                warn(f"{name}: 已漂移")
                for line in diff_listing(src, dst):
                    print(f"      {line}")
                had_error = True
        else:
            copy_skill(src, dst)
            ok(f"{name}  ←  {src}")
        suggestions.append(f"{name},{src_raw}")

    print()
    if had_error:
        err("部分源处理失败，见上。")
        return 4
    if check:
        ok("无漂移。")
    else:
        ok(f"同步完成 {len(suggestions)} 个。这些 skill 未在 sync.local.csv 登记，"
            "如需长期同步建议各补一行：")
        for s in suggestions:
            print(f"  {C_DIM}{s}{C_RESET}")
    return 0


# ─── 入口 ──────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sync.py",
        description="把源仓库中的 skill 同步到本仓库（分发快照）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  uv run scripts/sync.py                 # 同步配置中全部 skill
  uv run scripts/sync.py fusions ebook   # 仅同步配置中指定 skill
  uv run scripts/sync.py --src ~/foo/.agents/skills/bar  # 临时同步未登记源（可多次）
  uv run scripts/sync.py --check         # 漂移检测（漂移返回 1，CI 友好）
  uv run scripts/sync.py --list          # 列出配置映射
""",
    )
    parser.add_argument("names", nargs="*", help="仅同步配置中指定的 skill（按 name 过滤）")
    parser.add_argument("--src", metavar="PATH", action="append", default=None,
                        help="临时同步一个未登记的源路径（dest 名取自源目录名）；可多次指定")
    parser.add_argument("--check", action="store_true",
                        help="只检测漂移，不改文件（漂移返回 1）")
    parser.add_argument("--list", action="store_true", help="列出配置中的映射")
    args = parser.parse_args(argv)

    if args.list:
        return mode_list(load_config())

    if args.src:
        return run_src(args.src, args.check)

    config = load_config()
    if not config:
        return 3  # 配置缺失已在 load_config 内给出指引

    targets = select_targets(config, args.names) if args.names else config
    if not targets:
        warn("没有可处理的 skill。")
        return 0

    return run_check(targets) if args.check else run_sync(targets)


if __name__ == "__main__":
    sys.exit(main())
