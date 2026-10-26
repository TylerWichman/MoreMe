#!/usr/bin/env python
"""Remove personal details from files before they are committed.

Standard library only. Python 3.8 or newer.

What it replaces (all values are found at run time on the current machine,
nothing personal is written in this file):

    home folder path    every form: C:\\Users\\<name>, C:/Users/<name>,
                        /c/Users/<name>, //c/Users/<name>, JSON-escaped
                        backslashes, URL-encoded separators, /home/<name>
                        -> ~
    project-folder name Claude Code's folder name for a path under the home
                        folder, for example C--Users-<name>-Documents
                        -> HOME-Documents
    personal names      first and last name from the global git user.name,
                        the OS user name with a capital first letter, and
                        anything in MOREME_PRIVATE_TOKENS (comma separated),
                        whole words, case-sensitive -> [name]
    OS user name        whole word, any case -> [user]
    email addresses     every address except the GitHub noreply form
                        -> [email]

Usage:
    python tools/sanitize_artifacts.py --check PATH...    report, change nothing
    python tools/sanitize_artifacts.py --write PATH...    rewrite files in place
    python tools/sanitize_artifacts.py --check --tracked  every git-tracked file

Prints counts per file, never the matched text. Exit codes: 0 clean (or
written), 1 findings in --check mode, 2 bad usage.
"""

import argparse
import getpass
import os
import re
import subprocess
import sys
from pathlib import Path

DISCLOSURE = ("Home folder path replaced with ~ by tools/sanitize_artifacts.py "
              "(the OS user name, personal names, and email addresses are also replaced: "
              "[user], [name], [email]).")

HOME_TOKEN = "~"
SLUG_TOKEN = "HOME"
NAME_TOKEN = "[name]"
USER_TOKEN = "[user]"
EMAIL_TOKEN = "[email]"

# Account names that say nothing about a person (CI runners, containers).
GENERIC_USERS = {"runner", "root", "user", "admin", "administrator", "ubuntu", "vagrant",
                 "docker", "build", "builder", "ci", "test", "runneradmin"}

SEP = r"(?:\\|/|%5[cC]|%2[fF])+"
WORD_LEFT = r"(?<![A-Za-z0-9])"
WORD_RIGHT = r"(?![A-Za-z0-9])"
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
NOREPLY_RE = re.compile(r"^(?:[0-9]+\+)?[A-Za-z0-9-]+@users\.noreply\.github\.com$", re.I)


def _git_global(key):
    try:
        p = subprocess.run(["git", "config", "--global", key], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=20)
        return p.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def discover(home=None, user=None, use_git=True, env=None):
    """Collect the private values of this machine. Returns a dict with keys
    home (str), users (list), names (list), emails (list)."""
    env = os.environ if env is None else env
    home = str(home if home is not None else Path.home())
    # Split on both separators so a Windows path is read the same on any OS.
    home_name = re.split(r"[\\/]", home.rstrip("\\/"))[-1]
    users = []
    for u in (user if user is not None else _safe_getuser(), home_name):
        if u and len(u) >= 3 and u.lower() not in GENERIC_USERS and u.lower() not in [x.lower() for x in users]:
            users.append(u)
    names = []
    for u in users:
        cap = u[:1].upper() + u[1:]
        if cap not in names:
            names.append(cap)
    emails = []
    if use_git:
        for w in re.split(r"\s+", _git_global("user.name")):
            w = w.strip()
            if len(w) >= 3 and w not in names:
                names.append(w)
        e = _git_global("user.email")
        if e and not NOREPLY_RE.match(e):
            emails.append(e)
    for w in (env.get("MOREME_PRIVATE_TOKENS") or "").split(","):
        w = w.strip()
        if len(w) >= 3 and w not in names:
            names.append(w)
    return {"home": home, "users": users, "names": names, "emails": emails}


def _safe_getuser():
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - getuser raises several types
        return ""


def _home_parts(home):
    """('c', ['Users', 'name']) for a Windows home, (None, ['home', 'name']) for POSIX."""
    h = home.replace("\\", "/")
    m = re.match(r"^([A-Za-z]):/*(.*)$", h)
    if m:
        return m.group(1), [p for p in m.group(2).split("/") if p]
    m = re.match(r"^/([A-Za-z])/(.*)$", h)  # MSYS form given as the home
    if m:
        return m.group(1), [p for p in m.group(2).split("/") if p]
    return None, [p for p in h.split("/") if p]


