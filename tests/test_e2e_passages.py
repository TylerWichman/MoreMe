"""AMEND-003 interviewee: writing prompts are answered with verbatim train-split
passages (eval/e2e/run_moreme.py), no model calls."""
import importlib.util
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "eval"))
spec = importlib.util.spec_from_file_location("run_moreme_p", str(REPO / "eval" / "e2e" / "run_moreme.py"))
drv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drv)

SPLIT = json.loads((REPO / "eval" / "split.json").read_text(encoding="utf-8"))


def test_spans_are_whole_paragraphs_or_sentences():
    text = ("Short paragraph one.\n\n" + " ".join("Sentence number %d is here." % i for i in range(40))
            + "\n\nLast one.\n")
    spans = drv.passage_spans(text, max_words=30)
    pieces = [text[a:b] for a, b in spans]
    assert pieces[0] == "Short paragraph one."
    assert pieces[-1] == "Last one."
    for p in pieces[1:-1]:
        assert len(p.split()) <= 30
        assert p.startswith("Sentence number") and p.endswith("here.")
    joined = " ".join(pieces[1:-1])
    assert joined == " ".join("Sentence number %d is here." % i for i in range(40))


def test_catalog_is_verbatim_train_text_with_exact_spans():
    cat = drv.passage_catalog("era-c", SPLIT)
    assert len(cat) > 20
    train = set(d["file"] for d in SPLIT["personas"]["era-c"]["documents"] if d["split"] == "train")
    for c in cat:
        assert c["file"] in train
        src = (REPO / "eval" / "corpus" / c["file"]).read_text(encoding="utf-8")
        assert src[c["start"]:c["end"]] == c["text"]
        assert c["words"] <= drv.PASSAGE_MAX_WORDS or "\n" not in c["text"].strip()
    assert len(set(c["id"] for c in cat)) == len(cat)


def test_catalog_never_names_the_real_writer():
    words = drv.author_words("era-c")
    assert words
    for c in drv.passage_catalog("era-c", SPLIT):
        assert not drv.names_author(c["text"], words)
    assert drv.names_author("Signed, " + words[0], words)
    assert not drv.names_author("Mr. " + words[-1] + " came by.", words)


def test_resolve_answer_passages_and_in_role():
    cat = drv.passage_catalog("era-c", SPLIT)
    text, prov, err = drv.resolve_answer("USE: p2, p5", cat)
    assert err is None
    assert text == cat[1]["text"].strip() + "\n\n" + cat[4]["text"].strip()
    assert [p["id"] for p in prov] == ["p2", "p5"]
    assert set(prov[0]) == {"id", "file", "start", "end", "words"}
    text, prov, err = drv.resolve_answer("Warm, chatty, and funny.", cat)
    assert (text, prov, err) == ("Warm, chatty, and funny.", None, None)


def test_resolve_answer_rejects_bad_or_reused_ids():
    cat = drv.passage_catalog("era-c", SPLIT)
    assert drv.resolve_answer("USE: p9999", cat)[2].startswith("unknown")
    assert drv.resolve_answer("USE: p2", cat, used=["p2"])[2].startswith("passages already used")
    assert drv.resolve_answer("USE: none", cat)[2]


def test_prompt_lists_used_ids_and_correction():
    prompt = drv.interviewee_prompt("BRIEF", [("user", "hi")], "Write a story.", ["p1", "p3"], "unknown ids")
    assert "Passages you already used: p1, p3." in prompt
    assert "could not be used (unknown ids)" in prompt


def test_banner_discloses_sample_method():
    assert "verbatim passages" in drv.SAMPLE_METHOD and "never reworded" in drv.SAMPLE_METHOD
    src = (REPO / "eval" / "e2e" / "run_moreme.py").read_text(encoding="utf-8")
    assert re.search(r'm\.get\("sample_method"\)', src)
