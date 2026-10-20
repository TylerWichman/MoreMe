"""Report generator: pre-registered sentence selection and disagreement rule."""
import test_harness_support  # noqa: F401  (puts eval/ on sys.path)
from harness import common, report, stats


def ci(est, lo, hi, n=48):
    return {"n_tasks": n, "estimate": est, "lo": lo, "hi": hi}


def analysis(correct, delta, char3, pct=None, means=(0.4, 0.3, 0.35)):
    return {
        "arm_means": {"correct": dict(zip(common.ARMS, means)), "delta_fw": dict(zip(common.ARMS, (1.0, 1.1, 1.05))),
                      "char3_cosine": dict(zip(common.ARMS, (0.2, 0.2, 0.2))),
                      "exposed_distance": dict(zip(common.ARMS, (0.5, 0.9, 0.7)))},
        "with_vs_without": {"correct": correct, "delta_fw": delta, "char3_cosine": char3,
                            "exposed_distance": ci(-0.4, -0.5, -0.3),
                            "delta_fw_pct": pct or ci(-9.1, -15.0, -2.0)},
        "per_persona": {"era-c": dict((m, dict(zip(common.ARMS, (0.5, 0.25, 0.5)))) for m in stats.METRICS)},
    }


def test_attribution_gain_sentence():
    a = analysis(ci(0.1, 0.02, 0.18), ci(-0.1, -0.2, -0.01), ci(-0.01, -0.02, 0.01))
    oc, s = report.headline(a, "attribution", 1 / 6.0)
    assert oc == "gain" and len(s) == 1
    assert s[0] == ("With the skill, a style measure the skill never saw picked the right writer for 40% of drafts, "
                    "compared with 30% without it (difference 10.0 points, 95% CI 2.0 to 18.0; chance is 17%).")


def test_attribution_no_clear_difference_and_loss():
    oc, s = report.headline(analysis(ci(0.02, -0.05, 0.09), ci(0, -1, 1), ci(0, -1, 1)), "attribution", 1 / 6.0)
    assert oc == "no_clear_difference" and "includes zero" in s[0] and "(-5.0 to 9.0 points)" in s[0]
    oc, s = report.headline(analysis(ci(-0.1, -0.2, -0.01), ci(0, -1, 1), ci(0, -1, 1)), "attribution", 1 / 6.0)
    assert oc == "loss" and s[0].endswith("On this test the skill made drafts measure less like the writer.")


def test_disagreement_sentence_when_a_secondary_points_the_other_way():
    # Attribution up, but delta_fw moved away from the writer with a CI that excludes zero.
    a = analysis(ci(0.1, 0.02, 0.18), ci(0.2, 0.05, 0.3), ci(0.0, -0.01, 0.01))
    _oc, s = report.headline(a, "attribution", 1 / 6.0)
    assert len(s) == 2
    assert s[1] == "Other style measures disagree: function-word distance moved away from the writer (95% CI 0.0500 to 0.3000)."


def test_no_disagreement_when_secondary_ci_spans_zero_or_agrees():
    a = analysis(ci(0.1, 0.02, 0.18), ci(0.2, -0.05, 0.3), ci(-0.02, -0.03, -0.01))
    assert len(report.headline(a, "attribution", 1 / 6.0)[1]) == 1


def test_fallback_primary_with_gate_sentence():
    a = analysis(ci(0.0, -0.1, 0.1), ci(-0.1, -0.2, -0.01), ci(0, -1, 1))
    gate = {"pooled_accuracy": 0.25}
    oc, s = report.headline(a, "fallback_delta_fw", 1 / 6.0, gate)
    assert oc == "gain"
    assert s[0] == ("Drafts with the skill measured 9.1% closer to the writer's own held-out writing on a "
                    "function-word measure the skill never saw (95% CI -15.0% to -2.0% change in distance).")
    assert s[-1] == ("Picking the writer from a draft-length chunk of their real text was right only 25% of the time, "
                     "so the eval uses distance to the writer instead.")


def test_render_has_sections():
    a = analysis(ci(0.1, 0.02, 0.18), ci(-0.1, -0.2, -0.01), ci(-0.01, -0.02, 0.01))
    man = {"invocation": {"rate": 0.875, "invoked": 14, "valid_with_units": 16}}
    text, oc, _s = report.render(a, "attribution", 1 / 6.0, man, None, {"era-c": "era-diverse"}, "dev")
    for h in ("## Headline", "## Arms by metric", "## Paired differences", "## Invocation", "## By persona"):
        assert h in text
    assert "14 of 16" in text and "dev-split run" in text
    assert "underpowered" in text
