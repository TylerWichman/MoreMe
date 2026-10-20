#!/usr/bin/env python
"""Check MoreMe's user-facing prose for TC-001 problems.

Standard library only. Python 3.8 or newer.

Usage:
    python tools/check_prose.py            check the default targets
    python tools/check_prose.py PATH...    check these files or folders
    python tools/check_prose.py --list     print the files that would be checked

Rules:
    em_dash          the long dash character (U+2014)
    banned_word      a word or phrase from BANNED_PHRASES (case-insensitive, word boundaries)
    exclamation      an exclamation mark that ends a sentence
    forbidden_token  a scoring-only name that must never reach a skill or a user
    function_word_table  10 or more lines in a row that pair one word with a number

Exemptions:
    tools/prose_exempt.txt lists files that hold verbatim evidence (raw drafts,
    transcripts). They are skipped for every rule except forbidden_token.

    Inside a file, three marker pairs exempt a span:
      <!-- verbatim-samples:start --> ... <!-- verbatim-samples:end -->
          the user's own text: skips em_dash, banned_word, exclamation
      <!-- verbatim-output:start --> ... <!-- verbatim-output:end -->
          quoted model output (README before/after): same skips
      <!-- avoid-words:start --> ... <!-- avoid-words:end -->
          a list of words to avoid: skips banned_word only
    Nothing is ever skipped for forbidden_token.

Exit codes: 0 no violations, 1 violations found, 2 bad usage or unreadable file.
"""

import argparse
import fnmatch
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXEMPT_FILE = REPO_ROOT / "tools" / "prose_exempt.txt"

# TC-001 list from the creative brief (Content Direction, voice rules).
# analyze.py embeds the same list for validate-skill and the default avoid list.
BANNED_PHRASES = (
    "seamless",
    "seamlessly",
    "leverage",
    "leveraging",
    "unlock",
    "empower",
    "game-changer",
    "game changer",
    "delve",
    "robust",
    "elevate",
    "revolutionize",
    "revolutionary",
    "cutting-edge",
    "supercharge",
    "effortless",
    "effortlessly",
    "unleash",
    "transformative",
    "next-level",
    "world-class",
    "best-in-class",
    "magic",
    "magical",
    "in today's",
    "it's worth noting",
    "dive into",
    "deep dive",
    "say goodbye to",
    "whether you're",
    "look no further",
    "take your writing to the next level",
)

FORBIDDEN_TOKENS = (
    "scoring_only",
    "function_word_freq",
    "char3_freq",
    "delta_fw",
    "char3_cosine",
    "reference_stats",
)

EM_DASH = "—"

# Default targets, relative to the repo root. Missing ones are skipped.
DEFAULT_TARGETS = (
    "README.md",
    "moreme/SKILL.md",
    "moreme/reference",
    "moreme/templates",
    "docs/example-run",
    "eval/skills",
)
TEXT_SUFFIXES = {".md", ".tmpl", ".txt"}

MARKERS = {
    "verbatim-samples": {"em_dash", "banned_word", "exclamation"},
    "verbatim-output": {"em_dash", "banned_word", "exclamation"},
    "avoid-words": {"banned_word"},
}
MARKER_RE = re.compile(r"<!--\s*(verbatim-samples|verbatim-output|avoid-words):(start|end)\s*-->")

APOSTROPHES = str.maketrans({"’": "'", "‘": "'"})


def _phrase_pattern(phrase):
    # Word boundaries on both ends; inner spaces match any run of whitespace.
    parts = [re.escape(p) for p in phrase.split(" ")]
    return re.compile(r"(?<![\w'-])" + r"\s+".join(parts) + r"(?![\w-])", re.IGNORECASE)


BANNED_RES = [(p, _phrase_pattern(p)) for p in BANNED_PHRASES]
# An exclamation mark right after a letter, digit, or closing quote/bracket,
# followed by whitespace, a closing quote/bracket, or the end of the line.
# This skips "!=" in code and "![alt](...)" image syntax.
EXCLAMATION_RE = re.compile(r"(?<=[\w\"')\]”’])!+(?=[\s\"')\]”’*_]|$)")
WORD_NUMBER_LINE_RE = re.compile(r"^\W*[^\W\d_]+(?:'[^\W\d_]+)?\W+\d+(?:\.\d+)?\W*$")


class Violation:
    __slots__ = ("path", "line", "col", "rule", "text")

    def __init__(self, path, line, col, rule, text):
        self.path = path
        self.line = line
        self.col = col
        self.rule = rule
        self.text = text

    def __str__(self):
        return "%s:%d:%d: %s: %s" % (self.path, self.line, self.col, self.rule, self.text)


def load_exempt(path=EXEMPT_FILE):
    """Return the glob patterns from the exemption file (comments and blanks dropped)."""
    patterns = []
    if not path.is_file():
        return patterns
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            patterns.append(line.replace("\\", "/"))
    return patterns


def is_exempt(rel_path, patterns):
    rel = rel_path.replace("\\", "/")
    for pat in patterns:
        if fnmatch.fnmatchcase(rel, pat):
            return True
        if pat.endswith("/") and rel.startswith(pat):
            return True
    return False


