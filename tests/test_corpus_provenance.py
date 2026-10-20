"""PROVENANCE.md and LICENSE-CORPUS.md cover every corpus document (AD-006)."""
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CORPUS = REPO / "eval" / "corpus"
PROVENANCE = (CORPUS / "PROVENANCE.md").read_text(encoding="utf-8")
LICENSE_CORPUS = (CORPUS / "LICENSE-CORPUS.md").read_text(encoding="utf-8")
LICENSES = json.loads((CORPUS / "licenses.json").read_text(encoding="utf-8"))["personas"]
PERSONAS = sorted(p.name for p in CORPUS.iterdir() if p.is_dir())
ROW = re.compile(r"^\| `(corpus/[^`]+)` \| (\S+) \| (.*?) \| (.*?) \| (.*?) \| (\d+) \| (.+) \|$", re.M)
LICENSE_LABEL = {"OGL-3.0": "OGL v3.0", "CC-BY-SA-4.0": "CC BY-SA 4.0", "US-PD": "Public domain (USA)"}
WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*")


def rows():
    return {m.group(1): m.groups() for m in ROW.finditer(PROVENANCE)}


def section(pid):
    return PROVENANCE.split("## %s\n" % pid, 1)[1].split("\n## ", 1)[0]


def test_every_document_has_exactly_one_row_and_every_row_a_file():
    found = [m.group(1) for m in ROW.finditer(PROVENANCE)]
    assert len(found) == len(set(found))
    files = sorted("corpus/%s/%s" % (p.parent.name, p.name) for p in CORPUS.glob("*/*.txt"))
    assert sorted(found) == files


def test_row_fields_are_filled_and_license_matches_persona():
    for path, (_, url, title, date, lic, words, attrib) in rows().items():
        pid = path.split("/")[1]
        assert url.startswith("https://"), path
        assert title.strip() and date.strip() and attrib.strip(), path
        assert lic == LICENSE_LABEL[LICENSES[pid]["license"]], path
        text = (CORPUS.parent / path).read_text(encoding="utf-8").replace("’", "'").replace("‘", "'")
        assert int(words) == len(WORD.findall(text)), path
        if LICENSES[pid]["license"] == "OGL-3.0":
            assert "Contains public sector information licensed under the Open Government Licence v3.0" in attrib
        if LICENSES[pid]["license"] == "CC-BY-SA-4.0":
            assert "CC BY-SA 4.0" in attrib and url in attrib and title in attrib
        if LICENSES[pid]["license"] == "US-PD":
            assert "Public domain in the USA" in attrib


@pytest.mark.parametrize("pid", PERSONAS)
def test_persona_section_records_source_license_evidence_and_changes(pid):
    sec = section(pid)
    for field in ("- Era:", "- Register:", "- Author:", "- License:", "- Changes made (every document):",
                  "- Attribution template:"):
        assert field in sec, (pid, field)
    assert re.search(r"(License evidence|US public domain basis):.*checked.*\d{4}-\d{2}-\d{2}", sec, re.I | re.S), pid
    if LICENSES[pid]["license"] == "US-PD":
        assert "Public domain in the USA." in sec
        assert "Project Gutenberg header, footer, and license" in sec
        assert re.search(r"published[^\n]*1[89]\d\d", sec), pid


def test_license_corpus_separates_code_and_lists_derived_paths():
    assert "MIT license" in LICENSE_CORPUS and "code only" in LICENSE_CORPUS
    for path in ("eval/skills/<persona-id>/", "eval/results/", "docs/transcript-e2e.md", "docs/example-run/"):
        assert path in LICENSE_CORPUS, path
    for pid in PERSONAS:
        assert "`%s`" % pid in LICENSE_CORPUS
        assert "eval/corpus/%s/" % pid in LICENSE_CORPUS


def test_headers_name_license_and_persona_only():
    for pid, meta in LICENSES.items():
        h = meta["header"]
        assert "(persona %s)" % pid in h and "eval/corpus/PROVENANCE.md" in h
        if meta["license"] == "OGL-3.0":
            assert "Contains public sector information licensed under the Open Government Licence v3.0" in h
        elif meta["license"] == "CC-BY-SA-4.0":
            assert "CC BY-SA 4.0" in h and "this file is licensed under CC BY-SA 4.0" in h
        else:
            assert "public domain in the USA" in h
