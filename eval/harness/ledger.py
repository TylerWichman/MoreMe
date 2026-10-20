"""Resumable unit ledger with torn-tail quarantine (AD-006).

One append-only JSONL file (eval/lib/childrun.Ledger) holds two kinds of rows:

- "call": written by childrun.run_claude after every model call, with the
  unit key in the "unit" field.
- "done": written by the harness after the unit's draft record is saved.
  A unit is complete only when its "done" row is in the ledger.

Resume rules:
- Before anything else the ledger is healed: if it does not end in a newline,
  the partial last line goes to ledger.quarantine.jsonl and is never merged
  with the next record. A "quarantine" row records that it happened.
- Units with a "done" row are skipped, so a resumed run never duplicates them.
- A unit with "call" rows but no "done" row (interrupted after the model call,
  or its "done" row was the torn tail) is re-run once more and the re-run is
  counted ("interrupted_reruns").
"""
from harness import common

cr = common.childrun

MAX_ATTEMPTS = 3


def unit_key(persona, task_id, arm, rep):
    return "%s|%s|%s|%d" % (persona, task_id, arm, rep)


class UnitLedger(object):
    def __init__(self, path):
        self.ledger = cr.Ledger(path)
        self.path = self.ledger.path
        self.quarantine = self.ledger.quarantine

    def heal(self):
        torn = self.ledger.heal()
        if torn is not None:
            self.ledger.append({"kind": "quarantine", "bytes": len(torn.encode("utf-8")),
                                "note": "partial last line moved to %s" % self.quarantine.name})
        return torn

    def rows(self):
        return self.ledger.rows()

    def done_units(self):
        return dict((r["unit"], r) for r in self.rows() if r.get("kind") == "done")

    def calls_by_unit(self):
        out = {}
        for r in self.rows():
            if r.get("kind") == "call" and r.get("unit"):
                out[r["unit"]] = out.get(r["unit"], 0) + 1
        return out

    def interrupted_units(self):
        done = self.done_units()
        return sorted(u for u in self.calls_by_unit() if u not in done)

    def mark_done(self, unit, valid, attempts, draft_file, reasons=None, interrupted_rerun=False):
        self.ledger.append({"kind": "done", "unit": unit, "valid": bool(valid), "attempts": attempts,
                            "draft_file": draft_file, "invalid_history": reasons or [],
                            "interrupted_rerun": bool(interrupted_rerun)})

    def call_count(self):
        return self.ledger.count("call")

    def summary(self):
        rows = self.rows()
        done = [r for r in rows if r.get("kind") == "done"]
        return {
            "calls": sum(1 for r in rows if r.get("kind") == "call"),
            "units_done": len(done),
            "units_valid": sum(1 for r in done if r["valid"]),
            "invalid_attempts": sum(len(r.get("invalid_history") or []) for r in done),
            "interrupted_reruns": sum(1 for r in done if r.get("interrupted_rerun")),
            "quarantined_lines": sum(1 for r in rows if r.get("kind") == "quarantine"),
        }
