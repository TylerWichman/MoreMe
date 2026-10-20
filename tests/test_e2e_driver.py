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


def test_scratch_has_only_skill_and_settings(temp):
    """AMEND-003: MoreMe never reads the user's files, so none are copied in."""
    d, found = drv.build_scratch("t1", "era-c", SPLIT)
    assert d == temp / "moreme-e2e" / "t1"
    assert found == []
    assert not (d / "my-writing").exists()
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
    for c in drv.passage_catalog("era-c"):
        assert "[%s] (%d words)" % (c["id"], c["words"]) in brief
    assert "USE:" in brief and "my-writing/" not in brief
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


# ------------------------------------------------------------- T-011 additions

def _a(*blocks):
    return {"type": "assistant", "parent_tool_use_id": None, "message": {"content": list(blocks)}}


def _t(text):
    return {"type": "text", "text": text}


def _u(name):
    return {"type": "tool_use", "id": name, "name": name, "input": {}}


def _good_turns(report_lines):
    names = drv.STAGE_NAMES
    t1 = [_a(_t("Step 1 of 6: five questions, about 3 minutes."), _u("Write")), _a(_t("Step 1 of 6 done: Interview.\n\nStep 2 of 6: paste three things you wrote. About 2 minutes."))]
    t2 = [_a(_t("Saving your samples now."), _u("Read"), _u("Write")),
          _a(_t("Saved 3 pieces, about 3,300 words.")), _a(_t("Step 2 of 6 done: Sample.")),
          _a(_t("Step 3 of 6: measuring your style, about 1 minute."), _u("Bash")),
          _a(_t("\n".join(report_lines))), _a(_t("Step 3 of 6 done: Analysis."))]
    rest = []
    for n in range(4, 7):
        rest += [_a(_t("Step %d of 6: next part." % n), _u("Bash")),
                 _a(_t("Step %d of 6 done: %s." % (n, names[n - 1])))]
    return [("I'd like to make my voice skill", t1), ("my-writing/a.txt", t2 + rest)]


def test_chat_visibility_passes_when_every_line_is_in_chat(tmp_path):
    report = tmp_path / "report.txt"
    lines = ["Your style", "Sentences: 21 words on average", "Commas: 80 per 1,000 words"]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cv = drv.chat_visibility(_good_turns(lines), report)
    assert cv["ok"] and cv["done_lines_in_order"]
    assert all(s["done"] and s["opening"] for s in cv["stages"])
    assert cv["stages"][1]["word_count"] and cv["stages"][2]["report_shown"]


def test_chat_visibility_fails_like_run_r1(tmp_path):
    """r1 shape: stages 2-4 ran in one turn with tool calls only; the done
    lines and the report lived in run-log.md writes, not in chat."""
    report = tmp_path / "report.txt"
    report.write_text("Your style\nSentences: 21 words on average\n", encoding="utf-8")
    t1 = [_a(_t("Step 1 of 6: questions."), _u("Write")), _a(_t("Step 1 of 6 done: Interview."))]
    silent = [_a(_u("Read"), _u("Write"), _u("Bash"), _u("Read"), _u("Write"), _u("Bash")),
              _a(_t("Here is your skill.")), _a(_t("Step 4 of 6 done: Generate."))]
    cv = drv.chat_visibility([("hi", t1), ("files", silent)], report)
    assert not cv["ok"]
    st = dict((s["stage"], s) for s in cv["stages"])
    assert st[1]["done"] and not st[2]["done"] and not st[3]["done"] and st[4]["done"]
    assert st[2]["word_count"] is False
    assert st[3]["report_shown"] is False


