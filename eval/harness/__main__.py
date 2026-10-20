"""Command line for the eval harness. Run from the eval/ folder:

    python -m harness run --persona modern-a --split dev --evidence-dir DIR --results results/dev-smoke
    python -m harness validity
    python -m harness report --results results/dev-smoke --candidates dev
    python -m harness prereg check|hashes|write-hashes|freeze
    python -m harness tasks check|build
    python -m harness leakage
    python -m harness gen-skill --persona modern-a --run-id ID   (persona skill via the e2e driver)

`run` makes model calls (child `claude -p`) through eval/lib/childrun.py. The
others make none. DIR for --evidence-dir must be outside the repo: it receives
the call ledger and the raw stream-json logs.
"""
import argparse
import sys
from pathlib import Path

from harness import common


def cmd_run(argv):
    from harness import runner
    ap = argparse.ArgumentParser(prog="harness run")
    ap.add_argument("--persona", action="append", required=True)
    ap.add_argument("--split", choices=("dev", "heldout"), required=True)
    ap.add_argument("--evidence-dir", help="default: eval/lib/artifacts.evidence_dir('eval', <results name>)")
    ap.add_argument("--results", required=True)
    ap.add_argument("--mode", choices=("auto", "explicit"), default="auto")
    ap.add_argument("--task", action="append", help="limit to these task ids")
    ap.add_argument("--max-calls", type=int, default=120)
    a = ap.parse_args(argv)
    if not a.evidence_dir:
        a.evidence_dir = str(common.evidence_dir("eval", Path(a.results).name))
    ev = Path(a.evidence_dir).resolve()
    try:
        ev.relative_to(common.REPO)
        print("--evidence-dir must be outside the repo (AMEND-002)", file=sys.stderr)
        return 2
    except ValueError:
        pass
    return runner.run_batch(a.persona, a.split, ev, Path(a.results), mode=a.mode, task_ids=a.task,
                            max_calls=a.max_calls)


def cmd_leakage(argv):
    from harness import leakage
    split = common.load_split()
    docs = leakage.corpus_shingles(split, ("heldout",))
    hits = leakage.scan_files(list(leakage.leakage_targets()), docs)
    for f, doc, k in hits:
        print("%s shares %d 12-word shingles with %s" % (f, k, doc))
    print("leakage hits: %d" % len(hits))
    return 1 if hits else 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "run":
        return cmd_run(rest)
    if cmd == "leakage":
        return cmd_leakage(rest)
    if cmd == "gen-skill":
        from harness import persona_gen
        return persona_gen.main(rest)
    if cmd == "validity":
        from harness import validity
        return validity.main(rest)
    if cmd == "report":
        from harness import report
        return report.main(rest)
    if cmd == "prereg":
        from harness import prereg
        return prereg.main(rest)
    if cmd == "tasks":
        from harness import tasks
        return tasks.main(rest)
    print("unknown command: %s" % cmd, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
