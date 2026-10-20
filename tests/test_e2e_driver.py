"""e2e driver (eval/e2e/run_moreme.py) without model calls: scratch layout,
flags, interviewee brief, timings, transcript render, rubric file."""
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "eval"))
from lib import childrun  # noqa: E402

spec = importlib.util.spec_from_file_location("run_moreme", str(REPO / "eval" / "e2e" / "run_moreme.py"))
drv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drv)

SPLIT = json.loads((REPO / "eval" / "split.json").read_text(encoding="utf-8"))
WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*")


@pytest.fixture
def temp(tmp_path, monkeypatch):
    monkeypatch.setattr(childrun, "temp_base", lambda: tmp_path)
    return tmp_path


def test_scratch_has_only_skill_settings_and_train_files(temp):
    d, found = drv.build_scratch("t1", "era-c", SPLIT)
    assert d == temp / "moreme-e2e" / "t1"
    train = sorted(x["file"] for x in SPLIT["personas"]["era-c"]["documents"] if x["split"] == "train")
    assert found == train
    names = sorted(p.name for p in (d / "my-writing").iterdir())
    assert names == sorted(Path(f).name for f in train)
    assert sorted(p.name for p in (d / ".claude" / "skills").iterdir()) == ["moreme"]
    assert (d / ".claude" / "skills" / "moreme" / "analyze.py").exists()


def test_scratch_contents_check_rejects_extra_file(temp):
    d, _ = drv.build_scratch("t1", "era-c", SPLIT)
    (d / "notes.txt").write_text("x", encoding="utf-8")
    with pytest.raises(childrun.ScratchError):
        drv.assert_scratch_contents(d, "era-c", SPLIT)


def test_skill_flags_follow_profile():
    first = drv.skill_flags("abc", True)
    later = drv.skill_flags("abc", False)
    for f in (first, later):
        assert "--setting-sources" in f and f[f.index("--setting-sources") + 1] == "project"
        assert "--strict-mcp-config" in f
        assert f[f.index("--permission-mode") + 1] == "acceptEdits"
        assert f[f.index("--permission-prompts") + 1] == "none"
        assert f[f.index("--model") + 1] == childrun.MODEL
        allowed = [a for a in f if a.startswith("--allowedTools")]
        assert allowed == ["--allowedTools=" + ",".join(childrun.MOREME_ALLOWED_TOOLS)]
        assert "--no-session-persistence" not in f
    assert first[first.index("--session-id") + 1] == "abc" and "--resume" not in first
    assert later[later.index("--resume") + 1] == "abc" and "--session-id" not in later


def test_interviewee_flags_have_no_tools():
    f = drv.interviewee_flags()
    assert f[f.index("--tools") + 1] == ""
    assert "--no-session-persistence" in f
    assert not any(a.startswith("--allowedTools") for a in f)


def test_opener_is_text_not_slash_command():
    assert not drv.OPENER.startswith("/")
    assert "voice skill" in drv.OPENER


def _shingles(text, n=12):
    w = [x.lower() for x in WORD.findall(text)]
    return set(tuple(w[i:i + n]) for i in range(len(w) - n + 1))


def test_interviewee_brief_uses_train_text_only_and_no_author_name(temp):
    d, _ = drv.build_scratch("t1", "era-c", SPLIT)
    brief = drv.interviewee_brief("era-c", d)
    for rel in drv.PERSONAS["era-c"]["give_files"]:
        assert rel in brief
    assert "Project folder." in brief
    assert drv.PERSONAS["era-c"]["task"] in brief
    for name in ("Stewart", "Elinore", "Pruitt", "Gutenberg"):
        assert name not in brief.replace("Mr. Stewart", "")  # a neighbor's name inside the excerpts is fine
    held = set()
    for doc in SPLIT["personas"]["era-c"]["documents"]:
        if doc["split"] != "train":
            held |= _shingles((REPO / "eval" / "corpus" / doc["file"]).read_text(encoding="utf-8"))
    assert not (_shingles(brief) & held)


