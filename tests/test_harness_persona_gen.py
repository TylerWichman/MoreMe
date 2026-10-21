"""Persona briefs for skill generation: train files only, no writer names in
anything the model sees, the driver's own era-c brief left untouched."""
import json
import re

import test_harness_support  # noqa: F401  (puts eval/ on sys.path)
from harness import common, persona_gen


def test_briefs_cover_every_persona_with_train_files_only():
    persona_gen.register_briefs()
    drv = persona_gen.run_moreme.PERSONAS
    assert sorted(drv) == sorted(common.RUN_ORDER)
    split = common.load_split()
    for pid, b in drv.items():
        train = set("my-writing/" + f.split("/")[1] for f in common.split_files(split, pid, "train"))
        assert set(b["give_files"]) <= train, pid
        assert b["first_name"] == common.personas.persona_first_name(pid)


def test_era_c_brief_is_the_drivers_own():
    before = dict(persona_gen.run_moreme.PERSONAS["era-c"])
    persona_gen.register_briefs()
    assert persona_gen.run_moreme.PERSONAS["era-c"] == before


def test_model_facing_brief_text_names_no_writer():
    prov = (common.CORPUS / "PROVENANCE.md").read_text(encoding="utf-8")
    names = set()
    for a in re.findall(r"^- Author: ([^,\n(]+)", prov, re.M):
        names.update(w.strip(".,").lower() for w in a.split() if w[:1].isupper() and len(w) > 3)
    for pid, b in persona_gen.BRIEFS.items():
        text = (b["who"] + " " + b["task"]).lower()
        for n in names:
            assert not re.search(r"\b%s\b" % re.escape(n), text), (pid, n)


def _fake_runs(tmp_path, monkeypatch, manifests):
    monkeypatch.setattr(persona_gen.run_moreme, "RUNS", tmp_path)
    calls = []

    def run(rid):
        m = manifests[len(calls)]
        calls.append(rid)
        d = tmp_path / rid
        d.mkdir()
        (d / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
        return 0
    return run, calls


def _m(status="completed", share=0.8):
    return {"status": status, "sample_composition": {"corpus_share": share, "meets_rule": share >= 0.75}}


def test_corpus_share_rule_reruns_and_counts(tmp_path, monkeypatch):
    run, calls = _fake_runs(tmp_path, monkeypatch, [_m(share=0.74), _m(share=0.81)])
    rid, log = persona_gen.generate("era-c", "gen-x", run=run)
    assert rid == "gen-x-a2" and calls == ["gen-x", "gen-x-a2"]
    assert [x["usable"] for x in log] == [False, True]
    assert log[0]["reason"] == "corpus_share:0.74"


def test_no_usable_run_after_attempts(tmp_path, monkeypatch):
    run, _calls = _fake_runs(tmp_path, monkeypatch, [_m(share=0.5), _m(share=0.6)])
    rid, log = persona_gen.generate("era-c", "gen-y", run=run)
    assert rid is None and len(log) == 2


def test_usage_limit_stops_without_retry(tmp_path, monkeypatch):
    run, calls = _fake_runs(tmp_path, monkeypatch, [_m(status="usage_limit", share=0.0), _m()])
    rid, _log = persona_gen.generate("era-c", "gen-z", run=run)
    assert rid is None and calls == ["gen-z"]


def test_verdict_requires_completed_run_and_share():
    assert persona_gen.generation_verdict(_m()) == (True, "ok")
    assert persona_gen.generation_verdict(_m(status="max_turns"))[0] is False
    assert persona_gen.generation_verdict(_m(share=0.749))[0] is False
