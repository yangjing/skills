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
  sync.local.csv   两列或三列：name,src[,mode]  （src 支持 ~ 与 $ENV 展开）
    mode=sync（默认，可省略）  参与同步
    mode=watch                仅监控漂移（--check 提示差异，不同步、不阻断退出码）
  同一 skill 可登记多行（多个仓库各有一份副本时）：
    - 多个 sync 行 → 同步 / 检测前按「源的最后迭代时间」择新：git 仓库取该目录的
      最后提交时间（未提交的工作区改动不计，重 clone / checkout 不污染结果），
      非 git 目录回退树内最新 mtime；并列取 CSV 中靠前的一行
    - 落选 sync 行与 watch 行：--check 只提示与本仓库的差异，不阻断退出码
配套样本见 sync.local.example.csv。

【四种模式】
  uv run scripts/sync.py                 # 同步配置中全部 skill（默认）
  uv run scripts/sync.py fusions ebook   # 仅同步配置中指定的 skill（按 name 过滤，可多个）
  uv run scripts/sync.py --src <path>    # 临时同步未登记的源（可多次：--src a --src b）
  uv run scripts/sync.py --check         # 仅检测漂移，不改文件（CI 友好；当前同步源漂移返回 1，
                                         #   watch / 落选源差异只提示不阻断）
  uv run scripts/sync.py --list          # 列出配置中的映射（含 mode）

  【同步规则】（迁移自旧 sync.sh，保证等价）
  - 复制源到 skills/<name>/，已存在则覆盖（dirs_exist_ok=True）
  - 仅在 skill 根目录排除 README.md：根 README 是本仓库人工为分发写的，源里没有，
    不覆盖；源内子目录的 README.md 属于 skill 本体，照常同步
  - 排除 __pycache__（任意层级）：Python 运行缓存，不应进分发快照
  - 不删本仓库独有文件（无 --delete 语义）
  - 幂等：内容无变化时不产生改动，git diff 干净
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

# ─── 定位仓库根目录（脚本无论从哪调用都能定位）──────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
CONFIG_PATH = REPO_ROOT / "sync.local.csv"
EXAMPLE_PATH = REPO_ROOT / "sync.local.example.csv"

# 跳过规则：README.md 仅在 skill 根目录跳过——根 README 是本仓库人工写的分发说明
# （源里没有）；子目录的 README.md 属于 skill 本体（如 sdd/stacks/README.md），必须同步。
# __pycache__ 是 Python 运行缓存，任意层级都跳过。
ROOT_EXCLUDE_NAMES = {"README.md"}
EXCLUDE_NAMES = {"__pycache__"}

# CSV 第三列 mode 的合法取值：sync 参与同步；watch 仅监控漂移。
MODES = ("sync", "watch")


class Entry(NamedTuple):
    """sync.local.csv 的一行。"""
    name: str
    src: str   # 已展开 ~ / $ENV 的源路径
    mode: str  # "sync" | "watch"

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


