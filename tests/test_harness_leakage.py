"""Physical leakage control: scratch asserts and the 12-word shingle test (AD-006)."""
import shutil

import pytest

import test_harness_support as S
from harness import common, leakage

cr = common.childrun


def test_shingles_are_12_words_and_case_insensitive():
    assert leakage.shingles("a b c d e f g h i j k") == set()
    s = leakage.shingles("One two three four five six seven eight nine ten eleven twelve thirteen")
    assert len(s) == 2
    assert s == leakage.shingles("ONE two three four five six seven eight nine ten eleven twelve thirteen")


def test_scan_texts_finds_a_copied_sentence():
    doc = {"d": leakage.shingles("the quick brown fox jumps over the lazy dog and runs far away home")}
    hits = leakage.scan_texts([("x", "Note: the quick brown fox jumps over the lazy dog and runs far away.")], doc)
    assert hits and hits[0][0] == "x"
    assert leakage.scan_texts([("y", "an unrelated sentence about beans and peas in the garden today")], doc) == []


def test_draft_scratch_rejects_dev_file_and_extras(tmp_path):
    split = common.load_split()
    d = cr.make_scratch("moreme-eval", "leak-test", base=tmp_path)
    leakage.assert_draft_scratch(d, split, "without")
    dev = common.split_files(split, "era-c", "dev")[0]
    shutil.copyfile(str(common.CORPUS / dev), str(d / "renamed.txt"))
    with pytest.raises(cr.ScratchError):
        leakage.assert_draft_scratch(d, split, "without")
    (d / "renamed.txt").unlink()
    (d / "notes.txt").write_text("hello", encoding="utf-8")
    with pytest.raises(cr.ScratchError):
        leakage.assert_draft_scratch(d, split, "without")


def test_with_arm_allows_only_the_skill(tmp_path):
    split = common.load_split()
    d = cr.make_scratch("moreme-eval", "leak-with", skills={"my-voice": S.fake_skill(tmp_path)}, base=tmp_path)
    leakage.assert_draft_scratch(d, split, "with")
    with pytest.raises(cr.ScratchError):
        leakage.assert_draft_scratch(d, split, "without")


def test_no_heldout_shingle_in_committed_artifacts():
    """Generated skills, transcripts, run records, and draft prompts share no
    12-word shingle with any held-out document (digests only, no text printed)."""
    split = common.load_split()
    docs = leakage.corpus_shingles(split, ("heldout",))
    assert len(docs) == sum(p["doc_count"]["heldout"] for p in split["personas"].values())
    targets = list(leakage.leakage_targets())
    hits = leakage.scan_files(targets, docs)
    assert not hits, hits


def test_shingle_scan_would_catch_heldout_text(tmp_path):
    split = common.load_split()
    docs = leakage.corpus_shingles(split, ("heldout",))
    rel = common.split_files(split, "era-d", "heldout")[0]
    excerpt = " ".join(common.read_corpus_text(split, rel, allow=("heldout",)).split()[100:140])
    f = tmp_path / "leaky.txt"
    f.write_text("prompt with " + excerpt, encoding="utf-8")
    hits = leakage.scan_files([f], docs)
    assert any(doc == rel for _f, doc, _k in hits)
