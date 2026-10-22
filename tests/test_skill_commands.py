"""validate-skill, build-skill, package, and install (all installs use a fake home)."""

import json
import os
import shutil
import zipfile

import pytest

from conftest import FIXTURES, REPO, TEMPLATE

BUILD = FIXTURES / "build"
GOOD_FRONT = (
    "---\nname: demo-skill\ndescription: Use this when testing. It does nothing else.\n---\n\n# Demo\n\nPlain body text.\n"
)


def make_skill(tmp_path, text=GOOD_FRONT, name="demo-skill"):
    folder = tmp_path / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(text, encoding="utf-8")
    return folder


def error_codes(data):
    return [e["code"] for e in data["errors"]]


# -- validate-skill -----------------------------------------------------------


def test_validate_ok(cli, tmp_path):
    res = cli("validate-skill", make_skill(tmp_path))
    assert res.code == 0
    assert res.json == {"ok": True, "errors": [], "warnings": []}


def test_validate_missing_dir_exit_2(cli, tmp_path):
    assert cli("validate-skill", tmp_path / "nope").code == 2


def test_validate_missing_skill_md(cli, tmp_path):
    (tmp_path / "empty").mkdir()
    res = cli("validate-skill", tmp_path / "empty")
    assert res.code == 0 and error_codes(res.json) == ["missing_skill_md"]


@pytest.mark.parametrize(
    "text,code",
    [
        ("# no frontmatter\n", "bad_frontmatter"),
        ("---\nname: x\n", "bad_frontmatter"),
        ("---\nname: Bad_Name\ndescription: ok\n---\n", "name_invalid"),
        ("---\nname: claude-helper\ndescription: ok\n---\n", "name_invalid"),
        ("---\nname: my-anthropic\ndescription: ok\n---\n", "name_invalid"),
        ("---\nname: " + "a" * 65 + "\ndescription: ok\n---\n", "name_invalid"),
        ("---\nname: ok\n---\nbody\n", "description_missing"),
        ("---\nname: ok\ndescription: " + "d" * 1025 + "\n---\n", "description_too_long"),
        ("---\nname: ok\ndescription: d\n---\n" + "x" * 20001, "body_too_long"),
        ("---\nname: ok\ndescription: d\n---\nThis is a robust plan.\n", "banned_word"),
        ("---\nname: ok\ndescription: d\n---\nIt’s worth noting this.\n", "banned_word"),
        ("---\nname: ok\ndescription: d\n---\nOne — two.\n", "em_dash"),
        ("---\nname: ok\ndescription: d\n---\nsee char3_freq here\n", "forbidden_token"),
        ("---\nname: ok\ndescription: d\nallowed-tools: Bash\n---\n", "allowed_tools_too_broad"),
        ("---\nname: ok\ndescription: d\nallowed-tools: Bash(python:*)\n---\n", "allowed_tools_too_broad"),
        ("---\nname: ok\ndescription: d\nallowed-tools: Bash(py:*), Read\n---\n", "allowed_tools_too_broad"),
        ("---\nname: ok\ndescription: d\nallowed-tools: Bash(python *)\n---\n", "allowed_tools_too_broad"),
        ("---\nname: ok\ndescription: d\nallowed-tools: Bash(python other.py:*)\n---\n", "allowed_tools_too_broad"),
        ("---\nname: ok\ndescription: d\nallowed-tools:\n  - Bash(python -c:*)\n---\n", "allowed_tools_too_broad"),
        ("---\nname: ok\ndescription: d\nallowed-tools: PowerShell\n---\n", "allowed_tools_too_broad"),
        ("---\nname: ok\ndescription: d\nallowed-tools: PowerShell(python:*)\n---\n", "allowed_tools_too_broad"),
    ],
)
def test_validate_error_codes(cli, tmp_path, text, code):
    res = cli("validate-skill", make_skill(tmp_path, text))
    assert res.code == 0
    data = res.json
    assert data["ok"] is False
    assert code in error_codes(data)


def test_validate_function_word_table_is_forbidden(cli, tmp_path):
    rows = "".join("| {0} | {1}.5 |\n".format(w, i) for i, w in enumerate(["the", "of", "and", "to", "in", "is", "it", "that", "was", "for"]))
    res = cli("validate-skill", make_skill(tmp_path, GOOD_FRONT + rows))
    assert "forbidden_token" in error_codes(res.json)


