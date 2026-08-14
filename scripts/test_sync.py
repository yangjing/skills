#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""sync.py 的功能自测（stdlib unittest，零依赖）。

跑法：uv run scripts/test_sync.py   （或 python3 scripts/test_sync.py）

覆盖：
  - sync.local.csv 解析（两列默认 sync / 第三列 mode / 非法 mode 跳行 / 表头兼容）
  - 复制排除语义（根 README.md 排除、子目录 README.md 同步、__pycache__ 排除、幂等）
  - 多源择新（git 最后提交时间优先、行序无关、并列取靠前行、mtime 回退、watch 不参与）
  - run_sync / run_check 的多源语义（择新复制、watch 不同步、watch 漂移不阻断退出码）
"""
from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync  # noqa: E402

GIT = shutil.which("git")

OLD_DATE = "2026-08-08T12:00:00+08:00"
NEW_DATE = "2026-08-09T12:00:00+08:00"


def make_git_repo(path: Path, files: dict[str, str], commit_date: str) -> Path:
    """建一个 git 仓库并做一次提交，提交时间固定为 commit_date（ISO 8601）。"""
    path.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        fp = path / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(text)
    env = dict(os.environ,
               GIT_AUTHOR_DATE=commit_date, GIT_COMMITTER_DATE=commit_date,
               GIT_AUTHOR_NAME="test", GIT_AUTHOR_EMAIL="test@test",
               GIT_COMMITTER_NAME="test", GIT_COMMITTER_EMAIL="test@test")
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True, env=env)
    return path


class SyncTestCase(unittest.TestCase):
    """临时目录 + 打桩 sync.CONFIG_PATH / sync.SKILLS_DIR。"""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="sync-test-"))
        self._old_config, self._old_skills = sync.CONFIG_PATH, sync.SKILLS_DIR
        sync.CONFIG_PATH = self.tmp / "sync.local.csv"
        sync.SKILLS_DIR = self.tmp / "skills"

    def tearDown(self) -> None:
        sync.CONFIG_PATH, sync.SKILLS_DIR = self._old_config, self._old_skills
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_config(self, text: str) -> None:
        sync.CONFIG_PATH.write_text(text, encoding="utf-8")

    @staticmethod
    def capture(fn, *args):
        """静默执行并捕获输出，返回 (返回码, stdout, stderr)。"""
        out, errb = StringIO(), StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(errb):
            rc = fn(*args)
        return rc, out.getvalue(), errb.getvalue()


class TestLoadConfig(SyncTestCase):
    def test_two_col_header_and_modes(self) -> None:
        a, b, c, d, e = (self.tmp / x for x in "abcde")
        # 表头仍是两列 name,src（第三列可省略）；数据行混用两列 / 三列
        self.write_config("\n".join([
            "name,src",
            f"skill-a,{a}",                       # 两列 → 默认 sync
            f"skill-b,{b},sync",                  # 显式 sync
            f"skill-c,{c},watch",                 # watch
            f"skill-d,{d},bogus",                 # 非法 mode → 跳行
            f"skill-e,{e}, WATCH ",               # mode 去空白、大小写不敏感
            "",
            "# 注释行",
        ]) + "\n")
        self.assertEqual(sync.load_config(), [
            sync.Entry("skill-a", str(a), "sync"),
            sync.Entry("skill-b", str(b), "sync"),
            sync.Entry("skill-c", str(c), "watch"),
            sync.Entry("skill-e", str(e), "watch"),
        ])


class TestCopySemantics(SyncTestCase):
    def test_root_readme_excluded_nested_synced(self) -> None:
        src = self.tmp / "src"
        dst = sync.SKILLS_DIR / "x"
        (src / "sub" / "__pycache__").mkdir(parents=True)
        (src / "README.md").write_text("root")
        (src / "SKILL.md").write_text("body")
        (src / "sub" / "README.md").write_text("nested")
        (src / "sub" / "__pycache__" / "m.pyc").write_text("")

        sync.copy_skill(src, dst)
        self.assertFalse((dst / "README.md").exists())          # 根 README 排除
        self.assertEqual((dst / "SKILL.md").read_text(), "body")
        self.assertEqual((dst / "sub" / "README.md").read_text(), "nested")  # 嵌套 README 同步
        self.assertFalse((dst / "sub" / "__pycache__").exists())  # __pycache__ 排除

        sync.copy_skill(src, dst)  # 幂等重跑
        self.assertTrue(sync.dirs_equal(src, dst))

        (dst / "sub" / "README.md").unlink()  # 嵌套 README 缺失必须能检出
        self.assertFalse(sync.dirs_equal(src, dst))
        self.assertTrue(any("sub/README.md" in l for l in sync.diff_listing(src, dst)))


@unittest.skipUnless(GIT, "需要 git")
class TestPickNewestGit(SyncTestCase):
    def _two(self) -> tuple[Path, Path]:
        old = make_git_repo(self.tmp / "old", {"SKILL.md": "old"}, OLD_DATE)
        new = make_git_repo(self.tmp / "new", {"SKILL.md": "new"}, NEW_DATE)
        return old, new

    def test_newest_wins_regardless_of_row_order(self) -> None:
        old, new = self._two()
        e_old = sync.Entry("s", str(old), "sync")
        e_new = sync.Entry("s", str(new), "sync")
        self.assertIs(sync.pick_sync_source("s", [e_old, e_new]), e_new)
        self.assertIs(sync.pick_sync_source("s", [e_new, e_old]), e_new)

    def test_tie_picks_first_row(self) -> None:
        d1 = make_git_repo(self.tmp / "t1", {"SKILL.md": "1"}, NEW_DATE)
        d2 = make_git_repo(self.tmp / "t2", {"SKILL.md": "2"}, NEW_DATE)
        e1 = sync.Entry("s", str(d1), "sync")
        e2 = sync.Entry("s", str(d2), "sync")
        self.assertIs(sync.pick_sync_source("s", [e1, e2]), e1)

    def test_watch_not_counted_and_none_without_sync(self) -> None:
        old, new = self._two()
        watch = sync.Entry("s", str(old), "watch")
        self.assertIsNone(sync.pick_sync_source("s", [watch]))
        e_new = sync.Entry("s", str(new), "sync")
        self.assertIs(sync.pick_sync_source("s", [watch, e_new]), e_new)


class TestPickMtimeFallback(SyncTestCase):
    def test_mtime_fallback(self) -> None:
        d1, d2 = self.tmp / "m1", self.tmp / "m2"
        for d in (d1, d2):
            d.mkdir()
            (d / "SKILL.md").write_text("x")
        os.utime(d1 / "SKILL.md", (1785000000, 1785000000))
        os.utime(d2 / "SKILL.md", (1790000000, 1790000000))
        e1 = sync.Entry("s", str(d1), "sync")
        e2 = sync.Entry("s", str(d2), "sync")
        self.assertIs(sync.pick_sync_source("s", [e1, e2]), e2)

    def test_missing_source_scores_zero(self) -> None:
        e_missing = sync.Entry("s", str(self.tmp / "nope"), "sync")
        d = self.tmp / "m"
        d.mkdir()
        (d / "SKILL.md").write_text("x")
        e = sync.Entry("s", str(d), "sync")
        self.assertIs(sync.pick_sync_source("s", [e_missing, e]), e)


@unittest.skipUnless(GIT, "需要 git")
class TestRunSyncMultiSource(SyncTestCase):
    def test_syncs_from_newest_and_skips_watch(self) -> None:
        old = make_git_repo(self.tmp / "old",
                            {"SKILL.md": "old", "OLD_ONLY.txt": "x"}, OLD_DATE)
        new = make_git_repo(self.tmp / "new",
                            {"SKILL.md": "new", "NEW_ONLY.txt": "y"}, NEW_DATE)
        watch = self.tmp / "watch"
        watch.mkdir()
        (watch / "SKILL.md").write_text("watch")
        (watch / "WATCH_ONLY.txt").write_text("w")

        entries = [
            sync.Entry("s", str(old), "sync"),
            sync.Entry("s", str(new), "sync"),
            sync.Entry("s", str(watch), "watch"),
        ]
        rc, out, _ = self.capture(sync.run_sync, entries)
        self.assertEqual(rc, 0)

        dst = sync.SKILLS_DIR / "s"
        self.assertEqual((dst / "SKILL.md").read_text(), "new")   # 内容来自择新源
        self.assertTrue((dst / "NEW_ONLY.txt").exists())
        self.assertFalse((dst / "OLD_ONLY.txt").exists())         # 落选源独有文件不进来
        self.assertFalse((dst / "WATCH_ONLY.txt").exists())       # watch 源不同步
        self.assertIn("监控源不同步", out)

    def test_missing_chosen_source_errors(self) -> None:
        entries = [sync.Entry("s", str(self.tmp / "gone"), "sync")]
        rc, _, _ = self.capture(sync.run_sync, entries)
        self.assertEqual(rc, 4)


class TestRunCheckSemantics(SyncTestCase):
    def _mk_pair(self, name: str, body: str) -> Path:
        """源与仓库侧内容一致的 skill 目录，返回源路径。"""
        src = self.tmp / name
        src.mkdir()
        (src / "SKILL.md").write_text(body)
        dst = sync.SKILLS_DIR / name
        dst.mkdir(parents=True)
        (dst / "SKILL.md").write_text(body)
        return src

    def test_watch_drift_does_not_block(self) -> None:
        chosen = self._mk_pair("a", "v2")
        w = self.tmp / "watch-a"
        w.mkdir()
        (w / "SKILL.md").write_text("v1")  # watch 源落后于本仓库
        entries = [sync.Entry("a", str(chosen), "sync"),
                   sync.Entry("a", str(w), "watch")]
        rc, out, _ = self.capture(sync.run_check, entries)
        self.assertEqual(rc, 0)
        self.assertIn("监控源与本仓库不同", out)
        self.assertIn("a: 一致", out)

    def test_losing_sync_source_reported_not_blocking(self) -> None:
        chosen = self._mk_pair("b", "v2")
        alt = self.tmp / "alt-b"
        alt.mkdir()
        (alt / "SKILL.md").write_text("v1")  # 落选 sync 源落后
        entries = [sync.Entry("b", str(alt), "sync"),
                   sync.Entry("b", str(chosen), "sync")]
        # 无 git 目录 → mtime 择新；把 chosen 的 mtime 调新确保其胜出
        os.utime(chosen / "SKILL.md", (1790000000, 1790000000))
        rc, out, _ = self.capture(sync.run_check, entries)
        self.assertEqual(rc, 0)
        self.assertIn("备选源与本仓库不同", out)

    def test_chosen_drift_blocks(self) -> None:
        chosen = self._mk_pair("c", "v2")
        (sync.SKILLS_DIR / "c" / "SKILL.md").write_text("v1")  # 仓库侧落后
        rc, _, _ = self.capture(sync.run_check, [sync.Entry("c", str(chosen), "sync")])
        self.assertEqual(rc, 1)

    def test_watch_only_skill_never_blocks(self) -> None:
        w = self.tmp / "watch-only"
        w.mkdir()
        (w / "SKILL.md").write_text("x")
        rc, out, _ = self.capture(sync.run_check, [sync.Entry("d", str(w), "watch")])
        self.assertEqual(rc, 0)
        self.assertIn("仅监控", out)

    def test_missing_chosen_blocks_missing_watch_does_not(self) -> None:
        entries = [sync.Entry("e", str(self.tmp / "gone-sync"), "sync"),
                   sync.Entry("e", str(self.tmp / "gone-watch"), "watch")]
        rc, _, _ = self.capture(sync.run_check, entries)
        self.assertEqual(rc, 1)


class TestSelectTargets(SyncTestCase):
    def test_unknown_name_exits(self) -> None:
        self.write_config(f"x,{self.tmp / 'x'}\n")
        with self.assertRaises(SystemExit):
            sync.select_targets(sync.load_config(), ["nope"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
