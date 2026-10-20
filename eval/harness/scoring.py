"""Per-draft scores (AD-006 Metrics, AD-002 distances), using analyze.py functions.

For each valid draft: profile in view `all`, then against every persona's
candidate profile:
- attribution: predicted persona = smallest delta_fw (ties by sorted id);
  correct if it is the draft's persona; chance = 1/K
- delta_fw to the target persona (lower is closer)
- char3_cosine to the target persona (lower is closer)
- exposed_distance to the target persona (the skill states these targets)

Candidate profiles: the dev split for the Phase 1 smoke and template
iterations; the held-out split only for the final run, and only after the
pre-registration hash gate passes.
"""
from harness import common, prereg

_AN = None


def an():
    global _AN
    if _AN is None:
        _AN = common.load_analyze()
    return _AN


def candidate_profiles(split, which, personas=None, prereg_path=None):
    if which == "heldout":
        prereg.require_frozen(prereg_path)
    elif which not in ("train", "dev"):
        raise ValueError("candidate split must be train, dev, or heldout")
    out = {}
    for p in sorted(personas or split["personas"]):
        files = sorted(common.split_files(split, p, which))
        text = "\n\n".join(common.read_corpus_text(split, f, allow=(which,)).strip("\n") for f in files)
        out[p] = an().profile_text(text, view="all", name="%s-%s" % (p, which))
    return out


def attribute(profile, candidates, ref):
    deltas = {}
    for pid in sorted(candidates):
        d, _ = an().delta_fw(profile, candidates[pid], ref)
        deltas[pid] = d
    scored = sorted((v, pid) for pid, v in deltas.items() if v is not None)
    return (scored[0][1] if scored else None), deltas


def score_text(text, persona, candidates, ref):
    prof = an().profile_text(text, view="all", name="draft")
    predicted, deltas = attribute(prof, candidates, ref)
    cmp_target = an().compare_profiles(prof, candidates[persona], ref)
    return {
        "predicted": predicted,
        "correct": predicted == persona,
        "k": len(candidates),
        "delta_fw": cmp_target["delta_fw"],
        "char3_cosine": cmp_target["char3_cosine"],
        "exposed_distance": cmp_target["exposed_distance"],
        "deltas": dict((k, (round(v, 4) if v is not None else None)) for k, v in deltas.items()),
    }


def score_records(records, candidates, ref):
    rows = []
    for r in records:
        if not r.get("valid"):
            continue
        s = score_text(r["draft"], r["persona"], candidates, ref)
        s.update({"persona": r["persona"], "task_id": r["task_id"], "arm": r["arm"], "rep": r["rep"],
                  "invoked": bool(r["evidence"].get("invoked")), "draft_words": r.get("draft_words")})
        rows.append(s)
    return rows