def test_chat_visibility_credits_opening_in_the_done_line_message(tmp_path):
    """SKILL.md lets the next step's opening line follow the done line in the
    same message; that text opens the next stage, and does not count for the
    stage that just ended."""
    t = [_a(_t("Step 1 of 6: questions."), _u("Write")),
         _a(_t("Step 1 of 6 done: Interview.\n\nNext, paste three things. About 2 minutes."))]
    t2 = [_a(_u("Write")), _a(_t("Step 2 of 6 done: Sample."))]
    cv = drv.chat_visibility([("hi", t), ("files", t2)], None)
    st = dict((s["stage"], s) for s in cv["stages"])
    assert st[2]["opening"] and st[2]["done"]
    assert st[3]["opening"] is False


def test_chat_visibility_exempts_only_the_skill_load():
    ok = [_a(_u("Skill")), _a(_t("Step 1 of 6: five questions, about 3 minutes."), _u("Glob"), _u("Write")),
          _a(_t("Step 1 of 6 done: Interview."))]
    late = [_a(_u("Skill"), _u("Glob"), _u("Write")), _a(_t("Question 1 of 5")),
            _a(_t("Step 1 of 6 done: Interview."))]
    assert drv.chat_visibility([("hi", ok)], None)["stages"][0]["opening"] is True
    assert drv.chat_visibility([("hi", late)], None)["stages"][0]["opening"] is False


def test_chat_visibility_t013_report_message_shape(tmp_path):
    """T-013 shape: Steps 2 and 3 end in one report message that holds the
    Step 2 done line, the Step 3 opening, the report, the Step 3 done line, and
    the check-in question; Step 4 tools come only after the user's reply."""
    report = tmp_path / "report.txt"
    lines = ["Here is your style", "Sentences: 17 words on average"]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    t1 = [_a(_t("MoreMe asks five questions. It takes about 10 minutes. Question 1?"))]
    t2 = [_a(_u("Glob"), _u("Write"), _t("Step 1 of 6 done: Interview.\n\nNext, paste three things. About 2 minutes."))]
    t3 = [_a(_t("Saving them."), _u("Read"), _u("Write")), _a(_t("That is 3 pieces, about 3,800 words.")),
          _a(_u("Bash"), _u("Bash"), _u("Read"), _u("Write")),
          _a(_t("Step 2 of 6 done: Sample.\n\nNext, MoreMe's script reads your samples.\n\n" + "\n".join(lines)
                + "\n\nStep 3 of 6 done: Analysis.\n\nDoes this sound like you? Reply yes, or tell me what's off."))]
    t4 = [_a(_t("Next, I'll write your skill. About a minute."), _u("Write"), _u("Bash")),
          _a(_t("Step 4 of 6 done: Generate.\n\nNext, a blind test. What short message should I draft?"))]
    cv = drv.chat_visibility([("go", t1), ("letters", t2), ("files", t3), ("yes", t4)], report)
    st = dict((s["stage"], s) for s in cv["stages"])
    for n in (1, 2, 3, 4):
        assert st[n]["opening"] and st[n]["done"] and st[n]["done_timely"], n
    assert st[2]["word_count"] and st[3]["report_shown"]


def test_chat_visibility_done_line_after_a_user_turn_is_late():
    t1 = [_a(_t("Intro, about 10 minutes. Question 1?"))]
    t2 = [_a(_u("Write"), _t("Thanks. Paste your files."))]
    t3 = [_a(_t("Step 1 of 6 done: Interview."))]
    cv = drv.chat_visibility([("go", t1), ("answer", t2), ("files", t3)], None)
    assert cv["stages"][0]["done"] and not cv["stages"][0]["done_timely"]


def test_chat_visibility_report_after_step4_tool_is_late(tmp_path):
    report = tmp_path / "report.txt"
    report.write_text("Line one of report\nLine two of report\n", encoding="utf-8")
    t = [_a(_t("Intro, about 10 minutes."), _u("Write"), _t("Step 1 of 6 done: Interview. Next, files.")),
         ]
    t2 = [_a(_u("Write"), _t("Step 2 of 6 done: Sample. Next, measuring.")),
          _a(_u("Bash"), _t("Step 3 of 6 done: Analysis.")),
          _a(_u("Write"), _t("Line one of report\nLine two of report"))]
    cv = drv.chat_visibility([("go", t), ("files", t2)], report)
    assert cv["stages"][2]["report_shown"] is False