class Sanitizer(object):
    """Find and replace the private values from `discover()`."""

    def __init__(self, tokens=None):
        self.tokens = tokens if tokens is not None else discover()
        self.rules = []  # (kind, compiled regex, replacement or None)
        drive, parts = _home_parts(self.tokens["home"])
        if parts and len(parts) >= 1 and self.tokens["home"] not in ("/", ""):
            body = SEP.join(re.escape(p) for p in parts)
            if drive:
                prefix = (r"(?:%s%s:|(?<![A-Za-z0-9:])/{1,2}%s(?=[\\/%%])|%s%s(?:%%3[aA]))?" % (
                    WORD_LEFT, drive, drive, WORD_LEFT, drive))
            else:
                prefix = ""
            self.rules.append(("home", re.compile("(?:" + prefix + SEP + "|" + WORD_LEFT + ")" + body + WORD_RIGHT, re.I),
                               HOME_TOKEN))
            slug_body = "-+".join(re.escape(re.sub(r"[^A-Za-z0-9]", "-", p)) for p in parts)
            slug_prefix = r"(?:%s-+)?" % drive if drive else ""
            self.rules.append(("slug", re.compile(WORD_LEFT + r"-*" + slug_prefix + slug_body + WORD_RIGHT, re.I),
                               SLUG_TOKEN))
        for e in self.tokens.get("emails", []):
            self.rules.append(("email", re.compile(re.escape(e), re.I), EMAIL_TOKEN))
        self.rules.append(("email", EMAIL_RE, None))
        for n in sorted(self.tokens.get("names", []), key=len, reverse=True):
            self.rules.append(("name", re.compile(WORD_LEFT + re.escape(n) + WORD_RIGHT), NAME_TOKEN))
        for u in self.tokens.get("users", []):
            self.rules.append(("username", re.compile(WORD_LEFT + re.escape(u) + WORD_RIGHT, re.I), USER_TOKEN))

    def findings(self, text):
        """[(kind, start, end)] for every private value, in rule order."""
        out = []
        for kind, rx, _rep in self.rules:
            for m in rx.finditer(text):
                if kind == "email" and NOREPLY_RE.match(m.group(0)):
                    continue
                out.append((kind, m.start(), m.end()))
        return out

    def sanitize(self, text):
        """Return (new_text, {kind: count})."""
        counts = {}
        for kind, rx, rep in self.rules:
            def sub(m, kind=kind, rep=rep):
                if kind == "email" and NOREPLY_RE.match(m.group(0)):
                    return m.group(0)
                counts[kind] = counts.get(kind, 0) + 1
                return rep if rep is not None else EMAIL_TOKEN
            text = rx.sub(sub, text)
        return text, counts


_DEFAULT = None


def default_sanitizer():
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Sanitizer()
    return _DEFAULT


def sanitize_text(text, sanitizer=None):
    """Sanitized text only (the hook the e2e driver and eval harness call)."""
    return (sanitizer or default_sanitizer()).sanitize(text)[0]


def disclose_markdown(text):
    """Add the DISCLOSURE as a quoted line after the first `# ` heading
    (or at the top), once."""
    if DISCLOSURE in text:
        return text
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("# "):
            return "\n".join(lines[:i + 1] + ["", "> " + DISCLOSURE] + lines[i + 1:])
    return "> " + DISCLOSURE + "\n\n" + text


def is_binary(data):
    return b"\x00" in data[:8192]


def sanitize_file(path, write=False, sanitizer=None):
    """Return {kind: count} for one file; rewrite it when write is True.
    Binary files are reported but never rewritten."""
    s = sanitizer or default_sanitizer()
    data = Path(path).read_bytes()
    text = data.decode("utf-8", "replace")
    new, counts = s.sanitize(text)
    if write and counts and not is_binary(data):
        Path(path).write_bytes(new.encode("utf-8"))
    return counts


def tracked_files(repo):
    p = subprocess.run(["git", "ls-files", "-z"], cwd=str(repo), capture_output=True, timeout=60)
    if p.returncode != 0:
        raise RuntimeError("git ls-files failed")
    return [Path(repo) / f for f in p.stdout.decode("utf-8").split("\0") if f]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Remove personal details from files")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="report only")
    g.add_argument("--write", action="store_true", help="rewrite files in place")
    ap.add_argument("--tracked", action="store_true", help="every git-tracked file of this repo")
    ap.add_argument("paths", nargs="*")
    args = ap.parse_args(argv)
    repo = Path(__file__).resolve().parent.parent
    files = []
    if args.tracked:
        files += tracked_files(repo)
    for p in args.paths:
        p = Path(p)
        files += sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else [p]
    if not files:
        ap.print_usage()
        return 2
    s = default_sanitizer()
    found = 0
    for f in files:
        if not f.is_file():
            continue
        counts = sanitize_file(f, write=args.write, sanitizer=s)
        if counts:
            found += 1
            try:
                shown = f.resolve().relative_to(repo).as_posix()
            except ValueError:
                shown = sanitize_text(str(f), s)
            print("%s %s" % (shown, " ".join("%s=%d" % kv for kv in sorted(counts.items()))))
    print("%d file(s) %s" % (found, "rewritten" if args.write else "with findings"))
    return 1 if (found and args.check) else 0


if __name__ == "__main__":
    sys.exit(main())
