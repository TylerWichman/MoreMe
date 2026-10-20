"""Pre-registered draft extraction and the invalid-unit detector (AD-006).

Unit cases run always. The committed-draft check runs over every harness draft
record under eval/results/ (the Phase 1 dev smoke writes them)."""
from pathlib import Path

import pytest

import test_harness_support as S
from harness import extraction

X = extraction.extract_draft


def test_plain_text_is_kept():
    assert X("Dear Sam,\n\nThe beans are up.\n") == "Dear Sam,\n\nThe beans are up."


@pytest.mark.parametrize("lead", [
    "Here's the email:", "Here’s a short blog post about weeds:", "Sure, here is the note:",
    "Certainly. Here's a draft.", "Below is the post:", "I've written the email below:", "OK, here are my thoughts:",
])
def test_single_line_preamble_is_dropped(lead):
    assert X(lead + "\n\nDear Sam,\nThe beans are up.") == "Dear Sam,\nThe beans are up."


def test_rule_after_preamble_is_dropped_but_not_without_preamble():
    assert X("Here's the note:\n---\nHi.") == "Hi."
    assert X("---\nHi.") == "---\nHi."


def test_only_the_first_line_can_be_a_preamble():
    text = "Dear Sam,\nHere's the thing:\nthe beans are up."
    assert X(text) == text


def test_preamble_must_be_a_lead_in_line():
    assert X("Here is where I grew up, a small town.\nMore.") == "More."  # ends in '.', matches
    assert X("Here is where I grew up, a small town by the river and") .startswith("Here is")


def test_code_fence_lines_are_dropped_and_content_kept():
    assert X("Here's the email:\n```\nSubject: Hello\n\nHi Sam.\n```") == "Subject: Hello\n\nHi Sam."
    assert X("~~~markdown\nHi\n~~~") == "Hi"


def test_crlf_input():
    assert X("Here's the note:\r\n\r\nHi.\r\nBye.") == "Hi.\nBye."


def test_empty_and_none():
    assert X("") == "" and X(None) == ""
    assert X("```\n```") == ""


def test_invalid_detector():
    inv = extraction.invalid_reasons
    assert inv("", "") == ["empty"]
    assert inv("I can't help with that.", "I can't help with that.") == ["refusal"]
    assert inv("I couldn't find the my-voice skill, so here is a draft.", "x") == ["missing_skill"]
    assert inv("The my-voice skill is not installed.", "x") == ["missing_skill"]
    assert inv("Dear Sam, I can help with the garden.", "Dear Sam") == []


def test_check_extracted():
    assert extraction.check_extracted("Hi") == []
    assert "code_fence_left" in extraction.check_extracted("Hi\n```")
    assert "preamble_left" in extraction.check_extracted("Here's the note:\nHi")
    assert extraction.check_extracted("  ") == ["empty"]


def _committed_records():
    import json
    out = []
    for f in sorted((S.EVAL / "results").glob("**/drafts/*.json")):
        out.append((f, json.loads(f.read_text(encoding="utf-8"))))
    return out


def test_committed_dev_drafts_follow_the_rule():
    recs = _committed_records()
    if not recs:
        pytest.skip("no committed harness drafts yet (Phase 1 dev smoke not run)")
    invalid = 0
    for f, r in recs:
        assert r["split"] == "dev", "%s: no held-out drafts in Phase 1" % f.name
        assert X(r["final_message"]) == r["draft"], f.name
        flagged = extraction.invalid_reasons(r["final_message"], r["draft"])
        if r["valid"]:
            assert extraction.check_extracted(r["draft"]) == [], f.name
            assert not flagged, f.name
        else:
            invalid += 1
            assert r["invalid_reasons"], f.name
    manifests = list((S.EVAL / "results").glob("**/manifest.json"))
    assert manifests
    import json
    assert sum(json.loads(m.read_text(encoding="utf-8"))["invalid_units"] for m in manifests) == invalid
