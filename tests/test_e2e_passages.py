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


def test_spans_are_whole_sentences_within_word_limits():
    sents = ["Sentence number %d is here." % i for i in range(40)]
    text = "Short paragraph one.\n\n" + " ".join(sents) + "\n\nLast one.\n"
    spans = drv.passage_spans(text, min_words=12, max_words=20)
    pieces = [text[a:b] for a, b in spans]
    assert pieces
    for piece in pieces:
        assert 12 <= len(piece.split()) <= 20
        assert piece.rstrip().endswith((".", "!", "?"))
        assert text.count(piece) == 1
    # A passage may cross a paragraph break; the break stays as written.
    assert pieces[0].startswith("Short paragraph one.\n\nSentence number 0")


def test_catalog_passages_are_60_to_100_words():
    ws = [c["words"] for c in drv.passage_catalog("era-c", SPLIT)]
    assert len(ws) >= 30
    assert min(ws) >= drv.PASSAGE_MIN_WORDS and max(ws) <= drv.PASSAGE_MAX_WORDS
    assert (drv.PASSAGE_MIN_WORDS, drv.PASSAGE_MAX_WORDS) == (60, 100)


def test_sample_composition_rule():
    turns = [
        {"role": "skill", "steps_done": []},
        {"role": "interviewee", "answer": "one two three four five", "answer_kind": "in_role"},
        {"role": "skill", "steps_done": ["1"]},
        {"role": "interviewee", "answer": " ".join(["w"] * 80), "answer_kind": "passages"},
        {"role": "skill", "steps_done": []},
        {"role": "interviewee", "answer": " ".join(["w"] * 70), "answer_kind": "passages"},
        {"role": "skill", "steps_done": ["2", "3"]},
        {"role": "interviewee", "answer": "Yes, that sounds like me, more or less.", "answer_kind": "in_role"},
    ]
    c = drv.sample_composition(turns)
    assert (c["corpus_words"], c["roleplay_words"]) == (150, 5)
    assert c["meets_rule"] and c["corpus_share"] == round(150 / 155.0, 3)
    turns[1]["answer"] = " ".join(["x"] * 60)
    c = drv.sample_composition(turns)
    assert c["corpus_share"] == round(150 / 210.0, 3) and not c["meets_rule"]
    assert drv.CORPUS_SHARE_MIN == 0.75


def test_brief_keeps_interview_answers_short_and_one_passage():
    brief = drv.interviewee_brief("era-c")
    # Tightened by T-007 from "about 15": r6 met the corpus-share rule by 0.002.
    assert drv.ANSWER_CAP_WORDS == 10
    assert "one short sentence of 10 words at most" in brief
    assert "about 15 words" not in brief
    assert "the id of the one passage that best answers it" in brief and "old quotation" in brief
    assert "For every topic question and follow-up" in brief


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
