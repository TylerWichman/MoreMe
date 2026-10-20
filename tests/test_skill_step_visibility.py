"""SKILL.md contract for step visibility and the user's name (T-010).

The T-006 e2e run showed Steps 2 to 4 running in one turn with no chat text, and both A/B drafts
signed with a name taken from the OS user folder. These tests pin the instructions that fix both.
"""

import getpass
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "moreme" / "SKILL.md"
BLIND_AB = REPO / "moreme" / "reference" / "blind-ab.md"
NOTES_GUIDE = REPO / "moreme" / "reference" / "voice-notes-guide.md"
TEMPLATE = REPO / "moreme" / "templates" / "my-voice" / "SKILL.md.tmpl"
STAGES = ["Interview", "Sample", "Analysis", "Generate", "Blind A/B", "Install"]
NAME_SENTENCE = ("Never take a name from a username, a file path, or system details. "
                 "If you do not know the writer's name, sign off without one.")


def _body():
    text = SKILL.read_text(encoding="utf-8")
    return text[text.index("\n---\n", 4) + 5:]


def _flat(s):
    return re.sub(r"\s+", " ", s)


def _section(body, start, end_prefix="\n## "):
    i = body.index(start)
    j = body.find(end_prefix, i + len(start))
    return body[i:] if j < 0 else body[i:j]


def _steps(body):
    return {n: _section(body, "## Step %d of 6:" % n) for n in range(1, 7)}


# -- Step visibility: turn-ending messages carry the step lines (T-010, T-012, T-013) ----


def test_visibility_section_comes_before_the_steps():
    body = _body()
    assert "## Show every step in chat (required)" in body
    assert body.index("## Show every step in chat") < body.index("## Step 1 of 6:")


def test_visibility_rules_use_turn_ending_messages():
    sec = _flat(_section(_body(), "## Show every step in chat"))
    assert "The user sees only your chat text" in sec
    assert "Put what the user must see in the message that ends your turn" in sec
    assert ("appear in chat no later than the next message that asks the user to act") in sec
    where = sec[sec.index("**Where they land at the latest.**"):]
    for phrase in ("Step 1: opening in the first message, done line in the message asking for samples.",
                   "Steps 2 and 3: in the Step 3 report message, which ends with the check-in question.",
                   "Step 4: in the message asking for the A/B task.",
                   "Step 5: in or before the install question.",
                   "Step 6: in the closing message."):
        assert phrase in where, phrase
    assert "Step 3's full report go in your chat text" in sec


def test_visibility_adds_no_questions():
    sec = _section(_body(), "## Show every step in chat")
    assert "?" not in sec
    assert "not extra questions" in sec and "Ask only the questions this file lists." in sec


def test_each_step_has_opening_line_and_logged_exit():
    steps = _steps(_body())
    for n, name in enumerate(STAGES, start=1):
        sec = _flat(steps[n])
        first_item = sec[sec.index("1. "):][:400]
        assert "Say" in first_item or "say:" in first_item or "First reply" in first_item, n
        exit_line = sec[sec.index("**Exit check:**"):]
        assert "stage=%d name=" % n in exit_line, n
        done = "`Step %d of 6 done: %s.`" % (n, name)
        assert done in sec, n


def test_stage_exit_order_documented():
    body = _flat(_body())
    sec = body[body.index("### Stage exit lines"):]
    assert sec.index("A new last line in `moreme-output/run-log.md`") < sec.index(
        "Then a chat line, exactly: `Step N of 6 done: <Name>.`")


def test_step2_word_count_shown_in_chat():
    s2 = _flat(_steps(_body())[2])
    assert "write the running count as chat text" in s2


def test_step1_first_turn_uses_no_tools():
    s1 = _flat(_steps(_body())[1])
    item1 = s1[s1.index("1. "):s1.index("2. **After the user's first answer:**")]
    assert item1.startswith("1. **First reply: no tools at all.**")
    assert "about 10 minutes" in item1
    intro = item1.index("MoreMe asks five short questions")
    perm_ref = item1.index("then the permissions sentence below, word for word")
    q1 = item1.index("then question 1 (item 3). End your turn there.")
    perm = item1.index("Claude Code may ask your permission a few times")
    assert intro < perm_ref < q1 < perm
    # No tool instruction before question 1.
    before_q1 = item1[:q1]
    for tool_word in ("Glob", "Write", "Read", "Run ", "PREFIX", ".gitignore"):
        assert tool_word not in before_q1, tool_word


def test_glob_and_gitignore_after_first_answer():
    body = _flat(_body())
    rules = body[body.index("## Ground rules"):body.index("### Stage exit lines")]
    assert ("**Earlier run:** right after the user's first answer (never before it), Glob for "
            "`moreme-output/run-log.md`.") in rules
    s1 = _flat(_steps(_body())[1])
    item2 = s1[s1.index("2. **After the user's first answer:**"):s1.index("3. Ask these five questions")]
    assert item2.index("Glob for an earlier run") < item2.index("Write `moreme-output/.gitignore`") < item2.index(
        "Then ask question 2.")
    ts = _flat((REPO / "moreme" / "reference" / "troubleshooting.md").read_text(encoding="utf-8"))
    assert "Right after the user's first interview answer (the first reply uses no tools)" in ts
    assert "At the start, Glob" not in ts


