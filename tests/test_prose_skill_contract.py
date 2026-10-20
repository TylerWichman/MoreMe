"""moreme/SKILL.md follows the FROZEN 4 flow contract (T-004).

Checks the frontmatter, the narrow allowed-tools list, the six stages in order, the fixed
user-facing sentences, Python discovery order, the blind A/B mechanics, and the install routes.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "moreme" / "SKILL.md"
REFERENCE = REPO / "moreme" / "reference"

FROZEN_ALLOWED_TOOLS = (
    "Bash(python --version), Bash(py -3 --version), Bash(python3 --version), "
    "Bash(python .claude/skills/moreme/analyze.py:*), Bash(py -3 .claude/skills/moreme/analyze.py:*), "
    "Bash(python3 .claude/skills/moreme/analyze.py:*), Bash(python ~/.claude/skills/moreme/analyze.py:*), "
    "Bash(py -3 ~/.claude/skills/moreme/analyze.py:*), Bash(python3 ~/.claude/skills/moreme/analyze.py:*), "
    "Write(moreme-output/**), Edit(moreme-output/**)"
)

PERMISSION_CLAUDE_CODE = (
    "Claude Code may ask your permission a few times while MoreMe works. It may ask before saving "
    "files in a folder called moreme-output. It may also ask before running a small measuring script "
    "that came with MoreMe. Choose Yes. The script works only with your MoreMe files and sends nothing "
    "over the internet."
)
PERMISSION_CLAUDE_AI = (
    "Claude will run a small measuring script that came with MoreMe. It runs in Claude's sandbox, not "
    "on your computer. Your samples go there under Anthropic's terms."
)
FIXED_LINES = [
    "Next, MoreMe's measuring script reads your samples. If Claude Code asks, choose Yes.",
    "Here are two drafts of the same message. One used your new voice skill and one didn't.",
    "Which sounds more like you? Type A or B.",
    "Project folder: my-voice works only in this project. Personal folder: it works in every project.",
    "Claude Code is open in your home folder, so this project folder is also your personal skills "
    "folder. Choose the personal folder instead, and my-voice will work in every project.",
    "Do not use any skills.",
]
COMMANDS = [
    "PREFIX build-skill moreme-output/profile.json moreme-output/voice-notes.md --samples "
    "moreme-output/samples --out moreme-output",
    "PREFIX ab-shuffle --out moreme-output",
    "PREFIX ab-present moreme-output",
    "PREFIX ab-reveal moreme-output --pick",
    "PREFIX install moreme-output/my-voice",
    "PREFIX install moreme-output/my-voice --personal",
    "--out moreme-output/profile.json",
    "PREFIX report moreme-output/profile.json --out moreme-output/report.txt",
]
STAGES = ["Interview", "Sample", "Analysis", "Generate", "Blind A/B", "Install"]
FORBIDDEN_TOKENS = ("scoring_only", "function_word_freq", "char3_freq", "delta_fw",
                    "char3_cosine", "reference_stats")


def _split():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    end = text.index("\n---\n", 4)
    fm = {}
    for line in text[4:end].splitlines():
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip()
    return fm, text[end + 5:]


def _flat(s):
    return re.sub(r"\s+", " ", s.replace("> ", " "))


def test_frontmatter_name_and_description():
    fm, _ = _split()
    assert fm["name"] == "moreme"
    desc = fm["description"]
    assert 0 < len(desc) < 1024
    assert "my-voice" in desc and "write like them" in desc and "voice skill" in desc


def test_allowed_tools_exact_and_narrow():
    fm, _ = _split()
    assert fm["allowed-tools"] == FROZEN_ALLOWED_TOOLS
    entries = [e.strip() for e in fm["allowed-tools"].split(",")]
    for e in entries:
        assert e not in ("Bash", "Bash(*)", "Bash(python:*)", "Bash(py:*)", "Bash(python3:*)")
        if e.startswith("Bash("):
            inner = e[5:-1]
            assert inner.endswith("--version") or "analyze.py:" in inner, e


def test_body_size_within_limit():
    _, body = _split()
    assert len(body) <= 20000, len(body)


def test_six_stages_in_order():
    _, body = _split()
    heads = re.findall(r"^## Step (\d) of 6: (.+?) \(about (\d) minutes?\)$", body, re.M)
    assert [int(h[0]) for h in heads] == [1, 2, 3, 4, 5, 6]
    assert [h[1] for h in heads] == STAGES
    assert sum(int(h[2]) for h in heads) == 10


def test_stage_exit_lines_documented():
    _, body = _split()
    assert "`Step N of 6 done: <Name>.`" in body
    for n, name in enumerate(STAGES, start=1):
        assert "Step %d of 6 done: %s." % (n, name) in body
    assert "stage=N name=<name> status=passed check=<what was checked> time=<time>" in body
    for n, slug in enumerate(["interview", "sample", "analysis", "generate", "blind-ab", "install"], 1):
        assert "stage=%d name=%s status=passed check=" % (n, slug) in body


def test_permission_sentences_exact():
    _, body = _split()
    flat = _flat(body)
    assert PERMISSION_CLAUDE_CODE in flat
    assert PERMISSION_CLAUDE_AI in flat
    # Shown before the first file is saved.
    assert flat.index(PERMISSION_CLAUDE_CODE) < flat.index("Write `moreme-output/.gitignore`")


def test_fixed_lines_present():
    flat = _flat(_split()[1])
    for line in FIXED_LINES:
        assert line in flat, line


def test_commands_present():
    flat = _flat(_split()[1])
    for cmd in COMMANDS:
        assert cmd in flat, cmd


def test_python_discovery_order_and_store_stub():
    _, body = _split()
    i_py = body.index("`python --version`")
    i_launcher = body.index("`py -3 --version`")
    i_py3 = body.index("`python3 --version`")
    assert i_py < i_launcher < i_py3
    assert "only if both of the others failed" in body
    assert "Microsoft Store" in body
    assert "Python 3.8" in body
    assert "analyze.py --version" in body


def test_ab_mapping_never_read():
    _, body = _split()
    assert "Never open, read, or print `ab-mapping.json`" in body


def test_without_draft_subagent_prompt_rules():
    _, body = _split()
    assert "subagent" in body
    assert "Nothing else: no interview answers, no samples, no voice notes." in body


def test_not_blind_and_no_python_paths():
    _, body = _split()
    assert "not fully blind" in body
    assert "estimated by Claude, not measured" in body
    assert "status=degraded reason=no_python" in body


def test_failure_paths_covered():
    _, body = _split()
    for phrase in ("If analyze.py exits 2", "If the user wants to stop", "--replace",
                   "project_is_home", "below_floor", "At most 3 runs in total"):
        assert phrase in body, phrase


def test_harness_details_not_in_user_skill():
    # Review note N-2: agent-run guard details stay out of the user-facing SKILL.md.
    _, body = _split()
    assert "MOREME_TEST_GUARD" not in body
    assert "headless" not in body.lower()


def test_no_forbidden_tokens_in_skill_or_reference():
    for f in [SKILL] + sorted(REFERENCE.glob("*.md")):
        low = f.read_text(encoding="utf-8").lower()
        for tok in FORBIDDEN_TOKENS:
            assert tok not in low, "%s in %s" % (tok, f.name)


def test_referenced_files_exist():
    _, body = _split()
    names = set(re.findall(r"`(?:reference/)?([a-z-]+\.md)`", body))
    names = {n for n in names if n not in ("interview.md", "voice-notes.md", "ab-task.md",
                                           "draft-with.md", "draft-without.md", "run-log.md")}
    assert names, "no reference files named"
    for n in names:
        assert (REFERENCE / n).is_file(), n
    for f in REFERENCE.glob("*.md"):
        assert f.name in body, "reference file not linked from SKILL.md: " + f.name


def test_no_chatgpt_or_gemini_files():
    # AMEND-001: Claude-only v1.0.0.
    assert not (REPO / "chat").exists()
    for f in (REPO / "moreme").rglob("*"):
        low = f.name.lower()
        assert "chatgpt" not in low and "gemini" not in low and "voice-card" not in low, f
        if f.is_file():
            text = f.read_text(encoding="utf-8", errors="replace").lower()
            assert "chatgpt" not in text and "gemini" not in text, f
