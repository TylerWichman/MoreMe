"""Stream-json invocation evidence and the per-call skill invariant over
committed logs and draft records (AD-006)."""
import json

import pytest

import test_harness_support as S
from harness import evidence

INIT = {"type": "system", "subtype": "init", "skills": ["my-voice"], "plugins": [], "mcp_servers": [],
        "claude_code_version": "2.1.303", "model": "claude-sonnet-5-5"}


def use(skill, tid="t1", parent=None):
    return {"type": "assistant", "parent_tool_use_id": parent,
            "message": {"content": [{"type": "tool_use", "id": tid, "name": "Skill", "input": {"skill": skill}}]}}


def result(tid="t1", err=False):
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "is_error": err,
                                                     "content": "x"}]}}


def text(t):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": t}]}}


def test_invoked_main_thread_ok():
    ev = evidence.unit_evidence([INIT, use("my-voice"), result(), text("Hi")], "with")
    assert ev["invoked"] and ev["problems"] == [] and ev["skill_calls"] == ["my-voice"]


def test_not_invoked_or_errored():
    assert evidence.invocation([INIT, text("Hi")]) == (False, "no_skill_tool_use")
    assert evidence.invocation([INIT, use("my-voice"), result(err=True)])[0] is False
    assert evidence.invocation([INIT, use("my-voice", parent="p1"), result()])[0] is False


def test_other_skill_breaks_invariant_and_tools_must_be_skill_only():
    ev = evidence.unit_evidence([INIT, use("my-voice"), result(), use("other", "t2")], "with")
    assert ev["invariant_violations"] == ["other"]
    assert any(p.startswith("skill_invariant") for p in ev["problems"])
    bash = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "b", "name": "Bash", "input": {}}]}}
    ev2 = evidence.unit_evidence([INIT, bash], "with")
    assert any(p.startswith("tools_not_subset_of_skill") for p in ev2["problems"])


def test_without_arm_expects_no_skills():
    init = dict(INIT, skills=[])
    ev = evidence.unit_evidence([init, text("Hi")], "without")
    assert ev["problems"] == [] and ev["invoked"] is False
    ev2 = evidence.unit_evidence([INIT, text("Hi")], "without")
    assert any(p.startswith("init:") for p in ev2["problems"])


def test_invocation_rate():
    recs = [{"arm": "with", "valid": True, "evidence": {"invoked": True}},
            {"arm": "with", "valid": True, "evidence": {"invoked": False}},
            {"arm": "with", "valid": False, "evidence": {"invoked": False}},
            {"arm": "without", "valid": True, "evidence": {"invoked": False}}]
    assert evidence.invocation_rate(recs) == (0.5, 1, 2)


def test_skill_invariant_over_committed_draft_records():
    recs = list((S.EVAL / "results").glob("**/drafts/*.json"))
    if not recs:
        pytest.skip("no committed harness drafts yet (Phase 1 dev smoke not run)")
    for f in recs:
        r = json.loads(f.read_text(encoding="utf-8"))
        allowed = evidence.allowed_skills(r["arm"])
        assert set(r["evidence"]["skill_calls"]) <= allowed or not r["valid"], f.name
        if r["valid"]:
            assert r["evidence"]["invariant_violations"] == [] and r["evidence"]["problems"] == [], f.name


def test_skill_invariant_over_committed_stream_json_logs():
    """Committed stream-json logs: e2e and persona-generation runs may call
    moreme, and my-voice during stages 5-6; nothing else."""
    from lib import childrun
    logs = [p for p in (S.EVAL / "e2e" / "runs").glob("*/logs/*.jsonl")]
    logs += [p for p in (S.EVAL / "results").glob("**/logs/*.jsonl")]
    import os
    from pathlib import Path
    extra = os.environ.get("MOREME_EVIDENCE_DIR")  # raw logs kept outside the repo (AMEND-002)
    if extra:
        logs += list(Path(extra).glob("**/logs/*.jsonl"))
    if not logs:
        pytest.skip("no committed stream-json logs in the repo (raw logs live outside it, AMEND-002)")
    for p in logs:
        events = childrun.parse_events(p.read_text(encoding="utf-8"))
        bad = evidence.invariant_over_log(events, {"moreme", "my-voice"})
        assert not bad, "%s: %s" % (p.name, bad)
