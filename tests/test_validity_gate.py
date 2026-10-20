"""Draft-length validity gate on dev data (AD-006, A-012; decision
2026-10-20-persona-distinctness-accept-moreme)."""
import builtins
import io
from pathlib import Path

import pytest

import test_harness_support  # noqa: F401  (puts eval/ on sys.path)
from harness import common, validity

SAVED = common.RESULTS / "validity-gate.json"


@pytest.fixture(scope="module")
def fresh(request):
    """Run the gate while recording every corpus file opened."""
    opened = []
    real_open = builtins.open
    real_io_open = io.open

    def spy(file, *a, **k):
        try:
            opened.append(Path(file).resolve())
        except TypeError:
            pass
        return real_open(file, *a, **k)

    builtins.open = spy
    io.open = spy
    try:
        result = validity.run_gate()
    finally:
        builtins.open = real_open
        io.open = real_io_open
    return result, opened


def test_no_heldout_file_is_opened(fresh):
    _r, opened = fresh
    split = common.load_split()
    heldout = set((common.CORPUS / f).resolve() for p in split["personas"]
                  for f in common.split_files(split, p, "heldout"))
    corpus_opened = [p for p in opened if common.CORPUS.resolve() in p.parents]
    assert corpus_opened, "the spy saw no corpus reads"
    assert not (set(corpus_opened) & heldout)
    dev_train = set((common.CORPUS / f).resolve() for p in split["personas"]
                    for w in ("train", "dev") for f in common.split_files(split, p, w))
    assert set(corpus_opened) <= dev_train


def test_read_corpus_text_refuses_heldout():
    split = common.load_split()
    rel = common.split_files(split, "era-c", "heldout")[0]
    with pytest.raises(PermissionError):
        common.read_corpus_text(split, rel)


def test_target_lengths_come_from_split_counts():
    split = common.load_split()
    for p in split["personas"]:
        med = split["personas"][p]["median_doc_words"]["heldout"]
        assert common.target_length(split, p) == max(120, min(400, round(med)))


def test_chunks_have_exact_length_and_do_not_overlap(fresh):
    r, _ = fresh
    split = common.load_split()
    for p, v in r["per_persona"].items():
        chunks = validity.dev_chunks(split, p, v["target_words"])
        assert len(chunks) == v["chunks"] == split["personas"][p]["words"]["dev"] // v["target_words"]
        for c in chunks:
            assert len(common.words(c)) == v["target_words"]


def test_confusion_table_is_complete_and_consistent(fresh):
    r, _ = fresh
    t = r["confusion"]["table"]
    personas = sorted(r["per_persona"])
    assert sorted(t) == personas
    for p in personas:
        assert sorted(t[p]) == personas
        assert sum(t[p].values()) == r["per_persona"][p]["chunks"]
        assert t[p][p] == r["per_persona"][p]["correct"]
    assert sum(sum(row.values()) for row in t.values()) == r["pooled_chunks"]


def test_gate_rule_and_below_chance_flags(fresh):
    r, _ = fresh
    assert r["chance"] == 1.0 / r["k"]
    assert r["threshold"] == 2.0 * r["chance"]
    assert r["passed"] == (r["pooled_accuracy"] >= r["threshold"])
    assert r["primary_in_force"] == ("attribution" if r["passed"] else "fallback_delta_fw")
    for p, v in r["per_persona"].items():
        assert v["below_chance"] == (v["accuracy"] < r["chance"])
    assert r["below_chance_personas"] == sorted(p for p, v in r["per_persona"].items() if v["below_chance"])


def test_saved_result_matches_a_fresh_run(fresh):
    r, _ = fresh
    saved = common.read_json(SAVED)
    for key in ("pooled_accuracy", "pooled_correct", "pooled_chunks", "passed", "primary_in_force",
                "per_persona", "confusion", "below_chance_personas", "k"):
        assert saved[key] == r[key], key
    md = (common.RESULTS / "validity-gate.md").read_text(encoding="utf-8")
    assert md == validity.render_markdown(saved)
    assert "## Confusion table" in md and "## Per persona" in md
