"""Pre-registration hash gate and drift checks against eval/PREREGISTRATION.md."""
import shutil

import pytest

import test_harness_support as S
from harness import common, extraction, prereg, report, tasks

PREREG_TEXT = common.PREREG.read_text(encoding="utf-8")


def _fake_repo(tmp_path):
    repo = tmp_path / "repo"
    for r in prereg.hashed_files():
        dst = repo / r
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(common.REPO / r), str(dst))
    p = repo / "eval" / "PREREGISTRATION.md"
    p.write_text("# x\n\n%s\n%s\n" % (prereg.START, prereg.END), encoding="utf-8")
    return repo, p


def test_committed_prereg_is_draft_and_refuses_heldout_scoring():
    status, hashes = prereg.parse_block(PREREG_TEXT)
    assert status in ("draft", "frozen")
    assert set(hashes) == set(prereg.hashed_files())
    if status == "draft":
        with pytest.raises(prereg.PreregError):
            prereg.require_frozen()


def test_frozen_and_matching_passes_then_any_change_refuses(tmp_path):
    repo, p = _fake_repo(tmp_path)
    prereg.write_hashes(p, status="draft", repo=repo)
    with pytest.raises(prereg.PreregError, match="not frozen"):
        prereg.require_frozen(p, repo)
    prereg.write_hashes(p, status="frozen", repo=repo)
    assert prereg.require_frozen(p, repo)
    f = repo / "moreme" / "templates" / "my-voice" / "SKILL.md.tmpl"
    f.write_text(f.read_text(encoding="utf-8") + "\nedited\n", encoding="utf-8")
    with pytest.raises(prereg.PreregError, match="SKILL.md.tmpl"):
        prereg.require_frozen(p, repo)


def test_line_endings_do_not_change_a_hash(tmp_path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_bytes(b"one\ntwo\n")
    b.write_bytes(b"one\r\ntwo\r\n")
    assert common.sha256_text_file(a) == common.sha256_text_file(b)


def test_missing_block_or_file_refuses(tmp_path):
    p = tmp_path / "P.md"
    p.write_text("no block", encoding="utf-8")
    with pytest.raises(prereg.PreregError):
        prereg.require_frozen(p)
    with pytest.raises(prereg.PreregError):
        prereg.require_frozen(tmp_path / "absent.md")


def test_hashed_files_cover_the_planned_set():
    files = prereg.hashed_files()
    for r in ("moreme/SKILL.md", "moreme/templates/my-voice/SKILL.md.tmpl", "moreme/analyze.py",
              "eval/reference_stats.json", "eval/tasks/tasks.json", "eval/harness/runner.py",
              "eval/harness/extraction.py", "eval/harness/stats.py"):
        assert r in files


def test_prereg_states_every_sentence_and_regex_verbatim():
    for group in ("attribution", "fallback_delta_fw"):
        for s in report.SENTENCES[group].values():
            assert s in PREREG_TEXT, s
    assert report.SENTENCES["gate"] in PREREG_TEXT
    assert report.SENTENCES["disagreement"] in PREREG_TEXT
    assert extraction.PREAMBLE_PATTERN in PREREG_TEXT
    assert extraction.FENCE_PATTERN in PREREG_TEXT
    assert tasks.PROMPT_TEMPLATE in PREREG_TEXT
    assert tasks.EXPLICIT_PREFIX in PREREG_TEXT and tasks.NEUTRAL_PREFIX in PREREG_TEXT
    assert common.ARM_ORDER_SEED in PREREG_TEXT and common.SAMPLES_SEED in PREREG_TEXT
    assert str(common.BOOTSTRAP_SEED) in PREREG_TEXT and "10,000 resamples" in PREREG_TEXT


def test_prereg_run_order_matches_harness():
    line = [ln for ln in PREREG_TEXT.splitlines() if ln.startswith("- Persona run order")][0]
    order = [x.strip("` .") for x in line.split(":", 1)[1].split(",")]
    assert tuple(order) == common.RUN_ORDER


def test_prereg_gate_numbers_match_saved_gate_result():
    gate = common.read_json(common.RESULTS / "validity-gate.json")
    assert "%d | %d | %.1f%%" % (gate["pooled_chunks"], gate["pooled_correct"], 100 * gate["pooled_accuracy"]) in PREREG_TEXT
    if gate["passed"]:
        assert "**Primary (in force):** nearest-persona attribution" in PREREG_TEXT
    else:
        assert "**Fallback primary (in force)" in PREREG_TEXT
