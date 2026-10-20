"""The my-voice template follows FROZEN 3: placeholder whitelist, pinned name and description (T-004)."""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "moreme" / "templates" / "my-voice" / "SKILL.md.tmpl"

# FROZEN 1: the 28 exposed keys.
EXPOSED_KEYS = {
    "sentence_length_mean", "sentence_length_sd", "sentence_length_p10", "sentence_length_p50",
    "sentence_length_p90", "word_length_mean", "paragraph_length_mean", "comma_per_1k",
    "semicolon_per_1k", "colon_per_1k", "exclamation_per_1k", "question_per_1k", "ellipsis_per_1k",
    "parenthesis_per_1k", "em_dash_per_1k", "en_dash_per_1k", "spaced_hyphen_per_1k",
    "contraction_per_1k", "first_person_singular_per_1k", "first_person_plural_per_1k",
    "second_person_per_1k", "question_sentence_share", "exclamation_sentence_share",
    "type_token_ratio_mattr100", "all_caps_word_per_1k", "lowercase_sentence_start_share",
    "emoji_per_1k", "sentence_opener_variety",
}

# FROZEN 3: the 13 display keys and the full placeholder whitelist.
DISPLAY_KEYS = {
    "sentence_length_p50", "sentence_length_p10", "sentence_length_p90", "paragraph_length_mean",
    "comma_per_1k", "exclamation_per_1k", "question_sentence_share", "contraction_per_1k",
    "first_person_singular_per_1k", "second_person_per_1k", "em_dash_per_1k", "emoji_per_1k",
    "lowercase_sentence_start_share",
}
WHITELIST = (
    {"exposed." + k for k in DISPLAY_KEYS}
    | {"meta.word_count", "meta.doc_count", "meta.date", "meta.moreme_version"}
    | {"notes.how_i_sound", "notes.do", "notes.dont", "notes.avoid_words", "notes.examples",
       "notes.channels"}
    | {"rules.dash_line"}
)

PINNED_DESCRIPTION = (
    "Use this skill whenever you draft, rewrite, or edit any text the user will send or post as "
    "their own, including emails, messages, social posts, cover letters, and bios. It holds the "
    "user's writing voice, measured from their own samples, and says how to match it."
)

FORBIDDEN_TOKENS = ("scoring_only", "function_word_freq", "char3_freq", "delta_fw",
                    "char3_cosine", "reference_stats")

PLACEHOLDER_RE = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")


def _text():
    return TEMPLATE.read_text(encoding="utf-8")


def _frontmatter(text):
    assert text.startswith("---\n"), "template must start with frontmatter"
    end = text.index("\n---\n", 4)
    fm = {}
    for line in text[4:end].splitlines():
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip()
    return fm, text[end + 5:]


def test_display_keys_are_exposed_keys():
    assert len(EXPOSED_KEYS) == 28
    assert len(DISPLAY_KEYS) == 13
    assert DISPLAY_KEYS <= EXPOSED_KEYS


def test_placeholders_are_whitelisted():
    found = set(PLACEHOLDER_RE.findall(_text()))
    assert found, "no placeholders found"
    assert found <= WHITELIST, "not whitelisted: %s" % sorted(found - WHITELIST)


def test_every_whitelisted_placeholder_is_used():
    found = set(PLACEHOLDER_RE.findall(_text()))
    assert WHITELIST <= found, "unused: %s" % sorted(WHITELIST - found)


def test_no_stray_braces():
    stripped = PLACEHOLDER_RE.sub("", _text())
    assert "{{" not in stripped and "}}" not in stripped


def test_exposed_placeholders_only_display_keys():
    keys = {p.split(".", 1)[1] for p in PLACEHOLDER_RE.findall(_text()) if p.startswith("exposed.")}
    assert keys == DISPLAY_KEYS
    for key in EXPOSED_KEYS - DISPLAY_KEYS:
        assert key not in _text(), key


def test_name_pinned_and_description_verbatim():
    fm, _ = _frontmatter(_text())
    assert fm["name"] == "my-voice"
    assert fm["description"] == PINNED_DESCRIPTION
    assert len(fm["description"]) <= 1024
    assert set(fm) == {"name", "description"}, "my-voice needs no other frontmatter (no allowed-tools)"


def test_no_forbidden_tokens():
    low = _text().lower()
    for tok in FORBIDDEN_TOKENS:
        assert tok not in low, tok


def test_markers_wrap_avoid_words_and_examples():
    t = _text()
    a0 = t.index("<!-- avoid-words:start -->")
    a1 = t.index("<!-- avoid-words:end -->")
    v0 = t.index("<!-- verbatim-samples:start -->")
    v1 = t.index("<!-- verbatim-samples:end -->")
    assert a0 < t.index("{{notes.avoid_words}}") < a1
    assert v0 < t.index("{{notes.examples}}") < v1
    assert a1 < v0


def test_section_order():
    _, body = _frontmatter(_text())
    headings = [l[3:] for l in body.splitlines() if l.startswith("## ")]
    assert headings == ["How I sound", "Measured profile", "Do", "Don't", "Words I avoid",
                        "Examples from my own writing", "Adjust by channel", "Rules for Claude"]


def test_body_within_skill_limit():
    _, body = _frontmatter(_text())
    assert len(body) < 20000


def test_no_em_dash_outside_placeholders():
    assert "—" not in _text()
