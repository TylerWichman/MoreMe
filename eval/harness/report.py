"""Report generator with the pre-registered README sentences (AD-006, brief FROZEN 5).

    cd eval && python -m harness.report --results results/<run> --candidates dev|heldout

Steps: load draft records, score them (scoring.py) against the candidate
profiles, run the paired stratified bootstrap (stats.py), pick the sentence
for the observed outcome of the primary metric named by the validity gate,
add the disagreement sentence if a secondary scoring-only metric's CI excludes
zero in the other direction, and write scores.json, analysis.json and
report.md next to the drafts.

The sentence templates below are copied verbatim into eval/PREREGISTRATION.md;
a test fails if the two drift apart.
"""
import argparse
import sys
import time
from pathlib import Path

from harness import common, evidence, runner, scoring, stats

SENTENCES = {
    "attribution": {
        "gain": "With the skill, a style measure the skill never saw picked the right writer for {with_pct}% of drafts, compared with {without_pct}% without it (difference {diff} points, 95% CI {lo} to {hi}; chance is {chance_pct}%).",
        "no_clear_difference": "With the skill, a style measure the skill never saw picked the right writer for {with_pct}% of drafts, compared with {without_pct}% without it. The 95% CI for the difference ({lo} to {hi} points) includes zero, so this test found no clear difference.",
        "loss": "With the skill, a style measure the skill never saw picked the right writer for {with_pct}% of drafts, compared with {without_pct}% without it (difference {diff} points, 95% CI {lo} to {hi}). On this test the skill made drafts measure less like the writer.",
    },
    "fallback_delta_fw": {
        "gain": "Drafts with the skill measured {pct_change}% closer to the writer's own held-out writing on a function-word measure the skill never saw (95% CI {lo}% to {hi}% change in distance).",
        "no_clear_difference": "Drafts with the skill measured {pct_change}% {direction} the writer's own held-out writing on a function-word measure the skill never saw. The 95% CI ({lo}% to {hi}% change in distance) includes zero, so this test found no clear difference.",
        "loss": "Drafts with the skill measured {pct_change}% further from the writer's own held-out writing on a function-word measure the skill never saw (95% CI {lo}% to {hi}% change in distance). On this test the skill made drafts measure less like the writer.",
    },
    "gate": "Picking the writer from a draft-length chunk of their real text was right only {gate_pct}% of the time, so the eval uses distance to the writer instead.",
    "disagreement": "Other style measures disagree: {metric} moved {direction} ({CI}).",
}

METRIC_NAMES = {"correct": "attribution accuracy", "delta_fw": "function-word distance",
                "char3_cosine": "character-pattern distance", "exposed_distance": "stated-feature distance"}


def _r(x, places=1):
    return "%.*f" % (places, x)


def toward(metric, value):
    """+1 if a with-minus-without value means closer to the writer, -1 if away."""
    if value == 0:
        return 0
    good = value < 0 if stats.LOWER_IS_CLOSER[metric] else value > 0
    return 1 if good else -1


def headline(analysis, primary, chance, gate=None):
    """(outcome, sentences list) for the primary metric."""
    out = []
    if primary == "attribution":
        ci = analysis["with_vs_without"]["correct"]
        oc = stats.outcome(ci)
        means = analysis["arm_means"]["correct"]
        vals = dict(with_pct=_r(100 * means["with"], 0), without_pct=_r(100 * means["without"], 0),
                    diff=_r(100 * ci["estimate"]), lo=_r(100 * ci["lo"]), hi=_r(100 * ci["hi"]),
                    chance_pct=_r(100 * chance, 0))
        out.append(SENTENCES["attribution"][oc].format(**vals))
    else:
        ci = analysis["with_vs_without"]["delta_fw_pct"]
        oc = stats.outcome(ci, lower_is_better=True)
        est = ci["estimate"]
        vals = dict(pct_change=_r(abs(est)), direction="closer to" if est < 0 else "further from",
                    lo=_r(ci["lo"]), hi=_r(ci["hi"]))
        out.append(SENTENCES["fallback_delta_fw"][oc].format(**vals))
    dis = disagreement(analysis, primary)
    out.extend(dis)
    if primary != "attribution" and gate is not None:
        out.append(SENTENCES["gate"].format(gate_pct=_r(100 * gate["pooled_accuracy"], 0)))
    return oc, out


def disagreement(analysis, primary):
    pmetric = "correct" if primary == "attribution" else "delta_fw"
    pdir = toward(pmetric, analysis["with_vs_without"][pmetric]["estimate"] or 0)
    if pdir == 0:
        return []
    secondary = ["delta_fw" if primary == "attribution" else "correct", "char3_cosine"]
    out = []
    for m in secondary:
        ci = analysis["with_vs_without"][m]
        if ci["lo"] is None:
            continue
        excludes_zero = ci["lo"] > 0 or ci["hi"] < 0
        if excludes_zero and toward(m, ci["estimate"]) == -pdir:
            scale = 100.0 if m == "correct" else 1.0
            unit = " points" if m == "correct" else ""
            places = 1 if m == "correct" else 4
            cis = "95% CI {0} to {1}{2}".format(_r(scale * ci["lo"], places), _r(scale * ci["hi"], places), unit)
            direction = "toward the writer" if toward(m, ci["estimate"]) > 0 else "away from the writer"
            out.append(SENTENCES["disagreement"].format(metric=METRIC_NAMES[m], direction=direction, CI=cis))
    return out


