"""Every derived file of a non-public-domain persona carries that persona's license header (AD-006).

Derived files live outside eval/corpus/ and eval/sourcing/. A file belongs to a
persona when a folder in its path is named after the persona or its file name
starts with the persona ID. Until T-006/T-007 write such files this test has
nothing to check beyond the self-test of the matcher.
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EVAL = REPO / "eval"
LICENSES = json.loads((EVAL / "corpus" / "licenses.json").read_text(encoding="utf-8"))["personas"]
NON_PD = {p: m for p, m in LICENSES.items() if not m["public_domain"]}
SKIP_DIRS = {"corpus", "sourcing", "__pycache__"}
TEXT_SUFFIXES = {".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".tmpl", ".csv"}


def owner(rel):
    """Persona IDs a path belongs to by the folder/file-name rule."""
    parts = rel.parts
    hits = set()
    for pid in NON_PD:
        if pid in parts[:-1] or parts[-1].startswith(pid):
            hits.add(pid)
    return hits


def derived_files():
    for f in EVAL.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in TEXT_SUFFIXES:
            continue
        rel = f.relative_to(EVAL)
        if rel.parts[0] in SKIP_DIRS:
            continue
        pids = owner(rel)
        if pids:
            yield f, pids


def test_owner_rule_self_check():
    assert owner(Path("skills/modern-b/SKILL.md")) == {"modern-b"}
    assert owner(Path("results/drafts/modern-a-task3-with-1.json")) == {"modern-a"}
    assert owner(Path("results/drafts/era-c-task3-with-1.json")) == set()
    assert owner(Path("split.json")) == set()


def test_non_public_domain_derived_files_carry_header():
    missing = []
    for f, pids in derived_files():
        text = f.read_text(encoding="utf-8", errors="replace")
        for pid in pids:
            if NON_PD[pid]["header"] not in text:
                missing.append("%s lacks the %s header" % (f.relative_to(REPO), pid))
    assert not missing, "\n".join(missing)
