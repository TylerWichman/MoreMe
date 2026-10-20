"""Paired task bootstrap, stratified by persona (AD-006 Analysis)."""
import random

import test_harness_support  # noqa: F401  (puts eval/ on sys.path)
from harness import common, stats


def _scores(n_personas=3, tasks=8, effect=0.2, seed=1):
    rng = random.Random(seed)
    out = []
    for p in range(n_personas):
        for t in range(tasks):
            base = rng.random()
            for arm, reps, shift in (("without", 2, 0.0), ("with", 2, effect), ("samples-pasted", 1, effect / 2)):
                for r in range(1, reps + 1):
                    v = base + shift + rng.gauss(0, 0.05)
                    out.append({"persona": "p%d" % p, "task_id": "p%d-t%d" % (p, t), "arm": arm, "rep": r,
                                "correct": 1.0 if v > 0.5 else 0.0, "delta_fw": 1.0 - v,
                                "char3_cosine": 0.3 - v / 10, "exposed_distance": 1.0, "invoked": r == 1})
    return out


def test_constants_are_the_preregistered_ones():
    assert common.BOOTSTRAP_RESAMPLES == 10000
    assert common.BOOTSTRAP_SEED == 20261019


def test_reps_are_averaged_within_task():
    s = [{"persona": "a", "task_id": "t", "arm": "with", "rep": 1, "delta_fw": 1.0},
         {"persona": "a", "task_id": "t", "arm": "with", "rep": 2, "delta_fw": 3.0}]
    assert stats.task_means(s, "delta_fw", "with") == {("a", "t"): 2.0}


def test_bootstrap_is_deterministic_and_brackets_the_estimate():
    pairs = stats.paired(_scores(), "delta_fw")
    a = stats.bootstrap(pairs, 2000)
    b = stats.bootstrap(pairs, 2000)
    assert a == b
    assert a["lo"] <= a["estimate"] <= a["hi"]
    assert a["n_tasks"] == 24
    assert abs(a["estimate"] - (-0.2)) < 0.03


def test_bootstrap_keeps_each_persona_task_count(monkeypatch):
    pairs = [("A", "a%d" % i, 1.0, 0.0) for i in range(2)] + [("B", "b%d" % i, 0.0, 0.0) for i in range(6)]
    seen = []
    real = stats.random.Random

    class Spy(real):
        def randrange(self, n):
            seen.append(n)
            return real.randrange(self, n)

    monkeypatch.setattr(stats.random, "Random", Spy)
    r = stats.bootstrap(pairs, 50)
    assert seen.count(2) == 2 * 50 and seen.count(6) == 6 * 50
    # A's share is always 2 of 8 tasks, so mean(a - b) is exactly 0.25 every time.
    assert r["lo"] == r["hi"] == r["estimate"] == 0.25


def test_outcome_rule():
    assert stats.outcome({"lo": 0.01, "hi": 0.3}) == "gain"
    assert stats.outcome({"lo": -0.1, "hi": 0.3}) == "no_clear_difference"
    assert stats.outcome({"lo": -0.3, "hi": -0.01}) == "loss"
    assert stats.outcome({"lo": -0.3, "hi": -0.01}, lower_is_better=True) == "gain"
    assert stats.outcome({"lo": 0.01, "hi": 0.2}, lower_is_better=True) == "loss"


def test_per_protocol_drops_uninvoked_with_drafts():
    s = _scores(1, 2)
    itt = stats.task_means(s, "delta_fw", "with")
    pp = stats.task_means(s, "delta_fw", "with", per_protocol=True)
    assert set(itt) == set(pp)
    assert any(itt[k] != pp[k] for k in itt)


def test_analyze_has_every_section():
    res = stats.analyze(_scores(), resamples=200)
    for m in stats.METRICS:
        assert set(res["arm_means"][m]) == set(common.ARMS)
        assert res["with_vs_without"][m]["n_tasks"] == 24
    assert res["with_vs_without"]["delta_fw_pct"]["estimate"] < 0
    assert sorted(res["per_persona"]) == ["p0", "p1", "p2"]
