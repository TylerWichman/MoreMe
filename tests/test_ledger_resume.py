"""Ledger test 1: a resumed batch never duplicates finished units, and a unit
interrupted after its model call but before its done record is re-run once and
counted (AD-006)."""
import test_harness_support as S
from harness import runner
from harness.ledger import UnitLedger, unit_key


def test_resume_without_duplication(tmp_path, monkeypatch):
    claude, _ = S.make_fake(tmp_path, "ok", monkeypatch)
    kw = S.run_kwargs(tmp_path, claude)
    tid = S.first_task()
    ev, res = tmp_path / "evidence", tmp_path / "results"
    assert runner.run_batch(["era-c"], "dev", ev, res, task_ids=[tid], **kw) == runner.EXIT_OK
    rows_before = S.ledger_rows(ev / "ledger.jsonl")
    # Second run of the same batch: everything is done, nothing is called again.
    assert runner.run_batch(["era-c"], "dev", ev, res, task_ids=[tid], **kw) == runner.EXIT_OK
    rows_after = S.ledger_rows(ev / "ledger.jsonl")
    assert rows_after == rows_before
    assert sum(1 for r in rows_after if r["kind"] == "call") == 5
    assert len(runner.load_records(res)) == 5


def test_interrupt_after_call_before_done_reruns_once(tmp_path, monkeypatch):
    claude, _ = S.make_fake(tmp_path, "ok", monkeypatch)
    kw = S.run_kwargs(tmp_path, claude)
    tid = S.first_task()
    ev, res = tmp_path / "evidence", tmp_path / "results"
    runner.run_batch(["era-c"], "dev", ev, res, task_ids=[tid], **kw)
    # Simulate a crash after the last unit's model call: drop its done row.
    path = ev / "ledger.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines(True)
    last_done = max(i for i, x in enumerate(lines) if '"kind": "done"' in x)
    lost_unit = S.ledger_rows(path)[last_done]["unit"]
    del lines[last_done]
    path.write_text("".join(lines), encoding="utf-8")
    led = UnitLedger(path)
    assert led.interrupted_units() == [lost_unit]
    assert runner.run_batch(["era-c"], "dev", ev, res, task_ids=[tid], **kw) == runner.EXIT_OK
    rows = S.ledger_rows(path)
    done = [r for r in rows if r["kind"] == "done"]
    assert len(done) == 5 and len(set(r["unit"] for r in done)) == 5
    redo = [r for r in done if r["unit"] == lost_unit]
    assert len(redo) == 1 and redo[0]["interrupted_rerun"] is True
    calls = [r for r in rows if r["kind"] == "call" and r["unit"] == lost_unit]
    assert len(calls) == 2  # original call plus exactly one re-run
    assert UnitLedger(path).summary()["interrupted_reruns"] == 1


def test_unit_key_shape():
    assert unit_key("era-c", "era-c-dev-01", "with", 2) == "era-c|era-c-dev-01|with|2"