def test_validate_marker_exemptions(cli, tmp_path):
    text = GOOD_FRONT + (
        "<!-- verbatim-samples:start -->\nA robust plan — really.\n<!-- verbatim-samples:end -->\n"
        "<!-- avoid-words:start -->\n- leverage\n- synergy\n<!-- avoid-words:end -->\n"
    )
    assert cli("validate-skill", make_skill(tmp_path, text)).json["ok"] is True
    # avoid-words markers exempt banned words only, not em dashes or forbidden tokens
    for inner in ("- one — two", "- delta_fw"):
        bad = GOOD_FRONT + "<!-- avoid-words:start -->\n" + inner + "\n<!-- avoid-words:end -->\n"
        assert cli("validate-skill", make_skill(tmp_path, bad)).json["ok"] is False
    # forbidden tokens are never exempt, even inside verbatim markers
    bad = GOOD_FRONT + "<!-- verbatim-samples:start -->\nscoring_only\n<!-- verbatim-samples:end -->\n"
    assert "forbidden_token" in error_codes(cli("validate-skill", make_skill(tmp_path, bad)).json)


def test_validate_narrow_allowed_tools_ok(cli, tmp_path):
    tools = (
        "Bash(python --version), Bash(py -3 --version), Bash(python3 --version), "
        "Bash(python .claude/skills/moreme/analyze.py:*), Bash(py -3 .claude/skills/moreme/analyze.py:*), "
        "Bash(python3 ~/.claude/skills/moreme/analyze.py:*), Write(moreme-output/**), Edit(moreme-output/**)"
    )
    text = "---\nname: moreme\ndescription: d\nallowed-tools: " + tools + "\n---\nbody\n"
    assert cli("validate-skill", make_skill(tmp_path, text, "moreme")).json == {"ok": True, "errors": [], "warnings": []}


def test_validate_crlf_skill(cli, tmp_path):
    folder = tmp_path / "crlf"
    folder.mkdir()
    (folder / "SKILL.md").write_bytes(GOOD_FRONT.replace("\n", "\r\n").encode("utf-8"))
    assert cli("validate-skill", folder).json["ok"] is True


def test_real_moreme_skill_validates(cli):
    if not (REPO / "moreme" / "SKILL.md").is_file():
        pytest.skip("moreme/SKILL.md not present")
    res = cli("validate-skill", REPO / "moreme")
    assert res.json["ok"] is True, res.json["errors"]


# -- build-skill ----------------------------------------------------------------


def copy_build(tmp_path):
    dst = tmp_path / "moreme-output"
    shutil.copytree(str(BUILD), str(dst))
    return dst


def build(cli, out, notes=None, *extra):
    return cli("build-skill", out / "profile.json", notes or (out / "voice-notes.md"), "--samples", out / "samples",
               "--out", out, "--date", "2026-10-20", *extra)


def test_build_skill_ok_with_real_template(cli, tmp_path, analyze):
    assert TEMPLATE.is_file(), "T-004 template missing"
    out = copy_build(tmp_path)
    res = build(cli, out)
    assert res.code == 0
    data = res.json
    assert data["ok"] is True, data["errors"]
    assert list(data) == ["ok", "skill_dir", "zip", "errors", "warnings"]
    skill = out / "my-voice" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert "{{" not in text
    assert cli("validate-skill", out / "my-voice").json["ok"] is True
    # excerpts verbatim inside the markers
    inner = text.split("<!-- verbatim-samples:start -->")[1].split("<!-- verbatim-samples:end -->")[0]
    assert inner.count("From sample-") == 3
    # display rule values equal the rule applied to profile.json
    profile = json.loads((out / "profile.json").read_text("utf-8"))["exposed"]
    assert "| A typical sentence | {0} words |".format(analyze.display_value("sentence_length_p50", profile["sentence_length_p50"])) in text
    assert "| Commas | {0} per 1,000 words |".format(analyze.display_value("comma_per_1k", profile["comma_per_1k"])) in text
    assert "| Sentences that are questions | {0} |".format(
        analyze.display_value("question_sentence_share", profile["question_sentence_share"])) in text
    # pet peeve kept, default list minus words found in the samples ("magic" is in sample-02)
    avoid = text.split("<!-- avoid-words:start -->")[1].split("<!-- avoid-words:end -->")[0]
    lines = [l for l in avoid.strip().split("\n")]
    assert "- leverage" in lines and "- synergy" in lines and "- circle back" in lines
    assert "- magic" not in lines and "- magical" in lines
    assert lines.count("- leverage") == 1
    # long dashes appear in the samples, so the dash line says they are fine
    assert "Long dashes are fine. My samples use about" in text
    assert "Made with MoreMe v1.0.0 on 2026-10-20." in text
    for token in ("scoring_only", "function_word_freq", "char3_freq", "delta_fw", "char3_cosine", "reference_stats"):
        assert token not in text
    # zip: single top-level my-voice/ folder
    with zipfile.ZipFile(str(out / "my-voice.zip")) as zf:
        names = zf.namelist()
    assert names == ["my-voice/SKILL.md"]


