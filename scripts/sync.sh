#!/usr/bin/env bash
# sync.sh — 把源仓库中的 skill 同步到本仓库（分发快照）。
#
# 本仓库是 skill 的「分发快照」，真相源在各业务仓库（~/hylxos、~/projects/books 等）。
# 源 skill 在业务仓库里迭代后，跑本脚本把最新内容覆盖到本仓库 skills/ 下。
#
# 映射表（skill 名 → 源绝对路径）集中在下方 SKILL_SOURCES 数组，新增/移除 skill 只改这里。
#
# 用法：
#   scripts/sync.sh               # 同步全部 skill（rsync 覆盖，保留 my-skills 独有的 README.md）
#   scripts/sync.sh --check       # 只检测漂移，不改文件（CI 友好；有漂移返回 1）
#   scripts/sync.sh axum-tower    # 只同步指定 skill（可多个：scripts/sync.sh axum-tower fusions）
#   scripts/sync.sh --list        # 列出映射表
#
# 设计要点：
#   - rsync 时 --exclude README.md：本仓库的每个 skill README.md 是人工为分发写的，
#     源目录没有；同步只覆盖源里有的内容，不动 README.md。
#   - 不删本仓库独有文件（如 README.md）：rsync 默认不加 --delete。
#   - 幂等：内容无变化时 rsync 不产生改动，git diff 干净。

set -euo pipefail

# ─── 仓库根目录（脚本无论从哪调用都能定位）──────────────────────────
# 兼容 bash（BASH_SOURCE）和 zsh（$0）；显式 bash 执行时走 BASH_SOURCE。
_SELF="${BASH_SOURCE[0]:-$0}"
REPO_ROOT="$(cd -- "$(dirname -- "$_SELF")/.." && pwd)"
SKILLS_DIR="$REPO_ROOT/skills"

# ─── 映射表：skill 名 → 源绝对路径（新增/移除 skill 只改这里）─────────
# 用 "name|source" 字符串数组承载映射，兼容 macOS 自带 bash 3.2（不支持关联数组）
# 和 zsh。键名含 '-' 在 bash 3.2 的 declare -A 下会触发算术展开报错，故避开。
SKILL_SOURCES=(
  "ebook-ai-notes|/Users/yangjing/projects/books/.agents/skills/ebook-ai-notes"
  "axum-tower|/Users/yangjing/hylxos/.agents/skills/axum-tower"
  "committing|/Users/yangjing/hylxos/.agents/skills/committing"
  "fusions|/Users/yangjing/hylxos/.agents/skills/fusions"
  "doc-governance|/Users/yangjing/hylxos/.agents/skills/doc-governance"
)

# 取某 skill 的源路径：source_of <name>；找到打印路径并返回 0，否则返回 1。
source_of() {
  local key="$1" entry
  for entry in "${SKILL_SOURCES[@]}"; do
    if [[ "${entry%%|*}" == "$key" ]]; then
      echo "${entry#*|}"
      return 0
    fi
  done
  return 1
}

# 列出所有 skill 名（已排序）。
all_names() {
  local entry
  for entry in "${SKILL_SOURCES[@]}"; do echo "${entry%%|*}"; done | sort
}

# ─── 颜色输出 ────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'
  C_CYAN=$'\033[36m'; C_DIM=$'\033[2m'; C_RESET=$'\033[0m'
else
  C_GREEN=""; C_YELLOW=""; C_RED=""; C_CYAN=""; C_DIM=""; C_RESET=""
fi

log()   { printf "${C_CYAN}▸${C_RESET} %s\n" "$*"; }
ok()    { printf "  ${C_GREEN}✓${C_RESET} %s\n" "$*"; }
warn()  { printf "  ${C_YELLOW}!${C_RESET} %s\n" "$*"; }
err()   { printf "  ${C_RED}✗${C_RESET} %s\n" "$*" >&2; }

# ─── 参数解析 ────────────────────────────────────────────────────
MODE="sync"          # sync | check | list
SELECTED=()          # 指定 skill 名，空表示全部

