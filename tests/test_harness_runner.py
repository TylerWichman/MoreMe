"""3-arm runner with a fake claude CLI (no model calls)."""
import json

import pytest

import test_harness_support as S
from harness import common, prereg, runner, tasks


def _run(tmp_path, monkeypatch, behavior="ok", persona="era-c", **kw):
    claude, state = S.make_fake(tmp_path, behavior, monkeypatch)
    kwargs = S.run_kwargs(tmp_path, claude, persona)
    kwargs.update(kw)
    tid = S.first_task(persona)
    code = runner.run_batch([persona], "dev", tmp_path / "evidence", tmp_path / "results", task_ids=[tid], **kwargs)
    return code, tid


def test_unit_plan_is_seeded_and_complete():
    a = runner.unit_plan("era-c", "era-c-dev-01")
    assert a == runner.unit_plan("era-c", "era-c-dev-01")
    assert sorted(a) == sorted([("with", 1), ("with", 2), ("without", 1), ("without", 2), ("samples-pasted", 1)])
    orders = set(tuple(runner.unit_plan("era-c", "era-c-dev-%02d" % i)) for i in range(1, 9))
    assert len(orders) > 1  # randomized per task


def test_draft_args_pin_model_and_skip_session_persistence():
    for arm in common.ARMS:
        args = runner.draft_args(arm)
        assert args[:2] == ["--model", "claude-sonnet-5-5"]
        assert "--no-session-persistence" in args
        assert "--strict-mcp-config" in args and "--setting-sources" in args
        assert not any(a == "--allowedTools" for a in args)
    assert "--allowedTools=Skill(my-voice)" in runner.draft_args("with")
    assert not any(a.startswith("--allowedTools") for a in runner.draft_args("without"))


