"""Child-run library: init assertion, skill invariant, guards, spill count,
invalid-unit detector, ledger healing, and the runner against a fake CLI.

No model calls.
"""
import json
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "eval"))
from lib import childrun  # noqa: E402

GOOD_INIT = {"type": "system", "subtype": "init", "skills": ["moreme"], "plugins": [], "mcp_servers": [],
             "claude_code_version": "2.1.303", "model": "claude-sonnet-5-5", "memory_paths": {}}


def test_init_assertion_passes_exact_set():
    assert childrun.check_init(GOOD_INIT, ["moreme"]) == []


@pytest.mark.parametrize("change", [
    {"skills": ["moreme", "design"]},
    {"skills": []},
    {"plugins": [{"name": "x"}]},
    {"mcp_servers": [{"name": "y", "status": "connected"}]},
    {"claude_code_version": "2.1.304"},
])
def test_init_assertion_fails(change):
    init = dict(GOOD_INIT, **change)
    assert childrun.check_init(init, ["moreme"])


def test_init_missing_is_a_failure():
    assert childrun.check_init(None, ["moreme"]) == ["no_init_event"]


def test_memory_check(tmp_path):
    mem = tmp_path / "memory"
    init = dict(GOOD_INIT, memory_paths={"auto": str(mem)})
    assert childrun.memory_problems(init) == []
    mem.mkdir()
    assert childrun.memory_problems(init) == []
    (mem / "MEMORY.md").write_text("x", encoding="utf-8")
    assert childrun.memory_problems(init) == ["auto_memory_written:auto"]


def _assistant(content, parent=None):
    return {"type": "assistant", "parent_tool_use_id": parent, "message": {"content": content}}


def test_skill_invariant_sees_subagent_calls():
    events = [
        _assistant([{"type": "tool_use", "id": "1", "name": "Skill", "input": {"skill": "moreme"}}]),
        _assistant([{"type": "tool_use", "id": "2", "name": "Skill", "input": {"skill": "design"}}], parent="9"),
    ]
    assert childrun.skill_invariant(events, {"moreme"}) == ["design"]
    assert childrun.skill_invariant(events, {"moreme", "design"}) == []


def test_guard_halts_on_guarded_names(tmp_path):
    dirs = [tmp_path / "skills", tmp_path / "commands"]
    for d in dirs:
        d.mkdir()
    before = childrun.names_snapshot(dirs)
    (tmp_path / "skills" / "unrelated").mkdir()
    assert childrun.check_snapshot(before, childrun.names_snapshot(dirs))
    for name in ("my-voice", "voice-dana", "moreme", "MoreMe-copy", "My-Voice-2"):
        b = childrun.names_snapshot(dirs)
        (tmp_path / "commands" / name).mkdir()
        with pytest.raises(childrun.GuardHit):
            childrun.check_snapshot(b, childrun.names_snapshot(dirs))


def test_guard_never_opens_files(tmp_path, monkeypatch):
    d = tmp_path / "skills"
    d.mkdir()
    (d / "secret.txt").write_text("do not read", encoding="utf-8")

    def boom(*a, **k):
        raise AssertionError("file opened")

    monkeypatch.setattr("builtins.open", boom)
    names = childrun.names_snapshot([d])
    assert str(d / "secret.txt") in names


def test_spill_names_counts_only_moreme_entries(tmp_path):
    p = tmp_path / ".claude" / "projects"
    p.mkdir(parents=True)
    for n in ("C--Users-x-AppData-Local-Temp-moreme-e2e-r1", "C--Users-x-AppData-Local-Temp-moreme-eval-a",
              "C--Users-x-Documents-other"):
        (p / n).mkdir()
    assert childrun.spill_names(tmp_path) == {"C--Users-x-AppData-Local-Temp-moreme-e2e-r1",
                                              "C--Users-x-AppData-Local-Temp-moreme-eval-a"}


@pytest.mark.parametrize("text,reason", [
    ("", "empty"),
    ("   \n", "empty"),
    ('I couldn\'t find a skill called "my-voice" in this project, so here is a draft anyway.', "missing_skill"),
    ("The my-voice skill isn't installed here.", "missing_skill"),
    ("It looks like the skill is unavailable.", "missing_skill"),
    ("I can't help with that request.", "refusal"),
    ("I'm unable to help with this.", "refusal"),
    ("Hi team, the night shift rota is attached. Thanks, Dana", None),
    ("I can help you skill up the new hires next week.", None),
])
def test_invalid_reason(text, reason):
    assert childrun.invalid_reason(text) == reason