for arg in "$@"; do
  case "$arg" in
    --check) MODE="check" ;;
    --list)  MODE="list" ;;
    -h|--help)
      sed -n '2,20p' "$_SELF"
      exit 0 ;;
    -*)
      err "未知选项: $arg (用 -h 查看帮助)"; exit 2 ;;
    *)
      SELECTED+=("$arg") ;;
  esac
done

# ─── --list：打印映射表 ──────────────────────────────────────────
if [[ "$MODE" == "list" ]]; then
  printf "%s%-18s  %s%s\n" "$C_DIM" "SKILL" "SOURCE" "$C_RESET"
  printf -- "------------------------------------------------------------\n"
  for name in $(all_names); do
    printf "%-18s  %s\n" "$name" "$(source_of "$name")"
  done
  exit 0
fi

# ─── 校验选中的 skill 名合法 ─────────────────────────────────────
targets=()
if [[ ${#SELECTED[@]} -gt 0 ]]; then
  for name in "${SELECTED[@]}"; do
    if ! source_of "$name" >/dev/null; then
      err "未知 skill: $name (用 scripts/sync.sh --list 查看可选项)"
      exit 2
    fi
    targets+=("$name")
  done
else
  targets=($(all_names))
fi

command -v rsync >/dev/null 2>&1 || { err "需要 rsync，请先安装：brew install rsync"; exit 3; }

# ─── 漂移检测（--check）：源 vs 本仓库 diff，不改文件 ──────────────
if [[ "$MODE" == "check" ]]; then
  log "检测漂移（源 → 本仓库，排除 README.md）…"
  drifted=0
  for name in "${targets[@]}"; do
    src="$(source_of "$name")"
    dst="$SKILLS_DIR/$name"
    if [[ ! -d "$src" ]]; then err "源目录不存在: $src"; drifted=1; continue; fi
    if [[ ! -d "$dst" ]]; then err "本仓库缺目录: $dst"; drifted=1; continue; fi
    # -r 递归；排除 README.md（本仓库独有）；有差异则输出
    diffs=$(diff -rq --exclude="README.md" "$src" "$dst" 2>/dev/null || true)
    if [[ -z "$diffs" ]]; then
      ok "$name: 一致"
    else
      warn "$name: 已漂移"
      printf "%s\n" "$diffs" | sed 's/^/      /'
      drifted=1
    fi
  done
  echo ""
  if [[ $drifted -eq 0 ]]; then
    ok "无漂移，所有 skill 与源一致。"
  else
    err "存在漂移，跑 scripts/sync.sh 同步。"
    exit 1
  fi
  exit 0
fi

# ─── 同步（默认）：rsync 覆盖，保留 README.md ─────────────────────
log "同步 ${#targets[@]} 个 skill 到 $SKILLS_DIR"
for name in "${targets[@]}"; do
  src="$(source_of "$name")"
  dst="$SKILLS_DIR/$name"
  if [[ ! -d "$src" ]]; then err "源目录不存在: $src"; exit 4; fi
  mkdir -p "$dst"
  # -a 归档（递归+保留属性）；--exclude README.md 不覆盖本仓库人工写的分发 README
  rsync -a --exclude="README.md" "$src/" "$dst/"
  ok "$name  ←  $src"
done

echo ""
ok "同步完成。下一步："
printf "  %s1.%s 检查改动: %sgit status%s\n" "$C_DIM" "$C_RESET" "$C_DIM" "$C_RESET"
printf "  %s2.%s 如源 skill 内容有变，相应更新 %sskills/%s<name>/README.md%s\n" "$C_DIM" "$C_RESET" "$C_DIM" "$C_RESET" "$C_RESET"
printf "  %s3.%s 提交推送: %sgit add -A && git commit%s（skills.sh 会在用户下次安装时自动取到新版）\n" "$C_DIM" "$C_RESET" "$C_DIM" "$C_RESET"