def _intro_turn():
    return [_a(_t("MoreMe asks five questions. It takes about 12 minutes. Question 1?"))]


def test_chat_visibility_does_not_credit_next_steps_opening_r5_shape(tmp_path):
    """r5: the report message went Step 2 done, report, Step 3 done, check-in,
    Step 4 opening. Step 4's 'Next' line must not count as Step 3's opening."""
    report = tmp_path / "report.txt"
    report.write_text("Report line A\nReport line B\n", encoding="utf-8")
    t2 = [_a(_u("Write"), _t("Step 1 of 6 done: Interview.\n\nStep 2 of 6: a few prompts. About 5 minutes. "
                              "About 60 of 300 words so far. Tell me a story."))]
    t3 = [_a(_u("Write"), _u("Bash"), _u("Read")),
          _a(_t("Step 2 of 6 done: Sample.\n\nHere is what MoreMe measured:\nReport line A\nReport line B\n\n"
                "Step 3 of 6 done: Analysis.\n\nDoes this sound like you?\n\nNext, I'll write your skill. "
                "It takes about a minute."))]
    cv = drv.chat_visibility([("go", _intro_turn()), ("a", t2), ("story", t3)], report)
    st = dict((s["stage"], s) for s in cv["stages"])
    assert st[3]["opening"] is False
    assert st[4]["opening"] is True and st[3]["report_shown"] is True


def test_chat_visibility_opening_before_a_late_done_line_r4_shape(tmp_path):
    """r4: Step 3's opening came before the Step 2 done line, which landed in
    the report message; the opening was shown in time and counts."""
    t2 = [_a(_u("Write"), _t("Step 1 of 6 done: Interview.\n\nNext, a few prompts. About 5 minutes. Tell me."))]
    t3 = [_a(_t("Step 3 of 6: Analysis. Next, MoreMe's measuring script reads your samples."), _u("Bash")),
          _a(_t("Step 2 of 6 done: Sample.\n\nReport.\n\nStep 3 of 6 done: Analysis.\n\nDoes this sound like you?"))]
    cv = drv.chat_visibility([("go", _intro_turn()), ("a", t2), ("story", t3)], None)
    st = dict((s["stage"], s) for s in cv["stages"])
    assert st[3]["opening"] is True and st[3]["done_timely"] is True


def test_opening_line_shapes():
    assert drv.opening_line("Step 3 of 6: Analysis.", 3)
    assert drv.opening_line("Next, a quick test.", 5)
    assert drv.opening_line("**Last step:** install.", 6)
    assert drv.opening_line("This takes about 2 minutes.", 2)
    assert not drv.opening_line("Step 3 of 6 done: Analysis.", 3)
    assert not drv.opening_line("Here is what MoreMe measured in your writing:", 3)


def test_chat_visibility_ignores_subagent_and_tool_text():
    sub = {"type": "assistant", "parent_tool_use_id": "x",
           "message": {"content": [_t("Step 1 of 6 done: Interview.")]}}
    write = _a({"type": "tool_use", "id": "w", "name": "Write",
                "input": {"content": "Step 1 of 6 done: Interview."}})
    cv = drv.chat_visibility([("hi", [sub, write])], None)
    assert not cv["stages"][0]["done"]


def test_interviewee_brief_has_persona_first_name(temp):
    d, _ = drv.build_scratch("t1", "era-c", SPLIT)
    brief = drv.interviewee_brief("era-c", d)
    name = drv.PERSONAS["era-c"]["first_name"]
    assert "Your first name is %s." % name in brief
    assert "sign it %s" % name in brief
    assert "asks whether they sound like you" in brief


