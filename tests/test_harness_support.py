"""Shared helpers for the eval harness tests: a fake `claude` CLI and a runner
context. No test lives here. Nothing in these tests calls a model.

The fake CLI reads the prompt on stdin, lists the scratch project's
.claude/skills folders as the init event's skills, calls the my-voice skill when
it is installed, and answers with a short draft. FAKE_BEHAVIOR changes that:

    ok              valid draft (default)
    refuse_first    first call for each unit refuses, later calls are fine
    other_skill     calls a skill named "other" as well
    limit_after:N   calls after the Nth return a usage-limit error
    no_invoke       never calls the skill
"""
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EVAL = REPO / "eval"
if str(EVAL) not in sys.path:
    sys.path.insert(0, str(EVAL))

FAKE_CLAUDE = r'''
import json, os, sys
from pathlib import Path
prompt = sys.stdin.read()
state = Path(os.environ["FAKE_STATE"])
n = int(state.read_text()) + 1 if state.exists() else 1
state.write_text(str(n))
behavior = os.environ.get("FAKE_BEHAVIOR", "ok")
cwd = Path.cwd()
sk = cwd / ".claude" / "skills"
skills = sorted(p.name for p in sk.iterdir()) if sk.is_dir() else []
def emit(o):
    sys.stdout.write(json.dumps(o) + "\n")
emit({"type": "system", "subtype": "init", "skills": skills, "plugins": [], "mcp_servers": [],
      "claude_code_version": "2.1.303", "model": "claude-sonnet-5-5", "session_id": "s%d" % n})
if behavior.startswith("limit_after:") and n > int(behavior.split(":")[1]):
    emit({"type": "result", "subtype": "error", "is_error": True, "result": "Claude usage limit reached",
          "session_id": "s%d" % n})
    sys.exit(1)
if skills and behavior != "no_invoke":
    emit({"type": "assistant", "parent_tool_use_id": None, "message": {"content": [
        {"type": "tool_use", "id": "t1", "name": "Skill", "input": {"skill": "my-voice"}}]}})
    emit({"type": "user", "parent_tool_use_id": None, "message": {"content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": "loaded"}]}})
if behavior == "other_skill":
    emit({"type": "assistant", "parent_tool_use_id": None, "message": {"content": [
        {"type": "tool_use", "id": "t2", "name": "Skill", "input": {"skill": "other"}}]}})
marks = Path(os.environ["FAKE_STATE"] + ".units")
seen = marks.read_text().split("\n") if marks.exists() else []
key = cwd.name.rsplit("-a", 1)[0]
if behavior == "refuse_first" and key not in seen:
    marks.write_text("\n".join(seen + [key]))
    text = "I can't help with that."
else:
    text = "Here's the draft:\n\n---\n" + "Dear friend, the garden is coming along and the beans are up. " * 3
emit({"type": "assistant", "parent_tool_use_id": None, "message": {"content": [{"type": "text", "text": text}]}})
emit({"type": "result", "subtype": "success", "is_error": False, "result": text, "session_id": "s%d" % n,
      "num_turns": 1})
'''


def make_fake(tmp_path, behavior="ok", monkeypatch=None):
    script = tmp_path / "fake_claude.py"
    script.write_text(FAKE_CLAUDE, encoding="utf-8")
    state = tmp_path / "fake_state.txt"
    if monkeypatch is not None:
        monkeypatch.setenv("FAKE_STATE", str(state))
        monkeypatch.setenv("FAKE_BEHAVIOR", behavior)
    return [sys.executable, str(script)], state


def fake_skill(tmp_path):
    d = tmp_path / "skill-src" / "my-voice"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: my-voice\ndescription: test skill\n---\n# My voice\n", encoding="utf-8")
    return d


def run_kwargs(tmp_path, claude, persona="era-c"):
    home = tmp_path / "home"
    (home / ".claude" / "projects").mkdir(parents=True, exist_ok=True)
    return dict(claude=claude, home_dir=home, scratch_base=tmp_path / "temp",
                skill_dirs={persona: fake_skill(tmp_path)}, log=lambda *a: None)


def ledger_rows(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def first_task(persona="era-c", which="dev"):
    from harness import tasks
    return tasks.select(tasks.load(), persona, which)[0]["id"]
