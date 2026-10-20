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


# -- Defect 1: every step is visible in chat ------------------------------------


def test_visibility_section_comes_before_the_steps():
    body = _body()
    assert "## Show every step in chat (required)" in body
    assert body.index("## Show every step in chat") < body.index("## Step 1 of 6:")


def test_visibility_rules_are_explicit():
    sec = _flat(_section(_body(), "## Show every step in chat"))
    assert "The user sees only your chat text." in sec
    assert "Before the step's first tool call, write its opening line" in sec
    assert "After the step's last tool call" in sec
    assert "write `Step N of 6 done: <Name>.` as chat text, before any tool call of the next step" in sec
    assert "Step 3's full report go in your chat text" in sec
    assert "This holds inside one long turn." in sec
    assert "Steps 2, 3, and 4" in sec
    assert "Never run a step's tool calls silently" in sec


def test_visibility_adds_no_questions():
    sec = _section(_body(), "## Show every step in chat")
    assert "?" not in sec
    assert "not questions" in sec and "without waiting for a reply" in sec


def test_each_step_has_opening_line_and_ordered_exit():
    steps = _steps(_body())
    for n, name in enumerate(STAGES, start=1):
        sec = _flat(steps[n])
        first_item = sec[sec.index("1. "):][:400]
        assert "Say" in first_item or "first message" in first_item, n
        exit_line = sec[sec.index("**Exit check:**"):]
        log = exit_line.index("Log it, for example `stage=%d " % n)
        done = exit_line.index("Then write `Step %d of 6 done: %s.` as chat text." % (n, name))
        assert log < done, n


def test_stage_exit_order_documented():
    body = _flat(_body())
    sec = body[body.index("### Stage exit lines"):]
    assert sec.index("A new last line in `moreme-output/run-log.md`") < sec.index(
        "Then a chat line, exactly: `Step N of 6 done: <Name>.`")


def test_step2_word_count_and_step3_report_shown_in_chat():
    steps = _steps(_body())
    s2 = _flat(steps[2])
    assert "write the running count as chat text" in s2
    s3 = _flat(steps[3])
    assert "copy its full text, unchanged, into your chat message" in s3
    assert "The user cannot see what Read returns" in s3
    assert "Tell the user in chat" in _flat(steps[4])


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
