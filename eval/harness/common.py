"""Shared paths, constants, and helpers for the eval harness."""
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL = HERE.parent
REPO = EVAL.parent
CORPUS = EVAL / "corpus"
SPLIT_JSON = EVAL / "split.json"
LICENSES_JSON = CORPUS / "licenses.json"
REFERENCE_STATS = EVAL / "reference_stats.json"
TASKS_JSON = EVAL / "tasks" / "tasks.json"
RESULTS = EVAL / "results"
SKILLS = EVAL / "skills"
PREREG = EVAL / "PREREGISTRATION.md"
ANALYZE = REPO / "moreme" / "analyze.py"
SKILL_MD = REPO / "moreme" / "SKILL.md"
TEMPLATE = REPO / "moreme" / "templates" / "my-voice" / "SKILL.md.tmpl"

if str(EVAL) not in sys.path:
    sys.path.insert(0, str(EVAL))
from lib import childrun  # noqa: E402

ARMS = ("with", "without", "samples-pasted")
REPS = {"with": 2, "without": 2, "samples-pasted": 1}
TASKS_PER_PERSONA = 8
LENGTH_CLAMP = (120, 400)
SHINGLE_WORDS = 12
BOOTSTRAP_RESAMPLES = 10000
BOOTSTRAP_SEED = 20261019
ARM_ORDER_SEED = "moreme-arm-order-v1"
SAMPLES_SEED = "moreme-samples-pasted-v1"
INVOCATION_THRESHOLD = 0.80
GATE_MULTIPLE = 2.0

# Pre-registered persona run order: modern and era-diverse interleaved (AD-006).
RUN_ORDER = ("modern-a", "era-c", "modern-b", "era-d", "era-e", "era-f")

WORD_RE = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*")


def load_analyze():
    """Import moreme/analyze.py in-process (read-only use of its functions)."""
    spec = importlib.util.spec_from_file_location("moreme_analyze_harness", str(ANALYZE))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path):
    with open(str(path), encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    """UTF-8, LF, ensure_ascii False, trailing newline, atomic replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".tmp")
    with open(str(tmp), "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(str(tmp), str(path))


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".tmp")
    with open(str(tmp), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(str(tmp), str(path))


def load_split(path=SPLIT_JSON):
    return read_json(path)


def license_headers(path=LICENSES_JSON):
    return dict((p, m["header"]) for p, m in read_json(path)["personas"].items())


def persona_era(path=LICENSES_JSON):
    return dict((p, m["era"]) for p, m in read_json(path)["personas"].items())


def split_files(split, persona, which):
    """Relative corpus paths of one persona's documents in one split."""
    return [d["file"] for d in split["personas"][persona]["documents"] if d["split"] == which]


def target_length(split, persona):
    """Median held-out document word count from split.json metadata (counts only,
    no held-out text read), clamped to 120-400 words (AD-006)."""
    median = split["personas"][persona]["median_doc_words"]["heldout"]
    lo, hi = LENGTH_CLAMP
    return int(max(lo, min(hi, round(median))))


def read_corpus_text(split, rel, allow=("train", "dev")):
    """Read one corpus document, refusing any split not in `allow`.
    The validity gate and the dev smoke never pass "heldout"."""
    which = None
    for meta in split["personas"].values():
        for d in meta["documents"]:
            if d["file"] == rel:
                which = d["split"]
    if which is None:
        raise ValueError("not a corpus document: %s" % rel)
    if which not in allow:
        raise PermissionError("refusing to open a %s document: %s" % (which, rel))
    with open(str(CORPUS / rel), encoding="utf-8") as f:
        return f.read()


def words(text):
    t = text.replace("’", "'").replace("‘", "'")
    return WORD_RE.findall(t)


def sha256_text_file(path):
    """sha256 of a file with CRLF and CR normalized to LF, so a hash does not
    depend on the checkout's line endings."""
    data = Path(path).read_bytes()
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def rel(path):
    """Repo-relative forward-slash path (no home folders in saved records)."""
    try:
        return Path(path).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(path).name


_HOME_RE = re.compile(r"(?i)([A-Z]:[\\/]+Users[\\/]+|/Users/|/home/)[^\\/\s\"']+")


def scrub_paths(text):
    """Replace any home-folder path prefix with <home>, for repo summaries."""
    return _HOME_RE.sub(lambda m: m.group(1)[:0] + "<home>", text)