def test_full_task_writes_five_records_with_evidence(tmp_path, monkeypatch):
    code, tid = _run(tmp_path, monkeypatch)
    assert code == runner.EXIT_OK
    recs = runner.load_records(tmp_path / "results")
    assert len(recs) == 5
    by_arm = dict(((r["arm"], r["rep"]), r) for r in recs)
    task_prompt = [t for t in tasks.load()["tasks"] if t["id"] == tid][0]["prompt"]
    assert by_arm[("with", 1)]["prompt"] == task_prompt == by_arm[("without", 2)]["prompt"]
    sp = by_arm[("samples-pasted", 1)]["prompt"]
    assert sp.endswith(task_prompt) and sp.count("Sample ") == 3
    for r in recs:
        assert r["valid"], r["invalid_reasons"]
        assert r["license_header"] == common.license_headers()["era-c"]
        assert r["draft"].startswith("Dear friend")
        assert r["evidence"]["claude_code_version"] == "2.1.303"
    assert by_arm[("with", 1)]["evidence"]["invoked"] is True
    assert by_arm[("without", 1)]["evidence"]["init_skills"] == []
    manifest = json.loads((tmp_path / "results" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["unit_order"][tid] == ["%s-r%d" % u for u in runner.unit_plan("era-c", tid)]
    assert manifest["invocation"]["rate"] == 1.0
    assert manifest["ledger"]["calls"] == 5 and manifest["ledger"]["units_done"] == 5
    positions = sorted(r["position_in_task"] for r in recs)
    assert positions == [1, 2, 3, 4, 5]


def test_records_and_manifest_hold_no_home_paths(tmp_path, monkeypatch):
    _run(tmp_path, monkeypatch)
    for f in (tmp_path / "results").rglob("*.json"):
        text = f.read_text(encoding="utf-8")
        assert str(tmp_path) not in text and str(tmp_path).replace("\\", "\\\\") not in text, f.name


def test_raw_logs_and_ledger_go_to_evidence_dir(tmp_path, monkeypatch):
    _run(tmp_path, monkeypatch)
    assert (tmp_path / "evidence" / "ledger.jsonl").exists()
    assert len(list((tmp_path / "evidence" / "logs").glob("*.jsonl"))) == 5
    assert not list((tmp_path / "results").rglob("*.jsonl"))


def test_invalid_unit_is_rerun_and_counted(tmp_path, monkeypatch):
    code, _ = _run(tmp_path, monkeypatch, "refuse_first")
    assert code == runner.EXIT_OK
    recs = runner.load_records(tmp_path / "results")
    assert all(r["valid"] for r in recs)
    assert all(r["attempt"] == 2 and r["invalid_history"][0]["reasons"] == ["refusal"] for r in recs)
    rows = S.ledger_rows(tmp_path / "evidence" / "ledger.jsonl")
    assert sum(1 for r in rows if r["kind"] == "call") == 10


def test_skill_invariant_violation_invalidates(tmp_path, monkeypatch):
    _run(tmp_path, monkeypatch, "other_skill")
    recs = runner.load_records(tmp_path / "results")
    assert recs and not any(r["valid"] for r in recs)
    assert all(any(x.startswith("skill_invariant") for x in r["invalid_reasons"]) for r in recs)
    assert all(r["attempt"] == 3 for r in recs)
    m = json.loads((tmp_path / "results" / "manifest.json").read_text(encoding="utf-8"))
    assert m["skill_invariant_failures"] >= 5 * 2


def test_usage_limit_stops_cleanly_and_resumes(tmp_path, monkeypatch):
    code, tid = _run(tmp_path, monkeypatch, "limit_after:2")
    assert code == runner.EXIT_LIMIT
    assert len(runner.load_records(tmp_path / "results")) == 2
    monkeypatch.setenv("FAKE_BEHAVIOR", "ok")
    kwargs = S.run_kwargs(tmp_path / "again", S.make_fake(tmp_path, "ok")[0])
    (tmp_path / "again").mkdir(exist_ok=True)
    code = runner.run_batch(["era-c"], "dev", tmp_path / "evidence", tmp_path / "results", task_ids=[tid], **kwargs)
    assert code == runner.EXIT_OK
    recs = runner.load_records(tmp_path / "results")
    assert len(recs) == 5
    rows = S.ledger_rows(tmp_path / "evidence" / "ledger.jsonl")
    done = [r for r in rows if r["kind"] == "done"]
    assert len(done) == 5 and len(set(r["unit"] for r in done)) == 5
    assert sum(1 for r in done if r["interrupted_rerun"]) == 1  # the unit whose call hit the limit


def test_heldout_refused_while_preregistration_is_draft(tmp_path, monkeypatch):
    claude, _ = S.make_fake(tmp_path, "ok", monkeypatch)
    # The real file is frozen once the eval starts; check the refusal against a draft copy.
    draft = tmp_path / "PREREGISTRATION.md"
    draft.write_text(prereg.common.PREREG.read_text(encoding="utf-8").replace("status: frozen", "status: draft"),
                     encoding="utf-8")
    monkeypatch.setattr(prereg.common, "PREREG", draft)
    with pytest.raises(prereg.PreregError):
        runner.run_batch(["era-c"], "heldout", tmp_path / "evidence", tmp_path / "results",
                         **S.run_kwargs(tmp_path, claude))
    assert not (tmp_path / "evidence" / "ledger.jsonl").exists()


def test_rejection_blocks_only_until_reset():
    rej = [{"rate_limit_info": [{"status": "rejected", "resetsAt": 1000}]}]
    assert not runner.window_ok(rej, now=999)[0]
    assert runner.window_ok(rej, now=1000)[0]
    no_reset = [{"rate_limit_info": [{"status": "rejected"}]}]
    assert not runner.window_ok(no_reset, now=10 ** 12)[0]


def test_seven_day_window_check():
    full = [{"rate_limit_info": [{"status": "allowed", "unifiedWindows": {"seven_day": {"utilization": 0.95}}}]}]
    ok = [{"rate_limit_info": [{"status": "allowed", "unifiedWindows": {"seven_day": {"utilization": 0.39}}}]}]
    rej = [{"rate_limit_info": [{"status": "rejected"}]}]
    assert runner.window_ok([])[0]
    assert runner.window_ok(ok)[0]
    assert not runner.window_ok(full)[0]
    assert not runner.window_ok(rej)[0]


def test_window_full_refuses_to_start(tmp_path, monkeypatch):
    ev = tmp_path / "evidence"
    ev.mkdir()
    row = {"kind": "call", "rate_limit_info": [{"status": "allowed",
                                                "unifiedWindows": {"seven_day": {"utilization": 0.97}}}]}
    (ev / "ledger.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    code, _ = _run(tmp_path, monkeypatch)
    assert code == runner.EXIT_WINDOW
    assert not (tmp_path / "results" / "drafts").exists()


def test_explicit_mode_prefixes_have_matched_length():
    assert len(tasks.EXPLICIT_PREFIX) == len(tasks.NEUTRAL_PREFIX)
    p = "Write a note."
    assert tasks.arm_prompt(p, "with", "explicit") == "Use my-voice skill: Write a note."
    assert tasks.arm_prompt(p, "without", "explicit") == "Please do the task: Write a note."
    assert tasks.arm_prompt(p, "without", "auto") == p
