"""Eval task list (AD-006 Tasks)."""
import re

import test_harness_support  # noqa: F401  (puts eval/ on sys.path)
from harness import common, tasks


def test_tasks_json_matches_its_source():
    assert tasks.load() == tasks.build()


def test_eight_tasks_per_persona_and_split():
    doc = tasks.load()
    for p in common.RUN_ORDER:
        for w in ("dev", "heldout"):
            ts = tasks.select(doc, p, w)
            assert len(ts) == common.TASKS_PER_PERSONA
            assert len(set(t["topic"] for t in ts)) == len(ts)


def test_prompts_use_the_template_and_split_lengths():
    split = common.load_split()
    for t in tasks.load()["tasks"]:
        assert t["prompt"] == tasks.render_prompt(t)
        assert t["target_words"] == common.target_length(split, t["persona"])
        assert t["channel"] in tasks.CHANNELS


def test_prompts_name_no_writer_and_no_persona_id():
    prov = (common.CORPUS / "PROVENANCE.md").read_text(encoding="utf-8")
    authors = re.findall(r"^- Author: ([^,\n(]+)", prov, re.M)
    surnames = set()
    for a in authors:
        for w in a.split():
            if w[:1].isupper() and len(w) > 3:
                surnames.add(w.strip(".,").lower())
    assert len(authors) == 6
    for t in tasks.load()["tasks"]:
        low = t["prompt"].lower()
        for s in surnames:
            assert not re.search(r"\b%s\b" % re.escape(s), low), (t["id"], s)
        for p in common.RUN_ORDER:
            assert p not in low


def test_samples_pasted_excerpts_are_train_only_and_fixed():
    split = common.load_split()
    a = tasks.train_excerpts(split, "modern-a")
    assert a == tasks.train_excerpts(split, "modern-a")
    assert len(a) == 3 and all(len(common.words(x)) == tasks.SAMPLES_EXCERPT_WORDS for x in a)
    train = "\n\n".join(common.read_corpus_text(split, f).strip("\n")
                        for f in sorted(common.split_files(split, "modern-a", "train")))
    assert all(x in train for x in a)