def test_build_skill_replaces_earlier_skill(cli, tmp_path):
    out = copy_build(tmp_path)
    (out / "my-voice").mkdir()
    (out / "my-voice" / "stale.txt").write_text("old", encoding="utf-8")
    assert build(cli, out).json["ok"] is True
    assert sorted(p.name for p in (out / "my-voice").iterdir()) == ["SKILL.md"]
    assert not [p for p in out.iterdir() if p.name.startswith(".my-voice")]


def test_build_skill_changed_excerpt_writes_nothing(cli, tmp_path):
    out = copy_build(tmp_path)
    notes = out / "voice-notes.md"
    notes.write_text(notes.read_text("utf-8").replace("nothing fancy", "nothing special"), encoding="utf-8")
    res = build(cli, out)
    assert res.code == 0
    data = res.json
    assert data["ok"] is False and data["zip"] is None
    assert "excerpt_not_verbatim" in error_codes(data)
    assert not (out / "my-voice").exists() and not (out / "my-voice.zip").exists()


def test_build_skill_crlf_notes_and_samples(cli, tmp_path):
    out = copy_build(tmp_path)
    for path in [out / "voice-notes.md"] + list((out / "samples").glob("*.txt")):
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert build(cli, out).json["ok"] is True


def edit_notes(out, old, new):
    notes = out / "voice-notes.md"
    text = notes.read_text("utf-8")
    assert old in text
    notes.write_text(text.replace(old, new), encoding="utf-8")


@pytest.mark.parametrize(
    "old,new,code",
    [
        ("## Don't\n", "## Dont typo\n", "notes_section_missing"),
        ("- Sign off with a single word such as Cheers or Thanks.\n", "", "notes_count_out_of_range"),
        ("I ask a question when I want a reply.", "", "notes_count_out_of_range"),
        ("Post: Keep it under 60 words. Skip the greeting.\n", "", "notes_count_out_of_range"),
        (" What surprised me was how much I missed the quiet. No phone, no podcasts, just the sound of my own "
         "breathing and the odd dog barking from a yard. I don't time myself anymore.", "", "excerpt_length"),
        ("[sample-03.txt]", "[sample-09.txt]", "excerpt_not_verbatim"),
        ("[sample-03.txt]", "[../sample-03.txt]", "excerpt_not_verbatim"),
        ("- Use contractions like I'm, we're, and don't.", "- Use contractions to leverage warmth.", "banned_word"),
        ("Skip the greeting.", "Skip the greeting — always.", "em_dash"),
    ],
)
def test_build_skill_note_errors(cli, tmp_path, old, new, code):
    out = copy_build(tmp_path)
    edit_notes(out, old, new)
    data = build(cli, out).json
    assert data["ok"] is False
    assert code in error_codes(data), data["errors"]
    assert not (out / "my-voice").exists()


def test_build_skill_too_few_excerpts(cli, tmp_path):
    out = copy_build(tmp_path)
    text = (out / "voice-notes.md").read_text("utf-8")
    start = text.index("[sample-03.txt]")
    end = text.index("## Adjust by channel")
    (out / "voice-notes.md").write_text(text[:start] + "\n" + text[end:], encoding="utf-8")
    assert "notes_count_out_of_range" in error_codes(build(cli, out).json)


def test_build_skill_unknown_placeholder(cli, tmp_path):
    out = copy_build(tmp_path)
    tmpl = tmp_path / "bad.tmpl"
    tmpl.write_text(TEMPLATE.read_text("utf-8") + "\n{{exposed.comma_per_1k}} {{scores.secret}} {{exposed.semicolon_per_1k}}\n", encoding="utf-8")
    data = build(cli, out, None, "--template", tmpl).json
    assert data["ok"] is False
    msgs = [e["message"] for e in data["errors"] if e["code"] == "unknown_placeholder"]
    assert len(msgs) == 2  # scores.secret and a non-display exposed key
    assert not (out / "my-voice").exists()


