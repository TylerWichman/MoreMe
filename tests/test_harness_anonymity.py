"""AMEND-002: harness outputs in the repo hold no home paths, user names, or
raw logs. Raw stream-json logs and call ledgers live outside the repo."""
import os
import re
import sys
from pathlib import Path

import test_harness_support  # noqa: F401  (puts eval/ on sys.path)
from harness import common

sys.path.insert(0, str(common.REPO / "tools"))
from sanitize_artifacts import GENERIC_USERS  # noqa: E402

HOME_RE = re.compile(r"(?i)[A-Z]:[\\/]+Users[\\/]+[A-Za-z0-9._-]+|/Users/[A-Za-z0-9._-]+|/home/[A-Za-z0-9._-]+")


def owned_files():
    roots = [common.EVAL / "harness", common.EVAL / "tasks", common.RESULTS, common.PREREG]
    for r in roots:
        if r.is_file():
            yield r
        elif r.exists():
            for f in r.rglob("*"):
                if f.is_file() and "__pycache__" not in f.parts:
                    yield f


def test_no_home_paths_or_user_name_in_harness_files():
    user = os.path.basename(os.path.expanduser("~"))
    bad = []
    for f in owned_files():
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in HOME_RE.finditer(text):
            bad.append("%s: %s" % (f.relative_to(common.REPO).as_posix(), m.group(0)[:3] + "..."))
        if user and len(user) > 2 and user.lower() not in GENERIC_USERS and re.search(r"(?i)\b%s\b" % re.escape(user), text):
            bad.append("%s: OS user name" % f.relative_to(common.REPO).as_posix())
    assert not bad, bad


def test_no_raw_logs_or_ledgers_in_results():
    assert not [f for f in common.RESULTS.rglob("*.jsonl")] if common.RESULTS.exists() else True


def test_scrub_paths_helper():
    assert common.scrub_paths(r"cwd C:\Users\someone\AppData\x") == r"cwd <home>\AppData\x"
    assert common.scrub_paths("/home/someone/a") == "<home>/a"
