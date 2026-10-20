"""Missing values read naturally in `report` and in the rendered my-voice skill (T-010).

A value that could not be measured shows as "not measured (too little text)" (FROZEN 3) with no
unit after it, and report sentences are rephrased around it.
"""

import json
import re
import shutil

from conftest import FIXTURES

NM = "not measured (too little text)"
BUILD = FIXTURES / "build"


def _profile(cli, tmp_path, write_bytes, data, name="p.json"):
    prof = tmp_path / name
    res = cli("profile", write_bytes(name + ".txt", data), "--out", prof)
    assert res.code == 0
    return prof


def _report(cli, prof):
    res = cli("report", prof)
    assert res.code == 0
    return res.out


def _assert_reads_naturally(text):
    # No unit or connecting word glued onto the not-measured phrase.
    assert not re.search(re.escape(NM) + r" (words?|letters|per|long|of|to)\b", text), text
    assert "about " + NM not in text
    assert "is " + NM + " long" not in text
    assert "None" not in text


def test_report_empty_input_one_line_per_group(cli, tmp_path, write_bytes):
    text = _report(cli, _profile(cli, tmp_path, write_bytes, b""))
    _assert_reads_naturally(text)
    for heading in ("Sentences", "Words and paragraphs", "Punctuation per 1,000 words",
                    "Dashes per 1,000 words", "Contractions and pronouns per 1,000 words",
                    "Kinds of sentences", "Capitals and emoji per 1,000 words"):
        assert "\n{0}: {1}.\n".format(heading, NM) in text, heading
    # Each group says it once, not after every label.
    assert text.count(NM) == 7


def test_report_one_word_rephrases_spread(cli, tmp_path, write_bytes):
    text = _report(cli, _profile(cli, tmp_path, write_bytes, b"Hello"))
    _assert_reads_naturally(text)
    assert "varies by about" not in text
    assert "There is too little text to say how much the length varies." in text
    assert "a typical sentence is 1 word." in text
    assert "Based on 1 word in 1 sample." in text


def test_report_measured_profile_text_unchanged(cli, tmp_path):
    prof = tmp_path / "g.json"
    cli("profile", FIXTURES / "golden.txt", "--out", prof)
    text = _report(cli, prof)
    assert NM not in text
    assert ", and length varies by about " in text
    assert "Word variety is " in text and "(share of different words in each run of 100 words)." in text
    assert "Punctuation per 1,000 words: commas " in text


def test_words_line_partial_values(analyze):
    line = analyze._words_line({"word_length_mean": 4.25, "paragraph_length_mean": None,
                                "type_token_ratio_mattr100": 0.5})
    assert line == ("Words and paragraphs: the average word is 4.3 letters long. Paragraph length is "
                    + NM + ". Word variety is 50% (share of different words in each run of 100 words).")


def test_fit_display_text_drops_units_for_missing(analyze):
    tpl = ("| A | {{exposed.sentence_length_p50}} words |\n"
           "| B | {{exposed.sentence_length_p10}} to {{exposed.sentence_length_p90}} words |\n"
           "| C | {{exposed.comma_per_1k}} per 1,000 words |\n"
           "| D | {{exposed.question_sentence_share}} |\n")
    missing = {"exposed.sentence_length_p50": NM, "exposed.sentence_length_p10": NM,
               "exposed.sentence_length_p90": NM, "exposed.comma_per_1k": NM,
               "exposed.question_sentence_share": NM}
    out, errors = analyze.render_template(tpl, missing)
    assert errors == []
    assert out == "| A | {0} |\n| B | {0} |\n| C | {0} |\n| D | {0} |\n".format(NM)

    present = {"exposed.sentence_length_p50": "12", "exposed.sentence_length_p10": "4",
               "exposed.sentence_length_p90": "22", "exposed.comma_per_1k": "47.6",
               "exposed.question_sentence_share": "20%"}
    out, errors = analyze.render_template(tpl, present)
    assert out == "| A | 12 words |\n| B | 4 to 22 words |\n| C | 47.6 per 1,000 words |\n| D | 20% |\n"


def test_fit_display_text_singular_counts(analyze):
    tpl = "from {{meta.word_count}} words in {{meta.doc_count}} samples on x."
    assert analyze.render_template(tpl, {"meta.word_count": "1", "meta.doc_count": "1"})[0] == \
        "from 1 word in 1 sample on x."
    assert analyze.render_template(tpl, {"meta.word_count": "1,200", "meta.doc_count": "3"})[0] == \
        "from 1,200 words in 3 samples on x."


def test_fit_display_text_keeps_unknown_placeholder_error(analyze):
    out, errors = analyze.render_template("{{exposed.nope}} words", {})
    assert [e["code"] for e in errors] == ["unknown_placeholder"]


def test_build_skill_with_unmeasured_profile(cli, tmp_path, write_bytes):
    out = tmp_path / "moreme-output"
    shutil.copytree(str(BUILD), str(out))
    empty = _profile(cli, tmp_path, write_bytes, b"", name="empty.json")
    shutil.copyfile(str(empty), str(out / "profile.json"))
    res = cli("build-skill", out / "profile.json", out / "voice-notes.md", "--samples", out / "samples",
              "--out", out, "--date", "2026-10-20")
    assert res.json["ok"] is True, res.json["errors"]
    text = (out / "my-voice" / "SKILL.md").read_text(encoding="utf-8")
    _assert_reads_naturally(text)
    assert "| A typical sentence | {0} |".format(NM) in text
    assert "| Short and long sentences | {0} |".format(NM) in text
    assert "| Commas | {0} |".format(NM) in text
    assert "| Sentences that are questions | {0} |".format(NM) in text
    assert "from 0 words in 1 sample on 2026-10-20." in text
    assert cli("validate-skill", out / "my-voice").json["ok"] is True


def test_build_skill_measured_profile_keeps_units(cli, tmp_path, analyze):
    out = tmp_path / "moreme-output"
    shutil.copytree(str(BUILD), str(out))
    res = cli("build-skill", out / "profile.json", out / "voice-notes.md", "--samples", out / "samples",
              "--out", out, "--date", "2026-10-20")
    assert res.json["ok"] is True
    text = (out / "my-voice" / "SKILL.md").read_text(encoding="utf-8")
    exposed = json.loads((out / "profile.json").read_text("utf-8"))["exposed"]
    d = analyze.display_value
    assert "| Short and long sentences | {0} to {1} words |".format(
        d("sentence_length_p10", exposed["sentence_length_p10"]),
        d("sentence_length_p90", exposed["sentence_length_p90"])) in text
    assert "| Emoji | {0} per 1,000 words |".format(d("emoji_per_1k", exposed["emoji_per_1k"])) in text
    assert NM not in text
