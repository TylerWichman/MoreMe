"""Unit tests for tools/check_prose.py (T-004)."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CHECKER = REPO / "tools" / "check_prose.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_prose", str(CHECKER))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cp = _load()
EM = "—"


def rules(text, **kw):
    return [v.rule for v in cp.check_text(text, "t.md", **kw)]


def test_clean_text_has_no_violations():
    assert rules("Paste three things you wrote. This takes about 2 minutes.") == []


def test_em_dash_found():
    assert rules("One thing" + EM + "another.") == ["em_dash"]


def test_en_dash_and_hyphen_are_allowed():
    assert rules("Pages 3–5 and a well-known tool.") == []


@pytest.mark.parametrize("phrase", list(cp.BANNED_PHRASES))
def test_every_banned_phrase_is_caught(phrase):
    assert "banned_word" in rules("We " + phrase + " here.")


def test_banned_is_case_insensitive():
    assert rules("LEVERAGE this.") == ["banned_word"]


def test_banned_uses_word_boundaries():
    # "robustness" and "magician" are not the banned words themselves.
    assert rules("Robustness and a magician.") == []


def test_curly_apostrophe_phrase_is_caught():
    assert "banned_word" in rules("In today’s world.")


def test_phrase_split_across_lines_is_caught():
    assert "banned_word" in rules("Let us dive\ninto the details.")


def test_exclamation_mark_found():
    assert rules("This is great!") == ["exclamation"]


def test_exclamation_in_code_and_images_ignored():
    assert rules("Use `a != b` here.\n![alt text](demo.gif)") == []


def test_verbatim_samples_span_skips_style_rules():
    text = ("<!-- verbatim-samples:start -->\n"
            "I leverage dashes" + EM + "a lot!\n"
            "<!-- verbatim-samples:end -->\n")
    assert rules(text) == []


def test_verbatim_output_span_skips_style_rules():
    text = ("<!-- verbatim-output:start -->\n"
            "A seamless draft" + EM + "wow!\n"
            "<!-- verbatim-output:end -->\n")
    assert rules(text) == []


def test_text_after_span_end_is_checked_again():
    text = ("<!-- verbatim-samples:start -->\nok\n<!-- verbatim-samples:end -->\n"
            "Now a robust claim.\n")
    assert rules(text) == ["banned_word"]


def test_avoid_words_span_skips_banned_only():
    text = ("<!-- avoid-words:start -->\n- leverage\n- magic" + EM + "x\n<!-- avoid-words:end -->\n")
    assert rules(text) == ["em_dash"]


@pytest.mark.parametrize("token", list(cp.FORBIDDEN_TOKENS))
def test_forbidden_tokens_never_skipped(token):
    text = "<!-- verbatim-samples:start -->\n" + token + "\n<!-- verbatim-samples:end -->\n"
    assert rules(text) == ["forbidden_token"]
    assert rules(token, whole_file_exempt=True) == ["forbidden_token"]


def test_whole_file_exempt_skips_style_rules():
    assert rules("A seamless" + EM + "draft!", whole_file_exempt=True) == []


def test_function_word_table_found():
    words = ["the", "of", "and", "to", "a", "in", "that", "it", "is", "was"]
    table = "\n".join("%s %d.5" % (w, i) for i, w in enumerate(words))
    assert rules(table) == ["function_word_table"]


def test_short_word_number_runs_are_fine():
    table = "\n".join("%s %d" % (w, i) for i, w in enumerate(["the", "of", "and"]))
    assert rules(table) == []


def test_exempt_globs(tmp_path):
    f = tmp_path / "ex.txt"
    f.write_text("# comment\ndocs/transcript-e2e.md  # reason\neval/results/drafts/*\n", encoding="utf-8")
    pats = cp.load_exempt(f)
    assert pats == ["docs/transcript-e2e.md", "eval/results/drafts/*"]
    assert cp.is_exempt("docs/transcript-e2e.md", pats)
    assert cp.is_exempt("eval/results/drafts/p1/with-01.md", pats)
    assert not cp.is_exempt("moreme/SKILL.md", pats)


def test_release_skill_files_are_not_exempt():
    pats = cp.load_exempt()
    for rel in ("README.md", "moreme/SKILL.md", "moreme/reference/install.md",
                "moreme/templates/my-voice/SKILL.md.tmpl", "docs/example-run/my-voice/SKILL.md"):
        assert not cp.is_exempt(rel, pats), rel


def _run(*args, cwd=REPO):
    return subprocess.run([sys.executable, str(CHECKER)] + list(args), cwd=str(cwd),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_cli_exit_codes(tmp_path):
    good = tmp_path / "good.md"
    good.write_text("Plain words.\n", encoding="utf-8")
    bad = tmp_path / "bad.md"
    bad.write_text("A robust tool" + EM + "really.\n", encoding="utf-8")
    assert _run(str(good)).returncode == 0
    r = _run(str(bad))
    assert r.returncode == 1
    out = r.stdout.decode("utf-8")
    assert "banned_word" in out and "em_dash" in out and "bad.md:1:" in out
    assert _run(str(tmp_path / "missing.md")).returncode == 2


def test_cli_rejects_non_utf8(tmp_path):
    f = tmp_path / "latin.md"
    f.write_bytes(b"caf\xe9 \xff\xfe\n")
    assert _run(str(f)).returncode == 2
