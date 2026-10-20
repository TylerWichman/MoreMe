#!/usr/bin/env python
"""List, and only on request delete, the empty session folders that child
`claude -p` runs leave under ~/.claude/projects.

Safety rules (AD-006, T-006):
- Only direct children of <home>/.claude/projects are considered.
- A name matches only if it equals, or starts with followed by "-", one of two
  prefixes derived from the machine temp path (the same path the child-run
  library uses for scratch projects):
      project_folder_name(<temp>/moreme-eval)
      project_folder_name(<temp>/moreme-e2e)
  On this machine that is C--Users-<you>-AppData-Local-Temp-moreme-eval and
  ...-moreme-e2e. Matching is case-sensitive and anchored at the start.
- The bare temp entry (C--Users-<you>-AppData-Local-Temp) and every other
  project, including the OneShot inputs/MoreMe project, never match.
- Symlinks, junctions, and other reparse points are never followed and never
  deleted. Inside a matched folder, a link is removed as a link, never entered.
- Dry run is the default. Deletion needs --delete.

Usage:
    python eval/tools/cleanup_session_folders.py              dry run, real home
    python eval/tools/cleanup_session_folders.py --delete     delete (operator approval only)
    python eval/tools/cleanup_session_folders.py --home DIR --temp-dir DIR   (tests)

Prints one JSON object. Standard library only.
"""
import argparse
import json
import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.childrun import SCRATCH_KINDS, home, project_folder_name, temp_base  # noqa: E402

FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def prefixes(temp_dir=None):
    t = Path(temp_dir) if temp_dir else temp_base()
    return [project_folder_name(t / kind) for kind in SCRATCH_KINDS]


def name_matches(name, prefix_list):
    return any(name == p or name.startswith(p + "-") for p in prefix_list)


def is_link(path):
    """True for symlinks, junctions, and any other reparse point. Never follows."""
    try:
        st = os.lstat(str(path))
    except OSError:
        return True
    if stat.S_ISLNK(st.st_mode):
        return True
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)


def _remove_link(path):
    # A junction or directory symlink on Windows is removed with rmdir;
    # a file symlink with unlink. Neither touches the target.
    try:
        os.rmdir(str(path))
    except OSError:
        os.unlink(str(path))


def safe_rmtree(root):
    """Delete a real folder without ever entering a link."""
    if is_link(root):
        raise ValueError("refusing to delete a link as a tree: %s" % root)
    with os.scandir(str(root)) as it:
        entries = list(it)
    for e in entries:
        p = Path(e.path)
        if is_link(p):
            _remove_link(p)
        elif e.is_dir(follow_symlinks=False):
            safe_rmtree(p)
        else:
            os.chmod(str(p), stat.S_IWRITE)
            os.unlink(str(p))
    os.rmdir(str(root))


def plan(home_dir=None, temp_dir=None):
    base = Path(home_dir) if home_dir else home()
    projects = base / ".claude" / "projects"
    pre = prefixes(temp_dir)
    out = {"projects_dir": str(projects), "prefixes": pre, "matched": [], "skipped_links": [],
           "skipped_not_dir": []}
    if not projects.is_dir() or is_link(projects):
        out["error"] = "projects folder missing or a link"
        return out
    with os.scandir(str(projects)) as it:
        entries = sorted(it, key=lambda e: e.name)
    for e in entries:
        if not name_matches(e.name, pre):
            continue
        p = Path(e.path)
        if is_link(p):
            out["skipped_links"].append(e.name)
        elif not e.is_dir(follow_symlinks=False):
            out["skipped_not_dir"].append(e.name)
        else:
            out["matched"].append(e.name)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--home", help="home folder to work in (default: your real home)")
    ap.add_argument("--temp-dir", help="temp folder the prefixes come from (default: machine temp)")
    ap.add_argument("--delete", action="store_true", help="actually delete the matched folders")
    args = ap.parse_args(argv)
    out = plan(args.home, args.temp_dir)
    out["mode"] = "delete" if args.delete else "dry-run"
    out["deleted"] = []
    if args.delete and "error" not in out:
        projects = Path(out["projects_dir"])
        for name in out["matched"]:
            safe_rmtree(projects / name)
            out["deleted"].append(name)
    sys.stdout.write(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