def test_give_files_are_train_files():
    train = set("my-writing/" + Path(x["file"]).name for x in SPLIT["personas"]["era-c"]["documents"]
                if x["split"] == "train")
    assert set(drv.PERSONAS["era-c"]["give_files"]) <= train


def test_expected_skills_adds_my_voice_after_install(tmp_path):
    assert drv.expected_skills(tmp_path) == ["moreme"]
    p = tmp_path / ".claude" / "skills" / "my-voice"
    p.mkdir(parents=True)
    (p / "SKILL.md").write_text("x", encoding="utf-8")
    assert drv.expected_skills(tmp_path) == ["moreme", "my-voice"]


def test_stage_timings():
    turns = [
        {"wall_start": 0.0, "latency_s": 10.0, "steps_done": []},
        {"wall_start": 10.0, "latency_s": 5.0},
        {"wall_start": 15.0, "latency_s": 20.0, "steps_done": ["1"]},
        {"wall_start": 35.0, "latency_s": 40.0, "steps_done": ["2", "3"]},
    ]
    assert drv.stage_timings(turns) == [{"stage": 1, "seconds": 35.0}, {"stage": 2, "seconds": 40.0},
                                        {"stage": 3, "seconds": 0.0}]


def test_render_is_verbatim(tmp_path, monkeypatch):
    run = tmp_path / "r1"
    (run / "logs").mkdir(parents=True)
    events = [
        {"type": "system", "subtype": "init", "skills": ["moreme"], "model": "claude-sonnet-5-5"},
        {"type": "assistant", "parent_tool_use_id": None, "message": {"content": [
            {"type": "text", "text": "Question 1 ```odd``` text"},
            {"type": "tool_use", "id": "tu1", "name": "Bash", "input": {"command": "python --version"}}]}},
        {"type": "user", "parent_tool_use_id": None, "message": {"content": [
            {"type": "tool_result", "tool_use_id": "tu1", "content": "Python 3.11.9", "is_error": False}]}},
    ]
    (run / "logs" / "skill-t00.jsonl").write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    ledger = tmp_path / "calls.jsonl"
    ledger.write_text(json.dumps({"kind": "call", "run_id": "r1", "label": "skill-t00", "model": "claude-sonnet-5-5",
                                  "skill_calls": ["moreme"]}) + "\n", encoding="utf-8")
    monkeypatch.setattr(drv, "LEDGER", ledger)
    manifest = {"run_id": "r1", "license_header": "HDR", "banner_source": "public-domain texts by X",
                "started": "s", "finished": "f", "cli_version": "2.1.303 (Claude Code)",
                "model_pinned": "claude-sonnet-5-5", "persona": "era-c", "train_files_in_scratch": ["a"],
                "session_id": "sid", "scratch": "C:/x", "status": "completed", "spill_new": [],
                "skill_flags_first": drv.skill_flags("sid", True), "interviewee_flags": drv.interviewee_flags(),
                "env_removed": "CLAUDE*", "env_set_after_scrub": childrun.ENV_SET_AFTER_SCRUB,
                "scratch_settings": childrun.scratch_settings(), "stage_timings": [{"stage": 1, "seconds": 3}],
                "turns": [{"turn": 0, "role": "skill", "label": "skill-t00", "user": drv.OPENER, "latency_s": 1,
                           "num_turns": 2}]}
    (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    text = drv.render(run).read_text(encoding="utf-8")
    assert text.startswith("<!-- HDR -->")
    assert "Interviewee simulated by an AI agent; writing samples are public-domain texts by X." in text
    assert "Question 1 ```odd``` text" in text
    assert "````text" in text
    assert "Python 3.11.9" in text
    assert "2.1.303 (Claude Code)" in text
    assert "--setting-sources project --strict-mcp-config" in text


def test_rubric_file_has_every_item():
    text = (REPO / "docs" / "e2e-rubric.md").read_text(encoding="utf-8")
    for item in ("R1-R6 Stage exits", "R7 Script calls", "R8 No unexpected tool or permission failures",
                 "R9 No unnecessary clarification turns", "R10 Blind A/B integrity"):
        assert item in text
    assert "project_is_home" in text and "pick up at step N" in text