def check_text(text, display_path="<text>", whole_file_exempt=False):
    """Return a list of Violation objects for one file's text."""
    violations = []
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    open_spans = []  # marker names currently open
    table_run = []  # (line_no, text) of consecutive word-number lines

    def flush_table():
        if len(table_run) >= 10:
            first = table_run[0][0]
            violations.append(Violation(display_path, first, 1, "function_word_table",
                                        "%d lines in a row pair a word with a number" % len(table_run)))
        del table_run[:]

    for idx, line in enumerate(lines, start=1):
        skips = set()
        if whole_file_exempt:
            skips |= {"em_dash", "banned_word", "exclamation"}
        for name in open_spans:
            skips |= MARKERS[name]

        # Forbidden tokens: never skipped.
        low = line.lower()
        for tok in FORBIDDEN_TOKENS:
            pos = low.find(tok)
            if pos >= 0:
                violations.append(Violation(display_path, idx, pos + 1, "forbidden_token", tok))

        # Marker lines change the open spans; check the rest of the line too.
        content = line
        for m in MARKER_RE.finditer(line):
            name, kind = m.group(1), m.group(2)
            if kind == "start" and name not in open_spans:
                open_spans.append(name)
            elif kind == "end" and name in open_spans:
                open_spans.remove(name)
        content = MARKER_RE.sub("", content)

        if "em_dash" not in skips:
            pos = content.find(EM_DASH)
            if pos >= 0:
                violations.append(Violation(display_path, idx, pos + 1, "em_dash", "U+2014 long dash"))

        if "banned_word" not in skips:
            mapped = content.translate(APOSTROPHES)
            for phrase, rx in BANNED_RES:
                for m in rx.finditer(mapped):
                    violations.append(Violation(display_path, idx, m.start() + 1, "banned_word", phrase))

        if "exclamation" not in skips:
            stripped = re.sub(r"`[^`]*`", lambda m: " " * len(m.group(0)), content)
            for m in EXCLAMATION_RE.finditer(stripped):
                violations.append(Violation(display_path, idx, m.start() + 1, "exclamation", "!"))

        if WORD_NUMBER_LINE_RE.match(line.strip()):
            table_run.append((idx, line))
        else:
            flush_table()
    flush_table()

    # A phrase can be split across a line break; check joined lines once more.
    if not whole_file_exempt:
        violations.extend(_check_wrapped_phrases(lines, display_path))
    return violations


def _check_wrapped_phrases(lines, display_path):
    found = []
    open_spans = []
    for idx in range(len(lines) - 1):
        line = lines[idx]
        for m in MARKER_RE.finditer(line):
            name, kind = m.group(1), m.group(2)
            if kind == "start" and name not in open_spans:
                open_spans.append(name)
            elif kind == "end" and name in open_spans:
                open_spans.remove(name)
        if any("banned_word" in MARKERS[n] for n in open_spans):
            continue
        nxt = lines[idx + 1]
        if MARKER_RE.search(nxt):
            continue
        a = line.translate(APOSTROPHES)
        b = nxt.translate(APOSTROPHES)
        joined = a + " " + b
        for phrase, rx in BANNED_RES:
            if " " not in phrase:
                continue
            for m in rx.finditer(joined):
                if m.start() < len(a) < m.end():
                    found.append(Violation(display_path, idx + 1, m.start() + 1, "banned_word", phrase))
    return found


def iter_files(targets, root=REPO_ROOT):
    for t in targets:
        p = Path(t)
        if not p.is_absolute():
            p = root / p
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and f.suffix.lower() in TEXT_SUFFIXES and "__pycache__" not in f.parts:
                    yield f


def rel_display(path, root=REPO_ROOT):
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def check_paths(targets, root=REPO_ROOT, exempt_patterns=None):
    if exempt_patterns is None:
        exempt_patterns = load_exempt()
    violations = []
    checked = []
    for f in iter_files(targets, root):
        rel = rel_display(f, root)
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise SystemExit("check_prose: cannot read %s as UTF-8 (%s)" % (rel, exc.__class__.__name__))
        exempt = is_exempt(rel, exempt_patterns)
        checked.append((rel, exempt))
        violations.extend(check_text(text, rel, whole_file_exempt=exempt))
    return checked, violations


def _utf8_stdout():
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)
        if reconf is not None:
            try:
                reconf(encoding="utf-8")
            except (ValueError, OSError):
                pass


def main(argv=None):
    _utf8_stdout()
    ap = argparse.ArgumentParser(description="Check MoreMe prose for TC-001 problems.")
    ap.add_argument("paths", nargs="*", help="files or folders (default: the release prose targets)")
    ap.add_argument("--list", action="store_true", help="print the files that would be checked, then exit")
    args = ap.parse_args(argv)

    targets = args.paths or list(DEFAULT_TARGETS)
    for t in args.paths:
        p = Path(t) if Path(t).is_absolute() else Path.cwd() / t
        if not p.exists():
            print("check_prose: no such file or folder: %s" % t, file=sys.stderr)
            return 2
    if args.paths:
        targets = [str(Path(t).resolve()) for t in args.paths]

    try:
        checked, violations = check_paths(targets)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.list:
        for rel, exempt in checked:
            print(("%s  (exempt: verbatim evidence)" % rel) if exempt else rel)
        return 0

    for v in violations:
        print(v)
    n_exempt = sum(1 for _, e in checked if e)
    print("check_prose: %d file(s) checked (%d exempt), %d violation(s)"
          % (len(checked), n_exempt, len(violations)))
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