def test_build_skill_minimal_fixture_template_and_no_dash(cli, tmp_path):
    out = copy_build(tmp_path)
    profile = json.loads((out / "profile.json").read_text("utf-8"))
    profile["exposed"]["em_dash_per_1k"] = 0.0
    (out / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    data = build(cli, out, None, "--template", FIXTURES / "minimal-template.tmpl").json
    assert data["ok"] is True, data["errors"]
    text = (out / "my-voice" / "SKILL.md").read_text("utf-8")
    assert "- Do not use long dashes. Use commas, periods, colons, or parentheses instead." in text


def test_build_skill_missing_inputs_exit_2(cli, tmp_path):
    out = copy_build(tmp_path)
    assert cli("build-skill", out / "nope.json", out / "voice-notes.md", "--samples", out / "samples", "--out", out).code == 2
    assert cli("build-skill", out / "profile.json", out / "nope.md", "--samples", out / "samples", "--out", out).code == 2
    assert cli("build-skill", out / "profile.json", out / "voice-notes.md", "--samples", out / "nope", "--out", out).code == 2
    assert build(cli, out, None, "--template", tmp_path / "none.tmpl").code == 2


# -- package --------------------------------------------------------------------


def test_package_deterministic_and_clean(cli, tmp_path):
    skill = make_skill(tmp_path, name="moreme")
    (skill / "templates" / "my-voice").mkdir(parents=True)
    (skill / "templates" / "my-voice" / "SKILL.md.tmpl").write_text("t", encoding="utf-8")
    (skill / "__pycache__").mkdir()
    (skill / "__pycache__" / "x.pyc").write_bytes(b"x")
    (skill / "analyze.pyc").write_bytes(b"x")
    (skill / ".hidden").write_text("h", encoding="utf-8")
    (skill / ".git").mkdir()
    (skill / ".git" / "config").write_text("c", encoding="utf-8")
    z1, z2 = tmp_path / "a" / "one.zip", tmp_path / "two.zip"
    res = cli("package", skill, "--out", z1)
    assert res.code == 0
    assert res.json == {"ok": True, "out": str(z1), "files": 2, "warnings": []}
    os.utime(str(skill / "SKILL.md"), (1000000000, 1000000000))
    cli("package", skill, "--out", z2)
    assert z1.read_bytes() == z2.read_bytes()
    with zipfile.ZipFile(str(z1)) as zf:
        infos = zf.infolist()
    assert [i.filename for i in infos] == ["moreme/SKILL.md", "moreme/templates/my-voice/SKILL.md.tmpl"]
    for info in infos:
        assert info.date_time == (1980, 1, 1, 0, 0, 0)
        assert info.compress_type == zipfile.ZIP_DEFLATED
        assert (info.external_attr >> 16) & 0o777 == 0o644
    assert {n.split("/")[0] for n in [i.filename for i in infos]} == {"moreme"}


def test_package_requires_skill_md(cli, tmp_path):
    (tmp_path / "x").mkdir()
    assert cli("package", tmp_path / "x", "--out", tmp_path / "x.zip").code == 2


def test_package_real_moreme_folder(cli, tmp_path):
    if not (REPO / "moreme" / "SKILL.md").is_file():
        pytest.skip("moreme/SKILL.md not present")
    z = tmp_path / "moreme.zip"
    assert cli("package", REPO / "moreme", "--out", z).code == 0
    with zipfile.ZipFile(str(z)) as zf:
        names = zf.namelist()
    assert {n.split("/")[0] for n in names} == {"moreme"}
    assert "moreme/SKILL.md" in names and "moreme/analyze.py" in names
    assert not [n for n in names if "__pycache__" in n or n.endswith(".pyc")]


# -- install (fake home only) ------------------------------------------------------


def test_install_project_route(cli, tmp_path, fake_home):
    skill = make_skill(tmp_path, name="my-voice")
    project = tmp_path / "proj"
    project.mkdir()
    res = cli("install", skill, "--project", project)
    assert res.code == 0
    data = res.json
    target = project / ".claude" / "skills" / "my-voice"
    assert data == {"ok": True, "installed": str(target), "route": "project", "warnings": []}
    assert (target / "SKILL.md").is_file()
    assert not (fake_home / ".claude").exists()


def test_install_project_defaults_to_current_folder(cli, tmp_path, fake_home, monkeypatch):
    skill = make_skill(tmp_path, name="my-voice")
    project = tmp_path / "cwdproj"
    project.mkdir()
    monkeypatch.chdir(str(project))
    data = cli("install", skill).json
    assert data["route"] == "project"
    assert (project / ".claude" / "skills" / "my-voice" / "SKILL.md").is_file()


def test_install_personal_route(cli, tmp_path, fake_home):
    skill = make_skill(tmp_path, name="my-voice")
    data = cli("install", skill, "--personal").json
    target = fake_home / ".claude" / "skills" / "my-voice"
    assert data == {"ok": True, "installed": str(target), "route": "personal", "warnings": []}
    assert (target / "SKILL.md").is_file()


def test_install_project_is_home(cli, tmp_path, fake_home, monkeypatch):
    skill = make_skill(tmp_path, name="my-voice")
    monkeypatch.chdir(str(fake_home))
    res = cli("install", skill)
    assert res.code == 0
    assert res.json == {"ok": False, "reason": "project_is_home", "installed": None, "warnings": []}
    assert not (fake_home / ".claude").exists()
    res = cli("install", skill, "--project", fake_home)
    assert res.json["reason"] == "project_is_home"


def test_install_guard_blocks_personal(cli, tmp_path, fake_home, monkeypatch):
    monkeypatch.setenv("MOREME_TEST_GUARD", "1")
    skill = make_skill(tmp_path, name="my-voice")
    res = cli("install", skill, "--personal")
    assert res.code == 2
    assert "MOREME_TEST_GUARD" in res.err
    assert not (fake_home / ".claude").exists()


def test_install_guard_blocks_project_at_home(cli, tmp_path, fake_home, monkeypatch):
    monkeypatch.setenv("MOREME_TEST_GUARD", "1")
    skill = make_skill(tmp_path, name="my-voice")
    res = cli("install", skill, "--project", fake_home)
    assert res.code == 2  # the guard runs before the home-folder case
    assert "MOREME_TEST_GUARD" in res.err
    assert not (fake_home / ".claude").exists()


def test_install_guard_allows_scratch_project(cli, tmp_path, fake_home, monkeypatch):
    monkeypatch.setenv("MOREME_TEST_GUARD", "1")
    skill = make_skill(tmp_path, name="my-voice")
    project = tmp_path / "scratch"
    project.mkdir()
    assert cli("install", skill, "--project", project).json["ok"] is True


def test_install_existing_needs_replace(cli, tmp_path, fake_home):
    skill = make_skill(tmp_path, name="my-voice")
    project = tmp_path / "proj"
    project.mkdir()
    cli("install", skill, "--project", project)
    target = project / ".claude" / "skills" / "my-voice"
    (target / "old.txt").write_text("old", encoding="utf-8")
    res = cli("install", skill, "--project", project)
    assert res.code == 2
    assert "my-voice is already installed at" in res.err
    assert "Ask the user whether to replace it, then run again with --replace." in res.err
    res = cli("install", skill, "--project", project, "--replace")
    assert res.code == 0 and res.json["ok"] is True
    assert sorted(p.name for p in target.iterdir()) == ["SKILL.md"]
    leftovers = [p.name for p in target.parent.iterdir() if p.name.startswith(".")]
    assert leftovers == []


def test_install_both_routes_exit_2(cli, tmp_path, fake_home):
    skill = make_skill(tmp_path, name="my-voice")
    assert cli("install", skill, "--project", tmp_path, "--personal").code == 2


def test_install_invalid_skill_exit_2(cli, tmp_path, fake_home):
    skill = make_skill(tmp_path, "---\nname: Bad Name\ndescription: d\n---\n", name="my-voice")
    project = tmp_path / "proj"
    project.mkdir()
    res = cli("install", skill, "--project", project)
    assert res.code == 2 and "validate-skill" in res.err
    assert not (project / ".claude").exists()


def test_validate_accepts_scoped_powershell_entries(cli, tmp_path):
    text = ("---\nname: ok\ndescription: d\nallowed-tools: PowerShell(python --version), "
            "PowerShell(py -3 .claude/skills/moreme/analyze.py:*)\n---\nbody\n")
    res = cli("validate-skill", make_skill(tmp_path, text))
    assert "allowed_tools_too_broad" not in error_codes(res.json)
