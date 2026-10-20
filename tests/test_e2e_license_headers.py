"""Corpus license headers on e2e artifacts and the example run (LICENSE-CORPUS rule 3).

Every committed text file of an e2e run (eval/e2e/runs/<run>/, except the
safety check, which holds no corpus text) carries the header of the run's
persona from eval/corpus/licenses.json, and every text file under
docs/example-run/ carries a persona header. tests/test_corpus_license_headers.py
covers eval/ for non-public-domain personas; this file adds the public-domain
e2e persona and docs/example-run.
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "eval"))
from lib import artifacts  # noqa: E402

LICENSES = json.loads((REPO / "eval" / "corpus" / "licenses.json").read_text(encoding="utf-8"))["personas"]
TEXT = {".md", ".txt", ".json", ".jsonl"}
RUNS = REPO / "eval" / "e2e" / "runs"


def run_dirs():
    return sorted(d for d in RUNS.iterdir() if (d / "manifest.json").exists()) if RUNS.exists() else []


@pytest.mark.parametrize("run", run_dirs(), ids=lambda d: d.name)
def test_e2e_run_files_carry_persona_header(run):
    persona = json.loads((run / "manifest.json").read_text(encoding="utf-8"))["persona"]
    header = LICENSES[persona]["header"]
    missing = [f.name for f in sorted(run.rglob("*")) if f.is_file() and f.suffix in TEXT
               and header not in f.read_text(encoding="utf-8", errors="replace")]
    assert not missing, "%s files without the %s header: %s" % (run.name, persona, missing)


def test_example_run_files_carry_a_persona_header():
    root = REPO / "docs" / "example-run"
    if not root.exists():
        pytest.skip("no example run yet")
    headers = [m["header"] for m in LICENSES.values()]
    missing = [f.relative_to(REPO).as_posix() for f in sorted(root.rglob("*")) if f.is_file()
               and f.suffix in TEXT and not any(h in f.read_text(encoding="utf-8", errors="replace") for h in headers)]
    assert not missing, "files without a corpus license header: %s" % missing


def test_add_license_header_keeps_frontmatter_first():
    skill = "---\nname: my-voice\ndescription: x\n---\n\n# My voice\n"
    out = artifacts.add_license_header(skill, "HDR")
    assert out.startswith("---\nname: my-voice\ndescription: x\n---\n")
    assert "<!-- HDR -->" in out and out.index("<!-- HDR -->") > out.index("\n---\n")
    assert artifacts.add_license_header(out, "HDR") == out
    assert artifacts.add_license_header("plain\n", "HDR") == "<!-- HDR -->\n\nplain\n"
