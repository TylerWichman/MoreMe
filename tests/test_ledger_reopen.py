"""A reopen row makes a finished unit run again; nothing is deleted."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))

from harness.ledger import UnitLedger  # noqa: E402


def test_reopen_undoes_done_and_is_not_interrupted(tmp_path):
    led = UnitLedger(tmp_path / "ledger.jsonl")
    led.ledger.append({"kind": "call", "unit": "p|t|with|1"})
    led.mark_done("p|t|with|1", False, 3, "f.json", [{"reasons": ["init:claude_code_version=x expected=y"]}])
    assert "p|t|with|1" in led.done_units()
    led.reopen("p|t|with|1", "claude_code_version mismatch only")
    assert "p|t|with|1" not in led.done_units()
    assert led.interrupted_units() == []
    led.ledger.append({"kind": "call", "unit": "p|t|with|1"})
    assert led.interrupted_units() == ["p|t|with|1"]
    led.mark_done("p|t|with|1", True, 1, "f.json")
    assert led.done_units()["p|t|with|1"]["valid"] is True
    assert led.summary()["reopened"] == 1
