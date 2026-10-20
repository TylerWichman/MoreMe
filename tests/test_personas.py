"""Invented persona first names (eval/lib/personas.py)."""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "eval"))
from lib import personas  # noqa: E402


def test_every_eval_persona_has_a_first_name():
    split = json.loads((REPO / "eval" / "split.json").read_text(encoding="utf-8"))
    assert set(personas.PERSONA_FIRST_NAMES) == set(split["personas"])
    names = list(personas.PERSONA_FIRST_NAMES.values())
    assert len(set(names)) == len(names)
    for n in names:
        assert re.match(r"^[A-Z][a-z]+$", n)


def test_names_are_not_the_real_writers_names():
    prov = (REPO / "eval" / "corpus" / "PROVENANCE.md").read_text(encoding="utf-8")
    author_words = set()
    for line in prov.splitlines():
        if line.startswith("- Author:"):
            author_words |= set(re.findall(r"[A-Za-z]+", line.split(",")[0]))
    assert len(author_words) > 6, "author lines not found"
    for n in personas.PERSONA_FIRST_NAMES.values():
        assert n not in author_words


def test_name_rule_text():
    rule = personas.name_rule("era-c")
    assert rule.startswith("- Your first name is Hattie.")
    assert "sign it Hattie" in rule