def test_raw_evidence_defaults_outside_tracked_tree():
    ledger = drv.LEDGER.resolve()
    ev = drv.evidence_run_dir("r9").resolve()
    for p in (ledger, ev):
        inside_repo = REPO.resolve() in p.parents
        assert not inside_repo or ".evidence" in p.parts
    assert ev.name == "r9"


def test_render_sanitizes_and_discloses(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO / "tools"))
    import sanitize_artifacts as sa
    fake = {"home": "C:\\Users\\zqxjones", "users": ["zqxjones"], "names": ["Zqxjones"], "emails": []}
    monkeypatch.setattr(sa, "_DEFAULT", sa.Sanitizer(fake))
    run = tmp_path / "r2"
    run.mkdir()
    logs = tmp_path / "ev-logs"
    logs.mkdir()
    events = [_a(_t("Love, Zqxjones"), {"type": "tool_use", "id": "g", "name": "Glob",
                                         "input": {"path": "C:\\Users\\zqxjones\\AppData\\Local\\Temp\\x"}})]
    (logs / "skill-t00.jsonl").write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    ledger = tmp_path / "calls.jsonl"
    ledger.write_text("", encoding="utf-8")
    monkeypatch.setattr(drv, "LEDGER", ledger)
    manifest = {"run_id": "r2", "license_header": "HDR", "banner_source": "PD texts", "started": "s",
                "cli_version": "2.1.303", "model_pinned": "m", "persona": "era-c", "persona_first_name": "Hattie",
                "train_files_in_scratch": [], "session_id": "sid",
                "scratch": "C:\\Users\\zqxjones\\AppData\\Local\\Temp\\moreme-e2e\\r2", "status": "completed",
                "skill_flags_first": ["--model", "m"], "interviewee_flags": ["--tools", ""], "env_removed": "x",
                "env_set_after_scrub": {}, "scratch_settings": {},
                "turns": [{"turn": 0, "role": "skill", "label": "skill-t00", "user": "hi", "latency_s": 1}],
                "chat_visibility": drv.chat_visibility([("hi", events)], None)}
    (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    text = drv.render(run, logs).read_text(encoding="utf-8")
    assert "zqxjones" not in text.lower()
    assert "Love, [name]" in text
    assert "~\\\\AppData" in text
    assert sa.DISCLOSURE in text
    assert "Persona first name (invented) | Hattie" in text
    assert "Chat-visible stage lines" in text


def test_export_example_adds_header_after_frontmatter(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    run = runs / "rx"
    (run / "output" / "my-voice").mkdir(parents=True)
    (run / "manifest.json").write_text(json.dumps({"persona": "era-c"}), encoding="utf-8")
    (run / "output" / "my-voice" / "SKILL.md").write_text("---\nname: my-voice\ndescription: d\n---\n\n# My voice\n",
                                                          encoding="utf-8")
    monkeypatch.setattr(drv, "RUNS", runs)
    p = drv.export_example("rx", tmp_path / "dest")
    text = p.read_text(encoding="utf-8")
    assert text.startswith("---\nname: my-voice\n")
    assert drv.license_header("era-c") in text


def test_rubric_has_chat_visibility_note():
    text = (REPO / "docs" / "e2e-rubric.md").read_text(encoding="utf-8")
    assert "Chat-visible stage lines" in text and "**Assistant:**" in text
    assert "e2e-20261020-r1" in text
    assert "Chat visibility" in drv.REVIEW_PROMPT and "chat_visibility" in drv.REVIEW_PROMPT
    assert "next assistant message that asks the user to act" in text
    assert "asks the user to do\nsomething" in drv.REVIEW_PROMPT or "asks the user to do something" in drv.REVIEW_PROMPT
    assert "check-in" in text and "check-in" in drv.REVIEW_PROMPT
    assert "Guided writing sample" in text and "Guided writing sample" in drv.REVIEW_PROMPT
    assert "about 300" in text and "Stop early" in text and "No paste step" in text
    assert "Sample composition (run validity)" in text and "75%" in text
