"""Guided writing sample (AMEND-003, T-014).

MoreMe no longer asks for pasted writing or files. The five interview answers and 4 to 6 adaptive
writing prompts form one conversation; the user's own words are saved verbatim to
samples/conversation.txt and measured from there.
"""

import re
import shutil
from pathlib import Path

from conftest import FIXTURES

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "moreme" / "SKILL.md"
REFERENCE = REPO / "moreme" / "reference"
ALLOWED_PASTE_CONTEXT = ("never", "offers to paste")


def _body():
    text = SKILL.read_text(encoding="utf-8")
    return text[text.index("\n---\n", 4) + 5:]


def _flat(s):
    return re.sub(r"\s+", " ", s)


def _step(n):
    body = _body()
    i = body.index("## Step %d of 6:" % n)
    j = body.find("\n## ", i + 5)
    return _flat(body[i:j])


def _skill_files():
    return [SKILL] + sorted(REFERENCE.glob("*.md"))


def test_no_paste_or_file_instructions_anywhere():
    for path in _skill_files():
        for line in path.read_text(encoding="utf-8").splitlines():
            low = line.lower()
            if "paste" in low:
                assert any(c in low for c in ALLOWED_PASTE_CONTEXT), (path.name, line)
            for gone in ("file paths", "sample-01", "sample-nn", "3 pieces", "three or more things"):
                assert gone not in low, (path.name, gone)
    assert "Never ask them to paste or share existing writing or files." in _flat(_body())


def test_frontmatter_and_time_estimate():
    text = SKILL.read_text(encoding="utf-8")
    assert "a few writing prompts" in text.split("\n---\n", 1)[0]
    body = _flat(_body())
    assert "about 12 to 15 minutes" in body
    assert "10 minutes" not in body
    assert "## Step 2 of 6: Sample (about 5 minutes)" in _body()


def test_interview_answers_start_the_sample():
    s1 = _step(1)
    assert "their answers count, so answer the way they normally type" in s1
    assert ("Also Write `moreme-output/samples/conversation.txt` with the five answers: the user's words only, "
            "word for word, a blank line between answers, none of your text.") in s1
    assert "at the latest at the top of the first writing prompt" in s1


def test_adaptive_prompt_loop():
    s2 = _step(2)
    assert "The sample is this conversation" in s2
    assert "**Prompt loop.** One prompt per message" in s2
    assert "each following from the user's last answer and leaning toward what they write (answer 1)" in s2
    for kind in ("a short story", "explaining something to a coworker or friend",
                 "a reply they would really send", "an opinion with a reason"):
        assert kind in s2, kind
    assert "Never scold." in s2


def test_300_word_target_and_progress_cue():
    s2 = _step(2)
    assert "**Stop at about 300 words,** usually after 4 to 6 prompts." in s2
    assert "At most 8 prompts" in s2 and "reason=below_floor" in s2
    assert "running total, interview answers included" in s2
    assert "About 120 of 300 words so far." in s2


def test_answers_saved_verbatim_without_assistant_text():
    s2 = _step(2)
    assert ("**Save each answer** to the end of `moreme-output/samples/conversation.txt` (Write or Edit): "
            "the user's words only, word for word, typos kept") in s2
    sa = _flat((REFERENCE / "samples-and-analysis.md").read_text(encoding="utf-8"))
    assert "Never add your prompts, labels, or fixes." in sa


def test_stopping_early_is_explained_then_degraded():
    s2 = _step(2)
    assert "fewer words make the measurement less reliable" in s2
    assert "status=degraded reason=user_stopped_early" in s2


def test_profile_measures_conversation_file():
    s3 = _step(3)
    assert "PREFIX profile moreme-output/samples/conversation.txt --out moreme-output/profile.json" in s3


def test_voice_notes_excerpts_name_conversation_file():
    assert "(`[conversation.txt]`, then 40 to 120 words copied exactly)" in _step(4)
    guide = _flat((REFERENCE / "voice-notes-guide.md").read_text(encoding="utf-8"))
    assert "`[conversation.txt]` on its own line" in guide
    assert "an excerpt may run across two answers next to each other" in guide


def test_build_skill_from_single_conversation_file(cli, tmp_path):
    src = FIXTURES / "build"
    out = tmp_path / "moreme-output"
    (out / "samples").mkdir(parents=True)
    shutil.copyfile(str(src / "profile.json"), str(out / "profile.json"))
    parts = [p.read_text(encoding="utf-8").strip() for p in sorted((src / "samples").glob("*.txt"))]
    (out / "samples" / "conversation.txt").write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    notes = re.sub(r"\[sample-\d\d\.txt\]", "[conversation.txt]", (src / "voice-notes.md").read_text("utf-8"))
    (out / "voice-notes.md").write_text(notes, encoding="utf-8")
    res = cli("build-skill", out / "profile.json", out / "voice-notes.md", "--samples", out / "samples",
              "--out", out, "--date", "2026-10-20")
    assert res.json["ok"] is True, res.json["errors"]
    text = (out / "my-voice" / "SKILL.md").read_text(encoding="utf-8")
    assert "From conversation.txt:" in text


def test_too_few_excerpts_message_names_conversation_file(cli, tmp_path):
    out = tmp_path / "moreme-output"
    shutil.copytree(str(FIXTURES / "build"), str(out))
    text = (out / "voice-notes.md").read_text("utf-8")
    start = text.index("[sample-03.txt]")
    end = text.index("## Adjust by channel")
    (out / "voice-notes.md").write_text(text[:start] + "\n" + text[end:], encoding="utf-8")
    res = cli("build-skill", out / "profile.json", out / "voice-notes.md", "--samples", out / "samples",
              "--out", out, "--date", "2026-10-20")
    messages = [e["message"] for e in res.json["errors"] if e["code"] == "notes_count_out_of_range"]
    assert any("like [conversation.txt]" in m for m in messages), messages


def test_never_question_authorship():
    body = _flat(_body())
    talk = body[body.index("## How to talk to the user"):body.index("## Ground rules")]
    assert ("Never ask whether the user wrote an answer themselves or where it came from. "
            "Every answer counts as their writing.") in talk
    sa = _flat((REFERENCE / "samples-and-analysis.md").read_text(encoding="utf-8"))
    assert "Never ask whether they wrote it or where it came from" in sa
    for path in _skill_files():
        low = _flat(path.read_text(encoding="utf-8")).lower()
        for phrase in ("ask once whether they wrote", "clearly not the user's own", "clearly did not write",
                       "whether they have something they wrote alone"):
            assert phrase not in low, (path.name, phrase)