def test_step3_report_message_ends_turn_with_checkin():
    body = _flat(_body())
    s3 = _flat(_steps(_body())[3])
    read = s3.index("5. Read `moreme-output/report.txt`. Then log Step 3 in `run-log.md`")
    msg = s3.index("6. **Report message (ends your turn),** in this order:")
    prev = s3.index("- `Step 2 of 6 done: Sample.` and this step's opening line, if not written yet")
    lead = s3.index("- the line: Here is what MoreMe measured in your writing:")
    full = s3.index("- the full text of `report.txt`, copied word for word")
    tie = s3.index("- one or two plain sentences tying it to their interview answers")
    done = s3.index("- `Step 3 of 6 done: Analysis.`")
    ask = s3.index("- the question: Does this sound like you? Reply yes, or tell me what's off.")
    fwd = s3.index("- last, Step 4's opening line: Next, I'll write your my-voice skill. It takes about a minute.")
    stop = s3.index("Then stop and wait for the reply. No Step 4 tool call before it.")
    save = s3.index("7. **Save the answer.**")
    assert read < msg < prev < lead < full < tie < done < ask < fwd < stop < save
    # The check-in sits before Step 4 starts.
    assert body.index("Does this sound like you?") < body.index("## Step 4 of 6:")
    assert "the user cannot see what Read returns" in s3


def test_checkin_answer_flows_to_voice_notes():
    s3 = _flat(_steps(_body())[3])
    assert ("Add it to the end of `moreme-output/interview.md` under `## Check-in after the report`, "
            "word for word. Accept it as given, with no follow-up. Step 4 uses it.") in s3
    s4 = _flat(_steps(_body())[4])
    assert ("If the Step 3 check-in says something is off, reflect it in How I sound, Do, or Don't; "
            "never change the measured numbers.") in s4
    guide = _flat(NOTES_GUIDE.read_text(encoding="utf-8"))
    assert "Read the `## Check-in after the report` answer in `interview.md`." in guide
    ig = _flat((REPO / "moreme" / "reference" / "interview-guide.md").read_text(encoding="utf-8"))
    assert "## Check-in after the report" in ig


def test_step4_lines_land_in_ab_task_message():
    s4 = _flat(_steps(_body())[4])
    assert "at the latest at the top of the A/B task message" in s4
    assert "In the message that asks for the A/B task (Step 5), tell the user" in s4
    s5 = _flat(_steps(_body())[5])
    assert s5.index("1. In the same message as the Step 4 done line and summary, say:") < s5.index(
        "Here are two drafts of the same message.")


# -- Defect 2: never infer the user's name ----------------------------------------


def test_skill_ground_rule_on_names():
    body = _flat(_body())
    rules = body[body.index("## Ground rules"):body.index("### Stage exit lines")]
    assert ("**The user's name:** never take it from a username, a file or folder path, the environment, "
            "or other system details.") in rules
    assert "gave it in the interview or this chat, or signed their samples with it" in rules
    assert "sign drafts with their usual sign-off and no name, or leave them unsigned" in rules


def test_shared_ab_rule_carries_name_sentence_everywhere():
    body = _flat(_body())
    ab = _flat(BLIND_AB.read_text(encoding="utf-8"))
    assert NAME_SENTENCE in body
    assert ab.count(NAME_SENTENCE) == 2  # the shared rule block and the subagent prompt
    rule = re.search(r'The shared rule for both drafts \(use the same words in both\): "([^"]+)"', body).group(1)
    assert rule.endswith(NAME_SENTENCE)
    assert rule in ab


def test_with_draft_and_notes_guide_follow_name_rule():
    body = _flat(_body())
    assert "Sign with a name only as \"The user's name\" in Ground rules allows." in body
    ab = _flat(BLIND_AB.read_text(encoding="utf-8"))
    assert "never take it from a username, a folder path, or system details" in ab
    guide = _flat(NOTES_GUIDE.read_text(encoding="utf-8"))
    assert "Never take it from a username, a folder path, or system details." in guide


def test_my_voice_template_has_name_rule():
    text = _flat(TEMPLATE.read_text(encoding="utf-8"))
    rules = text[text.index("## Rules for Claude"):]
    assert ("Never take the user's name from a username, a file or folder path, or other system details."
            in rules)
    assert "Otherwise use the sign-off without a name, or leave the draft unsigned." in rules


def test_no_os_username_in_skill_files():
    try:
        user = getpass.getuser()
    except Exception:
        return
    if not user or len(user) < 3:
        return
    pattern = re.compile(r"\b" + re.escape(user) + r"\b", re.I)
    files = [SKILL, TEMPLATE] + sorted((REPO / "moreme" / "reference").glob("*.md"))
    for path in files:
        assert not pattern.search(path.read_text(encoding="utf-8")), path.name
