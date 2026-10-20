"""Eval corpus layout, persona mix, file hygiene, and name isolation (AD-006)."""
import json
import os
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
EVAL = REPO / "eval"
CORPUS = EVAL / "corpus"
LICENSES = json.loads((CORPUS / "licenses.json").read_text(encoding="utf-8"))["personas"]
PERSONAS = sorted(p.name for p in CORPUS.iterdir() if p.is_dir())
PROVENANCE = (CORPUS / "PROVENANCE.md").read_text(encoding="utf-8")


def corpus_files():
    return sorted(CORPUS.glob("*/*.txt"))


def author_names():
    names = re.findall(r"^- Author: ([^,\n]+)", PROVENANCE, re.M)
    assert len(names) == len(PERSONAS)
    return [n.strip() for n in names]


def test_persona_count_and_mix():
    assert len(PERSONAS) >= 4
    assert sorted(LICENSES) == PERSONAS
    modern = [p for p in PERSONAS if LICENSES[p]["era"] == "modern"]
    assert len(modern) >= 2
    for p in modern:
        assert LICENSES[p]["license"] in ("OGL-3.0", "CC-BY-SA-4.0", "US-PD")
    for p in PERSONAS:
        if LICENSES[p]["era"] != "modern":
            assert LICENSES[p]["license"] == "US-PD"


def test_one_demo_persona_and_it_is_public_domain():
    demo = [p for p in PERSONAS if LICENSES[p]["demo_candidate"]]
    assert len(demo) == 1
    assert LICENSES[demo[0]]["license"] == "US-PD" and LICENSES[demo[0]]["public_domain"] is True
    assert "Demo persona: yes" in PROVENANCE.split("## %s\n" % demo[0])[1].split("\n## ")[0]


@pytest.mark.parametrize("pid", PERSONAS)
def test_persona_folder_holds_only_text_documents(pid):
    entries = sorted(os.listdir(str(CORPUS / pid)))
    assert entries, pid
    for e in entries:
        assert re.fullmatch(r"%s-\d{2}\.txt" % re.escape(pid), e), e


def test_files_are_clean_utf8_without_bom_or_crlf():
    for f in corpus_files():
        raw = f.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), f
        assert b"\r" not in raw, f
        text = raw.decode("utf-8")
        assert text.strip(), f
        assert text.endswith("\n") and not text.endswith("\n\n\n"), f


def test_no_gutenberg_marks_or_markup_left():
    bad = re.compile(r"gutenberg|\*\*\* ?(START|END) OF|\[Illustration|\[Footnote|FOOTNOTE|<[a-z]+[ >/]|&[a-z]+;|_[A-Za-z]",
                     re.I)
    for f in corpus_files():
        m = bad.search(f.read_text(encoding="utf-8"))
        assert m is None, (f, m.group(0) if m else None)


def test_author_names_stay_out_of_names_and_metadata():
    names = author_names()
    surnames = [n.split()[-1].lower() for n in names]
    for path in list(CORPUS.rglob("*")) + list((EVAL / "skills").rglob("*") if (EVAL / "skills").exists() else []):
        low = str(path.relative_to(EVAL)).lower()
        for s in surnames:
            assert s not in low, path
    for meta in ("split.json", "corpus/licenses.json", "corpus/LICENSE-CORPUS.md", "reference_stats.json",
                 "distinctness.json"):
        p = EVAL / meta
        if p.exists():
            text = p.read_text(encoding="utf-8")
            for n in names:
                assert n not in text, (meta, n)


def test_documents_do_not_sign_off_with_the_author_name():
    names = author_names()
    for f in corpus_files():
        lines = [ln for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
        tail = " ".join(lines[-2:])
        for n in names:
            assert n not in tail, f
