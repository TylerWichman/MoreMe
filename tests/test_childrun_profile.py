"""Child-run library: isolation profile, env order, scratch builder, train-only check.

No model calls. Fake homes and scratch roots live under tmp_path.
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "eval"))
from lib import childrun  # noqa: E402

CORPUS = REPO / "eval" / "corpus"
SPLIT = json.loads((REPO / "eval" / "split.json").read_text(encoding="utf-8"))


def test_env_scrub_happens_before_guard_vars_are_set():
    base = {
        "PATH": "x",
        "CLAUDECODE": "1",
        "CLAUDE_CODE_ENTRYPOINT": "cli",
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "0",
        "claude_pid": "42",
        "AI_AGENT": "claude",
        "MOREME_TEST_GUARD": "0",
    }
    env = childrun.child_env(base)
    assert env["PATH"] == "x"
    for gone in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "claude_pid", "AI_AGENT"):
        assert gone not in env
    assert env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] == "1"
    assert env["DISABLE_AUTOUPDATER"] == "1"
    assert env["MOREME_TEST_GUARD"] == "1"
    claude_keys = [k for k in env if k.upper().startswith("CLAUDE")]
    assert claude_keys == ["CLAUDE_CODE_DISABLE_AUTO_MEMORY"]


def test_scratch_settings_match_sub004_plus_auto_memory():
    s = childrun.scratch_settings(home_dir=r"C:\Users\someone")
    assert s["enabledPlugins"] == {
        "cc-plugin-agents-md@builtin": False,
        "cc-plugin-telemetry@builtin": False,
        "cc-plugin-plugin-authoring@builtin": False,
    }
    assert s["disableBundledSkills"] is True
    assert s["skillOverrides"] == {"design": "off", "doctor": "off"}
    assert s["autoMemoryEnabled"] is False
    assert s["permissions"]["deny"] == [
        "Edit(~/.claude/**)",
        "Write(~/.claude/**)",
        "Edit(//c/Users/someone/.claude/**)",
        "Write(//c/Users/someone/.claude/**)",
    ]


def test_real_home_deny_form_is_derived_not_hardcoded():
    s = childrun.scratch_settings()
    expect = childrun.to_slash_abs(childrun.home() / ".claude")
    assert "Write(%s/**)" % expect in s["permissions"]["deny"]


def test_allowed_tools_are_narrow():
    allowed = childrun.MOREME_ALLOWED_TOOLS
    assert "Skill(moreme)" in allowed
    for a in allowed:
        assert a not in ("Bash", "Bash(python:*)", "Bash(py:*)", "Bash(python3:*)")
        if a.startswith("Bash(") and a.endswith(":*)"):
            assert "analyze.py" in a


def test_project_folder_name_matches_claude_code_naming():
    name = childrun.project_folder_name(r"C:\Users\someone\AppData\Local\Temp\moreme-e2e\run_1")
    assert name == "C--Users-someone-AppData-Local-Temp-moreme-e2e-run-1"


def test_make_scratch_layout(tmp_path):
    skill_src = tmp_path / "src" / "moreme"
    (skill_src / "__pycache__").mkdir(parents=True)
    (skill_src / "SKILL.md").write_text("x", encoding="utf-8")
    (skill_src / "__pycache__" / "a.pyc").write_bytes(b"\0")
    d = childrun.make_scratch("moreme-e2e", "t1", skills={"moreme": skill_src},
                              texts={"my-writing/a.txt": "hello"}, base=tmp_path / "temp")
    assert d == tmp_path / "temp" / "moreme-e2e" / "t1"
    assert (d / ".claude" / "skills" / "moreme" / "SKILL.md").exists()
    assert not (d / ".claude" / "skills" / "moreme" / "__pycache__").exists()
    settings = json.loads((d / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert settings["autoMemoryEnabled"] is False
    with pytest.raises(ValueError):
        childrun.scratch_root("elsewhere")
    with pytest.raises(childrun.ScratchError):
        childrun.make_scratch("moreme-e2e", "../escape", base=tmp_path / "temp")


def test_make_scratch_refuses_git_repo(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    with pytest.raises(childrun.ScratchError):
        childrun.make_scratch("moreme-e2e", "t1", base=tmp_path / "repo")


def _train_files(persona):
    return [d["file"] for d in SPLIT["personas"][persona]["documents"] if d["split"] == "train"]


def _other_files(persona):
    return [d["file"] for d in SPLIT["personas"][persona]["documents"] if d["split"] != "train"]


def test_train_only_passes_with_train_files(tmp_path):
    files = dict(("my-writing/" + Path(f).name, CORPUS / f) for f in _train_files("era-c"))
    d = childrun.make_scratch("moreme-e2e", "t1", files=files, base=tmp_path)
    found = childrun.assert_train_only(d, CORPUS, SPLIT, persona="era-c")
    assert found == sorted(_train_files("era-c"))


def test_train_only_catches_renamed_heldout_text(tmp_path):
    heldout = _other_files("era-c")[0]
    d = childrun.make_scratch("moreme-e2e", "t1", files={"my-writing/innocent.txt": CORPUS / heldout},
                              base=tmp_path)
    with pytest.raises(childrun.ScratchError):
        childrun.assert_train_only(d, CORPUS, SPLIT, persona="era-c")


def test_train_only_catches_heldout_name(tmp_path):
    name = Path(_other_files("era-c")[0]).name
    d = childrun.make_scratch("moreme-e2e", "t1", texts={"x/" + name: "different text"}, base=tmp_path)
    with pytest.raises(childrun.ScratchError):
        childrun.assert_train_only(d, CORPUS, SPLIT, persona="era-c")
