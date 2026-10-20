"""Exact-match fixtures: the FROZEN 1 worked example, the hand-counted golden file, and a lowercase writer."""

import json

from conftest import FIXTURES

WORKED_EXPECTED = {
    "sentence_length_mean": 4.2,
    "sentence_length_sd": 2.5612,
    "sentence_length_p10": 1,
    "sentence_length_p50": 4,
    "sentence_length_p90": 8,
    "word_length_mean": 3.1905,
    "paragraph_length_mean": 7.0,
    "contraction_per_1k": 95.2381,
    "first_person_singular_per_1k": 47.619,
    "first_person_plural_per_1k": 47.619,
    "second_person_per_1k": 47.619,
    "question_per_1k": 47.619,
    "exclamation_per_1k": 47.619,
    "ellipsis_per_1k": 47.619,
    "emoji_per_1k": 47.619,
    "comma_per_1k": 0.0,
    "semicolon_per_1k": 0.0,
    "colon_per_1k": 0.0,
    "parenthesis_per_1k": 0.0,
    "em_dash_per_1k": 0.0,
    "en_dash_per_1k": 0.0,
    "spaced_hyphen_per_1k": 0.0,
    "all_caps_word_per_1k": 0.0,
    "question_sentence_share": 0.2,
    "exclamation_sentence_share": 0.2,
    "lowercase_sentence_start_share": 0.8,
    "sentence_opener_variety": 1.0,
    "type_token_ratio_mattr100": 0.9524,
}


def test_worked_example_exact(cli):
    text = (FIXTURES / "worked_example.txt").read_bytes().decode("utf-8")
    assert text.rstrip("\r\n").endswith("\U0001F642")
    res = cli("profile", FIXTURES / "worked_example.txt")
    assert res.code == 0
    data = res.json
    assert data["word_count"] == 21
    assert data["sentence_count"] == 5
    assert data["paragraph_count"] == 3
    assert data["exposed"] == WORKED_EXPECTED  # all 28 keys, exact
    assert [w["code"] for w in data["warnings"]] == ["very_low_word_count"]
    assert data["docs"] == [{"name": "worked_example.txt", "word_count": 21, "encoding_used": "utf-8"}]


def test_worked_example_sentences(analyze):
    text = (FIXTURES / "worked_example.txt").read_bytes().decode("utf-8").replace("\r\n", "\n")
    lengths = []
    for para in text.strip().split("\n\n"):
        segments, _ = analyze.split_sentences(para, final=True)
        lengths += [len(analyze.find_words(s)) for s, _ in segments if analyze.find_words(s)]
    assert lengths == [1, 6, 4, 8, 2]


def test_golden_exact(cli):
    expected = json.loads((FIXTURES / "golden_expected.json").read_text(encoding="utf-8"))
    res = cli("profile", FIXTURES / "golden.txt")
    assert res.code == 0
    data = res.json
    assert data["word_count"] == expected["word_count"]
    assert data["sentence_count"] == expected["sentence_count"]
    assert data["paragraph_count"] == expected["paragraph_count"]
    assert data["exposed"] == expected["exposed"]
    assert [w["code"] for w in data["warnings"]] == expected["warnings"]


def test_lowercase_writer_splits_sentences(cli, analyze):
    text = (FIXTURES / "lowercase.txt").read_bytes().decode("utf-8").replace("\r\n", "\n")
    for para in text.strip().split("\n\n"):
        segments, _ = analyze.split_sentences(para, final=True)
        assert sum(1 for s, _ in segments if analyze.find_words(s)) > 1
    res = cli("profile", FIXTURES / "lowercase.txt")
    data = res.json
    assert data["sentence_count"] == 7
    assert data["paragraph_count"] == 2
    assert data["exposed"]["lowercase_sentence_start_share"] == 1.0


def test_crlf_and_cr_line_endings_match_lf(cli, write_bytes):
    raw = (FIXTURES / "golden.txt").read_bytes().replace(b"\r\n", b"\n")
    lf = cli("profile", write_bytes("lf.txt", raw)).json
    crlf = cli("profile", write_bytes("crlf.txt", raw.replace(b"\n", b"\r\n"))).json
    cr = cli("profile", write_bytes("cr.txt", raw.replace(b"\n", b"\r"))).json
    assert lf["exposed"] == crlf["exposed"] == cr["exposed"]
    assert lf["paragraph_count"] == crlf["paragraph_count"] == cr["paragraph_count"] == 3


