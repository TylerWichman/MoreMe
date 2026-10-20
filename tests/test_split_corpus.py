"""eval/split.py: whole-document split, stable hash, fixed seed, word minimums (AD-006)."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SPLIT_PY = REPO / "eval" / "split.py"
SPLIT_JSON = REPO / "eval" / "split.json"


def load():
    spec = importlib.util.spec_from_file_location("moreme_eval_split", str(SPLIT_PY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


split = load()
SAVED = json.loads(SPLIT_JSON.read_text(encoding="utf-8"))


def test_saved_split_matches_a_fresh_computation():
    assert SAVED == json.loads(json.dumps(split.compute()))
    r = subprocess.run([sys.executable, str(SPLIT_PY), "check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_minimum_words_per_persona_and_split():
    assert split.MINIMUMS == {"train": 3000, "dev": 1000, "heldout": 3000}
    assert len(SAVED["personas"]) >= 4
    for pid, p in SAVED["personas"].items():
        for s, m in split.MINIMUMS.items():
            assert p["words"][s] >= m, (pid, s, p["words"][s])


def test_shares_are_near_60_15_25():
    for pid, p in SAVED["personas"].items():
        assert 0.50 <= p["share"]["train"] <= 0.70, (pid, p["share"])
        assert 0.10 <= p["share"]["dev"] <= 0.25, (pid, p["share"])
        assert 0.20 <= p["share"]["heldout"] <= 0.35, (pid, p["share"])


def test_every_document_assigned_once_with_its_word_count():
    files = sorted("%s/%s" % (p.parent.name, p.name) for p in (REPO / "eval" / "corpus").glob("*/*.txt"))
    listed = sorted(d["file"] for p in SAVED["personas"].values() for d in p["documents"])
    assert listed == files
    for pid, p in SAVED["personas"].items():
        for d in p["documents"]:
            assert d["split"] in ("train", "dev", "heldout")
            text = (REPO / "eval" / "corpus" / d["file"]).read_text(encoding="utf-8")
            assert d["words"] == split.count_words(text)
        assert sum(d["words"] for d in p["documents"]) == p["total_words"]
        for s in ("train", "dev", "heldout"):
            assert p["words"][s] == sum(d["words"] for d in p["documents"] if d["split"] == s)
            assert p["median_doc_words"][s] is not None


def test_hash_is_stable_and_seeded():
    assert split.SEED == "moreme-eval-split-v1"
    # sha256 of "moreme-eval-split-v1:era-c:era-c-01.txt"; changes only if the seed or naming changes
    import hashlib
    assert split.doc_key("era-c", "era-c-01.txt") == hashlib.sha256(
        b"moreme-eval-split-v1:era-c:era-c-01.txt").hexdigest()


def test_assign_is_deterministic_and_order_independent():
    docs = [("d%02d.txt" % i, 400 + 37 * i, split.doc_key("x", "d%02d.txt" % i)) for i in range(30)]
    a = split.assign(docs)
    b = split.assign(list(reversed(docs)))
    assert a == b
    words = dict((n, w) for n, w, _ in docs)
    tot = dict((s, sum(words[n] for n in a if a[n] == s)) for s in ("train", "dev", "heldout"))
    assert tot["heldout"] >= 3000 and tot["dev"] >= 1000 and tot["train"] >= 3000


def test_assign_falls_back_to_plain_fill_when_minimum_would_be_missed():
    # one huge document first in hash order would be skipped by the nearer-goal rule,
    # leaving heldout short; the fallback must still reach the minimum
    docs = [("big.txt", 9000, "0"), ("a.txt", 500, "1"), ("b.txt", 500, "2"), ("c.txt", 1200, "3")]
    out = split.assign(docs)
    held = sum(w for n, w, _ in docs if out[n] == "heldout")
    assert held >= 3000


def test_word_rule_matches_frozen_1():
    assert split.count_words("hey. can you send the file today?") == 7
    assert split.count_words("i’m out at 3.5 pm.") == 4
    assert split.count_words("Dr. Lee said it's fine... we can wait!") == 8
    assert split.count_words("ok thanks \U0001F642") == 2


def test_materialize_copies_only_the_requested_split(tmp_path):
    out = tmp_path / "train"
    r = subprocess.run([sys.executable, str(SPLIT_PY), "materialize", "--split", "train", "--out", str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    copied = sorted("%s/%s" % (p.parent.name, p.name) for p in out.glob("*/*.txt"))
    expected = sorted(d["file"] for p in SAVED["personas"].values() for d in p["documents"] if d["split"] == "train")
    assert copied == expected
    assert sorted(os.listdir(str(out))) == sorted(SAVED["personas"])
