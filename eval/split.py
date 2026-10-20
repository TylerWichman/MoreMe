"""Assign whole corpus documents to train / dev / heldout splits.

    python eval/split.py build                 write eval/split.json
    python eval/split.py check                 recompute and compare with eval/split.json; check minimums
    python eval/split.py materialize --split train --out DIR
                                               copy one split's files to DIR/<persona-id>/

Method (AD-006): every document stays whole. Within each persona, documents are
ordered by sha256("<seed>:<persona-id>:<file name>"), a stable hash with a fixed
seed. Walking that order, documents fill heldout toward 25% of the persona's
words (at least its minimum), then dev toward 15% (at least its minimum),
skipping a document that would overshoot more than it helps; the rest are train
(about 60%). See assign() for the exact rule. Words are counted with the FROZEN 1
word rule.
Minimums per persona: 3,000 train, 1,000 dev, 3,000 heldout words.

split.json records per-document word counts so later steps (task length targets)
can use counts without opening heldout text.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import statistics
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")
SPLIT_JSON = os.path.join(HERE, "split.json")

SEED = "moreme-eval-split-v1"
SPLITS = ("train", "dev", "heldout")
TARGETS = {"heldout": 0.25, "dev": 0.15, "train": 0.60}
FILL_ORDER = ("heldout", "dev")
MINIMUMS = {"train": 3000, "dev": 1000, "heldout": 3000}

WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*")


def count_words(text):
    """FROZEN 1 word rule: NFC, apostrophes mapped, letters with internal apostrophes."""
    t = unicodedata.normalize("NFC", text).replace("﻿", "")
    t = t.replace("’", "'").replace("‘", "'")
    return len(WORD.findall(t))


def doc_key(persona, name):
    return hashlib.sha256(("%s:%s:%s" % (SEED, persona, name)).encode("utf-8")).hexdigest()


def personas(corpus=CORPUS):
    out = []
    for d in sorted(os.listdir(corpus)):
        p = os.path.join(corpus, d)
        if os.path.isdir(p) and any(f.endswith(".txt") for f in os.listdir(p)):
            out.append(d)
    return out


def _fill(ordered, goal, closest):
    have = {s: 0 for s in SPLITS}
    out = {}
    for name, w, _key in ordered:
        dest = "train"
        for s in FILL_ORDER:
            gap = goal[s] - have[s]
            # closest: take the document only if the split ends nearer its goal with it than without it
            if gap > 0 and (not closest or w <= 2 * gap):
                dest = s
                break
        out[name] = dest
        have[dest] += w
    return out, have


def assign(docs):
    """docs: list of (name, words, hash_key). Returns {name: split}. Pure function of the inputs.

    Walk the documents in hash order. A document goes to heldout while heldout is
    below its goal (the larger of 25% of the persona's words and the heldout
    minimum), as long as heldout ends nearer its goal with the document than
    without it; otherwise it is offered to dev the same way (15%, dev minimum);
    otherwise it is train. If that leaves heldout or dev under its minimum, the
    walk is redone without the nearer-goal condition (plain fill in hash order).
    """
    total = sum(d[1] for d in docs)
    goal = {s: max(TARGETS[s] * total, MINIMUMS[s]) for s in SPLITS}
    ordered = sorted(docs, key=lambda d: d[2])
    out, have = _fill(ordered, goal, closest=True)
    if any(have[s] < MINIMUMS[s] for s in FILL_ORDER):
        out, have = _fill(ordered, goal, closest=False)
    return out


def compute(corpus=CORPUS):
    result = {
        "schema_version": "1",
        "seed": SEED,
        "method": "whole documents; order by sha256(seed:persona:file); fill heldout toward max(25%, 3000 words), then dev toward max(15%, 1000 words), taking a document only if the split ends nearer its goal; rest train",
        "targets": TARGETS,
        "minimums": MINIMUMS,
        "word_rule": "FROZEN 1 (NFC, curly apostrophes mapped, [^\\W\\d_]+(?:'[^\\W\\d_]+)*)",
        "personas": {},
    }
    for pid in personas(corpus):
        pdir = os.path.join(corpus, pid)
        names = sorted(f for f in os.listdir(pdir) if f.endswith(".txt"))
        docs = []
        for n in names:
            with open(os.path.join(pdir, n), encoding="utf-8") as f:
                docs.append((n, count_words(f.read()), doc_key(pid, n)))
        mapping = assign(docs)
        totals = {s: sum(w for n, w, _ in docs if mapping[n] == s) for s in SPLITS}
        counts = {s: sorted(w for n, w, _ in docs if mapping[n] == s) for s in SPLITS}
        result["personas"][pid] = {
            "documents": [{"file": "%s/%s" % (pid, n), "words": w, "split": mapping[n]} for n, w, _ in docs],
            "words": totals,
            "total_words": sum(totals.values()),
            "share": {s: round(totals[s] / max(1, sum(totals.values())), 4) for s in SPLITS},
            "doc_count": {s: len(counts[s]) for s in SPLITS},
            "median_doc_words": {s: (statistics.median(counts[s]) if counts[s] else None) for s in SPLITS},
        }
    return result


def violations(result):
    bad = []
    for pid, p in result["personas"].items():
        for s, m in MINIMUMS.items():
            if p["words"][s] < m:
                bad.append("%s: %s has %d words, minimum %d" % (pid, s, p["words"][s], m))
    return bad


def write_json(obj, path):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, sort_keys=False)
        f.write("\n")


def cmd_build(a):
    r = compute(a.corpus)
    bad = violations(r)
    write_json(r, a.json)
    for pid, p in r["personas"].items():
        print("%-10s train %5d  dev %5d  heldout %5d  (%s)" % (
            pid, p["words"]["train"], p["words"]["dev"], p["words"]["heldout"],
            " / ".join("%.0f%%" % (100 * p["share"][s]) for s in SPLITS)))
    for b in bad:
        print("MINIMUM NOT MET:", b, file=sys.stderr)
    return 1 if bad else 0


def cmd_check(a):
    r = compute(a.corpus)
    with open(a.json, encoding="utf-8") as f:
        saved = json.load(f)
    problems = violations(r)
    if saved != json.loads(json.dumps(r)):
        problems.append("split.json differs from a fresh computation (rerun: python eval/split.py build)")
    for p in problems:
        print(p, file=sys.stderr)
    print("ok" if not problems else "FAILED")
    return 1 if problems else 0


def cmd_materialize(a):
    with open(a.json, encoding="utf-8") as f:
        saved = json.load(f)
    n = 0
    for pid, p in saved["personas"].items():
        if a.persona and pid not in a.persona:
            continue
        dest = os.path.join(a.out, pid)
        os.makedirs(dest, exist_ok=True)
        for d in p["documents"]:
            if d["split"] == a.split:
                shutil.copyfile(os.path.join(a.corpus, d["file"]), os.path.join(dest, os.path.basename(d["file"])))
                n += 1
    print(json.dumps({"ok": True, "split": a.split, "out": a.out, "files": n}))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus", default=CORPUS)
    ap.add_argument("--json", default=SPLIT_JSON)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    sub.add_parser("check")
    m = sub.add_parser("materialize")
    m.add_argument("--split", choices=SPLITS, required=True)
    m.add_argument("--out", required=True)
    m.add_argument("--persona", action="append", help="limit to this persona id (repeatable)")
    a = ap.parse_args(argv)
    return {"build": cmd_build, "check": cmd_check, "materialize": cmd_materialize}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
