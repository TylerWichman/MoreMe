"""Repo-wide privacy check over every git-tracked file.

Fails if a tracked file's path or content holds, for the machine running the
test: the home folder path in any form (backslash, forward slash, MSYS,
JSON-escaped, URL-encoded), Claude Code's project-folder name for it, the OS
user name (whole word, any case), a personal name from the global git
user.name or MOREME_PRIVATE_TOKENS (whole word, case-sensitive), or any email
address other than the GitHub noreply form. The values are found at run time by
tools/sanitize_artifacts.py; nothing personal is written here.

Exceptions: tests/privacy_allowlist.txt (kept empty unless justified).
"""
import fnmatch
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import sanitize_artifacts as sa  # noqa: E402

ALLOWLIST = REPO / "tests" / "privacy_allowlist.txt"
KINDS = {"home", "slug", "username", "name", "email"}


def load_allowlist(path=ALLOWLIST):
    entries = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            raise ValueError("bad allowlist line: %r" % raw)
        glob, kind = parts
        value = None
        if kind.startswith("email="):
            kind, value = "email", kind[len("email="):]
        if kind not in KINDS:
            raise ValueError("bad allowlist kind: %r" % raw)
        if "#" not in raw:
            raise ValueError("allowlist entry needs a reason after '#': %r" % raw)
        entries.append((glob, kind, value))
    return entries


def allowed(entries, rel, kind, matched):
    for glob, k, value in entries:
        if k == kind and fnmatch.fnmatch(rel, glob) and (value is None or value == matched):
            return True
    return False


def tracked():
    try:
        p = subprocess.run(["git", "ls-files", "-z"], cwd=str(REPO), capture_output=True, timeout=60)
    except OSError:
        pytest.skip("git not available")
    if p.returncode != 0:
        pytest.skip("not a git checkout")
    return [f for f in p.stdout.decode("utf-8").split("\0") if f]


def scan(files, sanitizer, entries, root=REPO):
    problems = []
    for rel in files:
        f = Path(root) / rel
        for kind, a, b in sanitizer.findings(rel):
            if not allowed(entries, rel, kind, rel[a:b]):
                problems.append("%s (file name): %s" % (rel, kind))
        if not f.is_file():
            continue
        text = f.read_bytes().decode("utf-8", "replace")
        for kind, a, b in sanitizer.findings(text):
            if allowed(entries, rel, kind, text[a:b]):
                continue
            line = text.count("\n", 0, a) + 1
            problems.append("%s:%d: %s" % (rel, line, kind))
    return problems


def test_allowlist_parses():
    load_allowlist()


def test_no_private_values_in_tracked_files():
    files = tracked()
    assert files, "git ls-files returned nothing"
    s = sa.Sanitizer()
    problems = scan(files, s, load_allowlist())
    # Report locations and kinds only, never the matched text.
    assert not problems, "private values in tracked files (fix with tools/sanitize_artifacts.py --write):\n" + \
        "\n".join(problems[:200]) + ("\n... %d more" % (len(problems) - 200) if len(problems) > 200 else "")


def test_scan_catches_every_kind(tmp_path):
    tokens = {"home": "C:\\Users\\zqxjones", "users": ["zqxjones"], "names": ["Zqxjones", "Brindleford"],
              "emails": []}
    s = sa.Sanitizer(tokens)
    samples = {
        "a.json": "\"C:\\\\Users\\\\zqxjones\\\\AppData\"",
        "b.txt": "/c/Users/zqxjones/x",
        "c.md": "C--Users-zqxjones-Documents",
        "d.md": "signed Brindleford",
        "e.md": "mail me at [email]",
        "f.md": "run as zqxjones",
        "ok.md": "1+h@users.noreply.github.com and ZqxjonesBrindleford",
    }
    for name, text in samples.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    probs = scan(sorted(samples), s, [], root=tmp_path)
    flagged = sorted(set(p.split(":")[0] for p in probs))
    assert flagged == ["a.json", "b.txt", "c.md", "d.md", "e.md", "f.md"]
    assert scan(["zqxjones-notes.md"], s, [], root=tmp_path) == ["zqxjones-notes.md (file name): username"]
    assert scan(["e.md"], s, [("*.md", "email", "[email]")], root=tmp_path) == []
    assert scan(["e.md"], s, [("*.md", "email", "[email]")], root=tmp_path) != []
