"""License-header coverage for corpus-derived files, by content (AD-006).

tests/test_corpus_license_headers.py matches derived files by path name. This
test looks at content: any text file under eval/ (outside eval/corpus/ and
eval/sourcing/) or docs/ that shares a 12-word shingle with a persona's corpus
text must carry that persona's header line from eval/corpus/licenses.json.
It also checks that every harness draft record and generated persona skill
carries its own persona's header, and that LICENSE-CORPUS.md lists the derived
paths the harness writes.
"""
import json
from pathlib import Path

import pytest

import test_harness_support  # noqa: F401  (puts eval/ on sys.path)
from harness import common, leakage

SKIP = {"corpus", "sourcing", "__pycache__"}
SUFFIXES = {".md", ".txt", ".json", ".jsonl", ".csv", ".tmpl"}


@pytest.fixture(scope="module")
def persona_shingles():
    """{persona: shingles of all its corpus text}; held-out included because a
    leak of held-out text into a repo file needs a header just the same."""
    split = common.load_split()
    out = {}
    for p in split["personas"]:
        s = set()
        for d in split["personas"][p]["documents"]:
            s |= leakage.shingles(common.read_corpus_text(split, d["file"], allow=("train", "dev", "heldout")))
        out[p] = s
    return out


def derived_candidates():
    for f in common.EVAL.rglob("*"):
        if f.is_file() and f.suffix.lower() in SUFFIXES and f.relative_to(common.EVAL).parts[0] not in SKIP:
            yield f
    for f in (common.REPO / "docs").rglob("*"):
        if f.is_file() and f.suffix.lower() in SUFFIXES:
            yield f


def _missing(persona_shingles, personas, files):
    headers = common.license_headers()
    missing = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        s = leakage.shingles(text)
        if not s:
            continue
        for p in personas:
            if len(s & persona_shingles[p]) >= 2 and headers[p] not in text:
                missing.append("%s holds %s text but lacks its header" % (f.relative_to(common.REPO).as_posix(), p))
    return missing


def test_every_file_with_non_pd_corpus_text_carries_the_matching_header(persona_shingles):
    """Binding rule (AD-006, Phase 1 exit): every file holding OGL or CC BY-SA
    persona text carries that persona's header, anywhere under eval/ and docs/."""
    lic = common.read_json(common.LICENSES_JSON)["personas"]
    non_pd = [p for p, m in lic.items() if not m["public_domain"]]
    assert non_pd
    missing = _missing(persona_shingles, non_pd, list(derived_candidates()))
    assert not missing, "\n".join(missing)


def test_harness_outputs_carry_headers_for_every_persona(persona_shingles):
    """Files the harness writes (eval/results/, eval/skills/) carry the header of
    every persona whose text they hold, public-domain personas included."""
    files = [f for f in derived_candidates()
             if f.relative_to(common.REPO).as_posix().startswith(("eval/results/", "eval/skills/"))]
    missing = _missing(persona_shingles, sorted(persona_shingles), files)
    assert not missing, "\n".join(missing)


def test_harness_draft_records_carry_their_persona_header():
    headers = common.license_headers()
    for f in common.RESULTS.glob("**/drafts/*.json"):
        r = json.loads(f.read_text(encoding="utf-8"))
        assert r["license_header"] == headers[r["persona"]], f.name
        assert f.name.startswith(r["persona"] + "-"), f.name


def test_generated_persona_skills_carry_their_header():
    headers = common.license_headers()
    for d in common.SKILLS.glob("*") if common.SKILLS.exists() else []:
        if d.is_dir() and d.name in headers:
            for f in d.rglob("*"):
                if f.is_file() and f.suffix.lower() in SUFFIXES:
                    assert headers[d.name] in f.read_text(encoding="utf-8", errors="replace"), f


def test_detector_would_flag_an_unheaded_modern_b_file(tmp_path, persona_shingles):
    split = common.load_split()
    rel = common.split_files(split, "modern-b", "train")[0]
    text = " ".join(common.read_corpus_text(split, rel).split()[:60])
    s = leakage.shingles(text)
    assert len(s & persona_shingles["modern-b"]) >= 2
    assert common.license_headers()["modern-b"] not in text


def test_license_corpus_lists_harness_derived_paths():
    lc = (common.CORPUS / "LICENSE-CORPUS.md").read_text(encoding="utf-8")
    assert "eval/skills/<persona-id>/" in lc
    assert "eval/results/" in lc