def test_ledger_quarantines_torn_tail(tmp_path):
    led = childrun.Ledger(tmp_path / "calls.jsonl")
    led.append({"kind": "call", "n": 1})
    with open(str(led.path), "a", encoding="utf-8") as f:
        f.write('{"kind": "call", "n": 2, "trunc')
    assert led.count() == 1
    led.append({"kind": "call", "n": 2})
    rows = led.rows()
    assert [r["n"] for r in rows] == [1, 2]
    assert led.quarantine.read_text(encoding="utf-8").startswith('{"kind": "call", "n": 2, "trunc')
    assert led.path.read_bytes().endswith(b"\n")


FAKE_CLI = textwrap.dedent('''
    import json, os, sys
    from pathlib import Path
    prompt = sys.stdin.read()
    home = Path(os.environ["FAKE_HOME_FOR_TEST"]) if "FAKE_HOME_FOR_TEST" in os.environ else None
    env_view = dict((k, os.environ.get(k)) for k in
                    ("CLAUDE_CODE_DISABLE_AUTO_MEMORY", "MOREME_TEST_GUARD", "DISABLE_AUTOUPDATER", "CLAUDECODE"))
    mode = Path("mode.txt").read_text() if Path("mode.txt").exists() else "ok"
    if mode == "guard":
        (Path(os.environ["GUARD_DIR_FOR_TEST"]) / "my-voice").mkdir()
    init = {"type": "system", "subtype": "init", "skills": ["moreme"], "plugins": [], "mcp_servers": [],
            "claude_code_version": "2.1.303", "model": "claude-sonnet-5-5", "session_id": "s1"}
    print(json.dumps(init))
    print(json.dumps({"type": "assistant", "parent_tool_use_id": None,
                      "message": {"content": [{"type": "text", "text": json.dumps({"env": env_view, "argv": sys.argv[1:], "prompt": prompt})}]}}))
    res = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 1, "session_id": "s1",
           "result": "ok", "total_cost_usd": 0.0}
    if mode == "limit":
        res.update(is_error=True, result="Claude AI usage limit reached")
    print(json.dumps(res))
''')


@pytest.fixture
def fake(tmp_path, monkeypatch):
    cli = tmp_path / "fake_claude.py"
    cli.write_text(FAKE_CLI, encoding="utf-8")
    home = tmp_path / "home"
    (home / ".claude" / "skills").mkdir(parents=True)
    (home / ".claude" / "projects").mkdir(parents=True)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("GUARD_DIR_FOR_TEST", str(home / ".claude" / "skills"))
    led = childrun.Ledger(tmp_path / "calls.jsonl")
    return dict(claude=[sys.executable, str(cli)], home=home, cwd=cwd, ledger=led, logs=tmp_path / "logs")


def _run(f, **kw):
    return childrun.run_claude("t", ["--model", "claude-sonnet-5-5", "--allowedTools=Skill(moreme)"], f["cwd"],
                               "hello prompt", f["ledger"], f["logs"], ["moreme"], claude=f["claude"],
                               home_dir=f["home"], **kw)


def test_runner_env_prompt_and_ledger(fake):
    r = _run(fake)
    seen = json.loads(r["text"])
    assert seen["prompt"] == "hello prompt"
    assert seen["env"] == {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "MOREME_TEST_GUARD": "1",
                           "DISABLE_AUTOUPDATER": "1", "CLAUDECODE": None}
    assert seen["argv"][:4] == ["-p", "--output-format", "stream-json", "--verbose"]
    assert r["invalid"] == []
    row = fake["ledger"].rows()[0]
    assert row["n"] == 1 and row["claude_code_version"] == "2.1.303" and row["guard_hits"] == []


def test_runner_rejects_split_variadic_flag(fake):
    with pytest.raises(ValueError):
        childrun.run_claude("t", ["--allowedTools", "Skill(moreme)"], fake["cwd"], "p", fake["ledger"],
                            fake["logs"], ["moreme"], claude=fake["claude"], home_dir=fake["home"])


def test_runner_budget(fake):
    _run(fake, max_calls=1)
    with pytest.raises(childrun.BudgetExceeded):
        _run(fake, max_calls=1)


def test_runner_guard_hit_halts_after_logging(fake):
    (fake["cwd"] / "mode.txt").write_text("guard", encoding="utf-8")
    with pytest.raises(childrun.GuardHit):
        _run(fake)
    assert fake["ledger"].rows()[0]["guard_hits"]


def test_runner_usage_limit(fake):
    (fake["cwd"] / "mode.txt").write_text("limit", encoding="utf-8")
    with pytest.raises(childrun.UsageLimit):
        _run(fake)
    assert fake["ledger"].count() == 1


def test_runner_marks_wrong_skill_set_invalid(fake):
    r = childrun.run_claude("t", [], fake["cwd"], "p", fake["ledger"], fake["logs"], [], claude=fake["claude"],
                            home_dir=fake["home"])
    assert any(x.startswith("init:skills=") for x in r["invalid"])
