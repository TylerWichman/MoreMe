"""Paired task bootstrap, stratified by persona (AD-006 Analysis).

Unit of analysis: the task. Within a task, reps of an arm are averaged. A
task's paired difference = mean(arm A) - mean(arm B). The pooled estimate is
the mean of task differences over all tasks. The bootstrap resamples tasks with
replacement within each persona (the persona's task count is kept), 10,000
resamples, fixed seed, percentile 95% interval.
"""
import random

from harness import common

METRICS = ("correct", "delta_fw", "char3_cosine", "exposed_distance")
LOWER_IS_CLOSER = {"correct": False, "delta_fw": True, "char3_cosine": True, "exposed_distance": True}


def task_means(scores, metric, arm, per_protocol=False):
    """{(persona, task_id): mean metric over the arm's reps}."""
    acc = {}
    for s in scores:
        if s["arm"] != arm or s.get(metric) is None:
            continue
        if per_protocol and arm == "with" and not s.get("invoked"):
            continue
        v = float(s[metric])
        acc.setdefault((s["persona"], s["task_id"]), []).append(v)
    return dict((k, sum(v) / len(v)) for k, v in acc.items())


def paired(scores, metric, arm_a="with", arm_b="without", per_protocol=False):
    a = task_means(scores, metric, arm_a, per_protocol)
    b = task_means(scores, metric, arm_b)
    keys = sorted(set(a) & set(b))
    return [(k[0], k[1], a[k], b[k]) for k in keys]


def _percentile(sorted_vals, q):
    if not sorted_vals:
        return None
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def bootstrap(pairs, resamples=common.BOOTSTRAP_RESAMPLES, seed=common.BOOTSTRAP_SEED, relative=False):
    """pairs: [(persona, task, a, b)]. Returns point estimate and 95% CI of
    mean(a - b), or with relative=True of (mean(a) - mean(b)) / mean(b) * 100."""
    if not pairs:
        return {"n_tasks": 0, "estimate": None, "lo": None, "hi": None}
    strata = {}
    for p in pairs:
        strata.setdefault(p[0], []).append(p)

    def stat(sample):
        ma = sum(x[2] for x in sample) / len(sample)
        mb = sum(x[3] for x in sample) / len(sample)
        if relative:
            return None if mb == 0 else (ma - mb) / mb * 100.0
        return ma - mb

    rng = random.Random(seed)
    est = stat(pairs)
    vals = []
    names = sorted(strata)
    for _ in range(resamples):
        sample = []
        for name in names:
            group = strata[name]
            sample.extend(group[rng.randrange(len(group))] for _ in range(len(group)))
        v = stat(sample)
        if v is not None:
            vals.append(v)
    vals.sort()
    return {"n_tasks": len(pairs), "estimate": est, "lo": _percentile(vals, 0.025), "hi": _percentile(vals, 0.975),
            "resamples": resamples, "seed": seed, "stratified_by": "persona"}


def outcome(ci, lower_is_better=False):
    """gain / no_clear_difference / loss from a CI of (with - without)."""
    lo, hi = ci["lo"], ci["hi"]
    if lo is None or hi is None:
        return None
    if lower_is_better:
        lo, hi = -hi, -lo
    if lo > 0:
        return "gain"
    if hi < 0:
        return "loss"
    return "no_clear_difference"


def arm_means(scores, metric):
    out = {}
    for arm in common.ARMS:
        vals = list(task_means(scores, metric, arm).values())
        out[arm] = (sum(vals) / len(vals)) if vals else None
    return out


def analyze(scores, resamples=common.BOOTSTRAP_RESAMPLES, seed=common.BOOTSTRAP_SEED):
    """Every comparison the report needs."""
    res = {"arm_means": {}, "with_vs_without": {}, "with_vs_without_per_protocol": {},
           "with_vs_samples": {}, "per_persona": {}}
    for m in METRICS:
        res["arm_means"][m] = arm_means(scores, m)
        res["with_vs_without"][m] = bootstrap(paired(scores, m), resamples, seed)
        res["with_vs_without_per_protocol"][m] = bootstrap(paired(scores, m, per_protocol=True), resamples, seed)
        res["with_vs_samples"][m] = bootstrap(paired(scores, m, "with", "samples-pasted"), resamples, seed)
    res["with_vs_without"]["delta_fw_pct"] = bootstrap(paired(scores, "delta_fw"), resamples, seed, relative=True)
    personas = sorted(set(s["persona"] for s in scores))
    for p in personas:
        sub = [s for s in scores if s["persona"] == p]
        res["per_persona"][p] = dict((m, arm_means(sub, m)) for m in METRICS)
    return res