def load_config() -> list[Entry]:
    """读取 sync.local.csv，返回 Entry 列表。

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

    rows: list[Entry] = []
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
            # 跳过表头（首数据行若形如 name,src 视为表头，第三列表头可选）
            if not header_seen:
                if [c.strip().lower() for c in row[:2]] == ["name", "src"]:
                    header_seen = True
                    continue
                header_seen = True
            if len(row) < 2:
                err(f"配置行格式错误（应为 name,src[,mode]）: {row}")
                continue
            name = row[0].strip()
            src = expand_src(row[1].strip())
            mode = row[2].strip().lower() if len(row) >= 3 else ""
            if mode and mode not in MODES:
                err(f"未知 mode（应为 sync / watch，可省略）: {row}")
                continue
            if name:
                rows.append(Entry(name, src, mode or "sync"))
    return rows


# ─── 复制 / 漂移检测的核心 ─────────────────────────────────────────
def should_skip(name: str, at_root: bool = False) -> bool:
    """at_root=True 表示该名字位于 skill 根目录（触发根级 README.md 排除）。"""
    return name in EXCLUDE_NAMES or (at_root and name in ROOT_EXCLUDE_NAMES)


def copy_skill(src: Path, dst: Path) -> None:
    """把 src 复制到 dst（覆盖），根目录跳过 README.md、任意层级跳过 __pycache__。

    用 copytree(dirs_exist_ok=True) + 自定义 ignore 实现等价于
    rsync -a --exclude /README.md --exclude __pycache__。
    """
    dst.mkdir(parents=True, exist_ok=True)

    def _ignore(dir_visited: str, names: list[str]) -> list[str]:
        at_root = Path(dir_visited) == src
        return [n for n in names if should_skip(n, at_root)]

    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=_ignore)


def dirs_equal(a: Path, b: Path) -> bool:
    """比较两目录树内容是否一致（排除 README.md / __pycache__）。"""
    def _walk(p: Path) -> dict[str, Path]:
        out: dict[str, Path] = {}
        for root, dirs, files in os.walk(p):
            at_root = Path(root) == p
            dirs[:] = [d for d in dirs if not should_skip(d)]
            for f in files:
                if should_skip(f, at_root):
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
            at_root = Path(root) == p
            dirs[:] = [d for d in dirs if not should_skip(d)]
            for f in files:
                if should_skip(f, at_root):
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


# ─── 多源语义：同名多行的分组与择新 ────────────────────────────────
def group_by_name(entries: list[Entry]) -> list[tuple[str, list[Entry]]]:
    """按 name 聚合（保持首次出现顺序）。"""
    groups: dict[str, list[Entry]] = {}
    for e in entries:
        groups.setdefault(e.name, []).append(e)
    return list(groups.items())


def source_last_modified(src: Path) -> tuple[float, str]:
    """取源的「最后迭代时间」，用于同名多 sync 行择新。

    git 仓库取该目录的最后提交时间（未提交的工作区改动不计，重 clone /
    重 checkout 也不会污染结果）；非 git 目录回退树内最新 mtime。
    返回 (epoch 秒, 依据说明)；源缺失返回 (0.0, "源缺失")。
    """
    if not src.is_dir():
        return 0.0, "源缺失"
    try:
        out = subprocess.run(
            ["git", "-C", str(src), "log", "-1", "--format=%cI", "--", "."],
            capture_output=True, text=True, timeout=10, check=True,
        )
        iso = out.stdout.strip()
        if iso:
            return datetime.fromisoformat(iso).timestamp(), f"git 提交 {iso}"
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    newest = 0.0
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if not should_skip(d)]
        for f in files:
            if should_skip(f):
                continue
            try:
                newest = max(newest, (Path(root) / f).stat().st_mtime)
            except OSError:
                continue
    return newest, f"mtime {datetime.fromtimestamp(newest).isoformat(timespec='seconds')}"


def pick_sync_source(name: str, entries: list[Entry]) -> Entry | None:
    """确定一个 skill 的当前同步源。

    无 sync 行返回 None；唯一 sync 行直接用；多个 sync 行按
    source_last_modified 择新（并列取 CSV 中靠前的一行），并打印择新依据。
    """
    sync_rows = [e for e in entries if e.mode == "sync"]
    if not sync_rows:
        return None
    if len(sync_rows) == 1:
        return sync_rows[0]
    stamped = [(source_last_modified(Path(e.src)), e) for e in sync_rows]
    best = 0
    for i in range(1, len(stamped)):
        if stamped[i][0][0] > stamped[best][0][0]:
            best = i
    log(f"{name}: {len(sync_rows)} 个同步源，择新（git 提交时间优先，回退 mtime）:")
    for i, ((_, human), e) in enumerate(stamped):
        if i == best:
            print(f"    {human}  {e.src}  {C_GREEN}← 选中（最新）{C_RESET}")
        else:
            print(f"    {C_DIM}{human}  {e.src}{C_RESET}")
    return stamped[best][1]


def hint_src_missing(src: Path) -> None:
    """源目录缺失时打印定位提示。"""
    err(f"源目录不存在: {src}")
    print(f"    {C_DIM}该 skill 的源在另一业务仓库。请核对 sync.local.csv 中该行的 src 路径，{C_RESET}",
          file=sys.stderr)
    print(f"    {C_DIM}src 支持 ~ 与 $ENV 展开（如 ~/hylxos/.agents/skills/fusions）。{C_RESET}",
          file=sys.stderr)


# ─── 各模式实现 ────────────────────────────────────────────────────
def mode_list(config: list[Entry]) -> int:
    if not config:
        warn("配置为空（或文件缺失）。")
        return 0
    print(f"{C_DIM}{'SKILL':<18}  {'MODE':<6}  SOURCE{C_RESET}")
    print("-" * 72)
    for e in config:
        print(f"{e.name:<18}  {e.mode:<6}  {e.src}")
    return 0


def select_targets(config: list[Entry], names: list[str]) -> list[Entry]:
    """按 name 过滤配置，对未知 name 报错。"""
    out: list[Entry] = []
    for want in names:
        match = [e for e in config if e.name == want]
        if not match:
            err(f"未知 skill: {want}（配置中未登记；用 --list 查看，或用 --src <path> 临时同步）")
            sys.exit(2)
        out.extend(match)
    return out


def run_check(targets: list[Entry]) -> int:
    log("检测漂移（源 → 本仓库，排除根 README.md / __pycache__）…")
    drifted = False
    for name, entries in group_by_name(targets):
        chosen = pick_sync_source(name, entries)  # 多个 sync 行时在此打印择新依据
        if chosen is None:
            warn(f"{name}: 未配置 sync 源，仅监控（不阻断）")
        # 非当前源（watch 行 + 落选 sync 行）：只提示差异，不阻断退出码
        for e in entries:
            if e is chosen:
                continue
            src, dst = Path(e.src), SKILLS_DIR / e.name
            label = "监控源" if e.mode == "watch" else "备选源"
            if not src.is_dir():
                print(f"  {C_YELLOW}!{C_RESET} {name}: {label}不存在（仅提示）: {src}")
            elif not dst.is_dir():
                print(f"  {C_YELLOW}!{C_RESET} {name}: {label}对应目录缺失（仅提示）: {dst}")
            elif dirs_equal(src, dst):
                print(f"  {C_DIM}· {name}: {label}一致: {src}{C_RESET}")
            else:
                print(f"  {C_YELLOW}!{C_RESET} {name}: {label}与本仓库不同（仅提示，不阻断）: {src}")
        if chosen is None:
            continue
        src, dst = Path(chosen.src), SKILLS_DIR / name
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
    ok("无漂移（当前同步源全部一致）；监控 / 备选源差异仅提示，见上。")
    return 0


def run_sync(targets: list[Entry]) -> int:
    groups = group_by_name(targets)
    log(f"同步 {len(groups)} 个 skill 到 {SKILLS_DIR}")
    had_error = False
    for name, entries in groups:
        for e in entries:
            if e.mode == "watch":
                print(f"  {C_DIM}· {name}: 监控源不同步: {e.src}{C_RESET}")
        chosen = pick_sync_source(name, entries)
        if chosen is None:
            warn(f"{name}: 无 sync 源，跳过")
            continue
        src, dst = Path(chosen.src), SKILLS_DIR / name
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
                        help="只检测漂移，不改文件（当前同步源漂移返回 1；watch / 备选源只提示）")
    parser.add_argument("--list", action="store_true", help="列出配置中的映射（含 mode）")
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