def test_sentence_rules(analyze):
    def count(text):
        segs, _ = analyze.split_sentences(text, final=True)
        return [s.strip() for s, _ in segs if analyze.find_words(s)]

    assert count("J. R. Smith came. He left.") == ["J. R. Smith came.", "He left."]
    assert count("I was there. I left.") == ["I was there.", "I left."]
    assert count("See e.g. the list. Then stop.") == ["See e.g. the list.", "Then stop."]
    assert count("Mrs. Day and Prof. Kim met vs. the rest etc. later.") == [
        "Mrs. Day and Prof. Kim met vs. the rest etc. later."]
    assert count("Go to example.com now. It costs 3.50 today.") == [
        "Go to example.com now.", "It costs 3.50 today."]
    assert count("wait... really?! yes") == ["wait... really?!", "yes"]
    assert count("He said \"stop.\" Then he went (finally.) Done") == [
        "He said \"stop.\"", "Then he went (finally.)", "Done"]
    assert count("Well… maybe. ok") == ["Well… maybe.", "ok"]
    assert count("!!! ... ?") == []


def test_question_and_exclamation_share(cli, write_bytes):
    path = write_bytes("q.txt", "Really?! Yes. Why? No!\n".encode("utf-8"))
    e = cli("profile", path).json["exposed"]
    assert e["question_sentence_share"] == 0.5
    assert e["exclamation_sentence_share"] == 0.5


def test_word_and_pronoun_rules(cli, write_bytes):
    path = write_bytes("w.txt", "I’m sure we’re fine and you’ll see. NASA OK A I. rock'n'roll 42 été\n".encode("utf-8"))
    data = cli("profile", path).json
    e = data["exposed"]
    # words: I'm sure we're fine and you'll see NASA OK A I rock'n'roll été = 13
    assert data["word_count"] == 13
    per = 1000.0 / 13
    assert e["contraction_per_1k"] == round(3 * per, 4)
    assert e["first_person_singular_per_1k"] == round(2 * per, 4)  # I'm, I
    assert e["first_person_plural_per_1k"] == round(per, 4)
    assert e["second_person_per_1k"] == round(per, 4)
    assert e["all_caps_word_per_1k"] == round(2 * per, 4)  # NASA, OK


def test_emoji_rules(cli, write_bytes):
    # thumbs up + skin tone counts 1, flag pair counts 1, ZWJ family counts 3, FE0F not counted, star 1
    text = "nice \U0001F44D\U0001F3FD flag \U0001F1FA\U0001F1F8 family \U0001F468‍\U0001F469‍\U0001F467 sun ☀️\n"
    e = cli("profile", write_bytes("e.txt", text.encode("utf-8"))).json["exposed"]
    assert e["emoji_per_1k"] == round(6 / 4 * 1000, 4)


def test_punctuation_rules(cli, write_bytes):
    text = "a - b -- c --- d e-f; g: h (i) j—k l–m n.. o… p...\n"
    data = cli("profile", write_bytes("p.txt", text.encode("utf-8"))).json
    e = data["exposed"]
    wc = data["word_count"]
    assert wc == 16  # e-f is two words
    per = 1000.0 / wc
    assert e["spaced_hyphen_per_1k"] == round(2 * per, 4)  # " - " and "--"
    assert e["ellipsis_per_1k"] == round(3 * per, 4)
    assert e["semicolon_per_1k"] == round(per, 4)
    assert e["colon_per_1k"] == round(per, 4)
    assert e["parenthesis_per_1k"] == round(per, 4)
    assert e["em_dash_per_1k"] == round(per, 4)
    assert e["en_dash_per_1k"] == round(per, 4)


def test_percentile_nearest_rank(analyze):
    assert analyze.percentile([5, 1, 3, 2, 4], 10) == 1
    assert analyze.percentile([5, 1, 3, 2, 4], 50) == 3
    assert analyze.percentile([5, 1, 3, 2, 4], 90) == 5
    assert analyze.percentile([], 50) is None
