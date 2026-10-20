"""Ledger test 2: a truncated final line is detected, quarantined, and its unit
re-run; it is never merged with the next record (AD-006)."""
import json

import test_harness_support as S
from harness import runner
from harness.ledger import UnitLedger


def test_torn_done_record_is_quarantined_and_unit_rerun(tmp_path, monkeypatch):
    claude, _ = S.make_fake(tmp_path, "ok", monkeypatch)
    kw = S.run_kwargs(tmp_path, claude)
    tid = S.first_task()
    ev, res = tmp_path / "evidence", tmp_path / "results"
    runner.run_batch(["era-c"], "dev", ev, res, task_ids=[tid], **kw)
    path = ev / "ledger.jsonl"
    data = path.read_bytes()
    lines = data.split(b"\n")[:-1]
    torn_row = json.loads(lines[-1].decode("utf-8"))
    assert torn_row["kind"] == "done"
    # Cut the last record in half: no trailing newline, invalid JSON.
    cut = data[: len(data) - 1 - len(lines[-1]) // 2]
    path.write_bytes(cut)
    torn_text = cut.split(b"\n")[-1]
    assert runner.run_batch(["era-c"], "dev", ev, res, task_ids=[tid], **kw) == runner.EXIT_OK
    q = (ev / "ledger.quarantine.jsonl").read_bytes()
    assert q == torn_text + b"\n"
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    for line in text.splitlines():
        json.loads(line)  # every remaining line is a whole record, nothing merged
    assert text.splitlines()[: len(lines) - 1] == [x.decode("utf-8") for x in lines[:-1]]
    rows = S.ledger_rows(path)
    assert any(r["kind"] == "quarantine" for r in rows)
    done = [r for r in rows if r["kind"] == "done" and r["unit"] == torn_row["unit"]]
    assert len(done) == 1 and done[0]["interrupted_rerun"] is True
    assert len([r for r in rows if r["kind"] == "done"]) == 5
    assert UnitLedger(path).summary()["quarantined_lines"] == 1


def test_heal_is_a_no_op_on_a_clean_ledger(tmp_path):
    led = UnitLedger(tmp_path / "ledger.jsonl")
    assert led.heal() is None
    led.mark_done("u", True, 1, "x.json")
    assert led.heal() is None
    assert not led.quarantine.exists()


def test_torn_call_record_does_not_glue_to_next_append(tmp_path):
    led = UnitLedger(tmp_path / "ledger.jsonl")
    led.mark_done("a", True, 1, "a.json")
    with open(str(led.path), "ab") as f:
        f.write(b'{"kind": "call", "unit": "b", "n"')
    led.heal()
    led.mark_done("c", True, 1, "c.json")
    rows = led.rows()
    assert [r.get("unit") for r in rows if r["kind"] == "done"] == ["a", "c"]
    assert led.quarantine.read_bytes() == b'{"kind": "call", "unit": "b", "n"\n'