def _cell(metric, v):
    if v is None:
        return "-"
    return "%.0f%%" % (100 * v) if metric == "correct" else "%.4f" % v


def render(analysis, primary, chance, manifest, gate, era, split_label):
    oc, sents = headline(analysis, primary, chance, gate)
    lines = ["# Eval report (%s)" % split_label, "",
             "Generated by `python -m harness.report` from the draft records in this folder. "
             "Numbers regenerate from committed files.", ""]
    if split_label != "heldout":
        lines += ["This is a dev-split run. It is a signal for the pre-registered checks, not the eval result. "
                  "The sentence below uses the README wording only to test the generator.", ""]
    lines += ["## Headline", ""] + sents + ["", "Primary metric: %s. Outcome: %s." % (
        "nearest-persona attribution" if primary == "attribution" else "mean delta_fw to the target persona",
        oc.replace("_", " ")), ""]
    lines += ["## Arms by metric", "", "Lower is closer for every distance. Attribution chance is %.0f%%." % (100 * chance),
              "", "| Arm | Attribution | delta_fw | char3_cosine | exposed_distance (the skill states these targets, so improvement is expected) |",
              "|---|---|---|---|---|"]
    for arm in common.ARMS:
        lines.append("| %s | " % arm + " | ".join(_cell(m, analysis["arm_means"][m][arm]) for m in stats.METRICS) + " |")
    lines += ["", "## Paired differences (with minus without, tasks resampled within persona, %d resamples)" %
              common.BOOTSTRAP_RESAMPLES, "", "| Metric | Tasks | Estimate | 95% CI |", "|---|---|---|---|"]
    for m in stats.METRICS:
        ci = analysis["with_vs_without"][m]
        if ci["estimate"] is None:
            lines.append("| %s | 0 | - | - |" % m)
            continue
        sc = 100.0 if m == "correct" else 1.0
        lines.append("| %s | %d | %.4f | %.4f to %.4f |" % (m, ci["n_tasks"], sc * ci["estimate"], sc * ci["lo"], sc * ci["hi"]))
    inv = (manifest or {}).get("invocation") or {}
    lines += ["", "## Invocation", ""]
    if inv.get("rate") is not None:
        lines.append("The my-voice skill was invoked in %d of %d valid `with` drafts (%.0f%%). Pre-registered threshold: %.0f%%."
                     % (inv["invoked"], inv["valid_with_units"], 100 * inv["rate"], 100 * common.INVOCATION_THRESHOLD))
    else:
        lines.append("No valid `with` drafts.")
    lines += ["", "## By persona (attribution of the without arm is the base rate)", "",
              "| Persona | Era | Without | With | Samples-pasted |", "|---|---|---|---|---|"]
    for p, ms in sorted(analysis["per_persona"].items()):
        c = ms["correct"]
        lines.append("| %s | %s | %s | %s | %s |" % (p, era.get(p, "?"), _cell("correct", c["without"]),
                                                    _cell("correct", c["with"]), _cell("correct", c["samples-pasted"])))
    lines += ["", "Per-persona results are descriptive. The study is underpowered for per-persona conclusions.", ""]
    return "\n".join(lines), oc, sents


def main(argv=None):
    ap = argparse.ArgumentParser(description="score drafts and write the report")
    ap.add_argument("--results", required=True)
    ap.add_argument("--candidates", choices=("dev", "heldout"), required=True)
    ap.add_argument("--resamples", type=int, default=common.BOOTSTRAP_RESAMPLES)
    a = ap.parse_args(argv)
    results = Path(a.results)
    split = common.load_split()
    ref = common.read_json(common.REFERENCE_STATS)
    records = runner.load_records(results)
    cands = scoring.candidate_profiles(split, a.candidates)
    scores = scoring.score_records(records, cands, ref)
    analysis = stats.analyze(scores, a.resamples)
    gate = common.read_json(common.RESULTS / "validity-gate.json")
    manifest = common.read_json(results / "manifest.json") if (results / "manifest.json").exists() else None
    primary = gate["primary_in_force"]
    text, oc, sents = render(analysis, primary, 1.0 / len(cands), manifest, gate, common.persona_era(), a.candidates)
    common.write_json(results / "scores.json", {"schema_version": "1", "candidates": a.candidates, "scores": scores})
    common.write_json(results / "analysis.json", {"schema_version": "1", "primary": primary, "outcome": oc,
                                                  "sentences": sents, "analysis": analysis,
                                                  "invocation": evidence.invocation_rate(records)[0],
                                                  "created": time.strftime("%Y-%m-%dT%H:%M")})
    common.write_text(results / "report.md", text)
    print("\n".join(sents))
    return 0


if __name__ == "__main__":
    sys.exit(main())
