"""Decoding chain (FROZEN 1 order) and edge cases: empty, whitespace, binary, huge, one sentence, no punctuation."""

import codecs

import pytest

from conftest import ANALYZE, FIXTURES

TEXT = "Café owners said “no” to the plan. We’ll try again next week, maybe.\n"
TEXT_WORDS = 13  # Café owners said no to the plan We'll try again next week maybe


def codes(data):
    return [w["code"] for w in data["warnings"]]


@pytest.mark.parametrize(
    "name,data,encoding,fallback",
    [
        ("utf8.txt", TEXT.encode("utf-8"), "utf-8", False),
        ("utf8bom.txt", codecs.BOM_UTF8 + TEXT.encode("utf-8"), "utf-8-sig", False),
        ("cp1252.txt", TEXT.encode("cp1252"), "cp1252", True),
        ("utf16le.txt", codecs.BOM_UTF16_LE + TEXT.encode("utf-16-le"), "utf-16-le", True),
        ("utf16be.txt", codecs.BOM_UTF16_BE + TEXT.encode("utf-16-be"), "utf-16-be", True),
    ],
)
def test_encoding_chain(cli, write_bytes, name, data, encoding, fallback):
    res = cli("profile", write_bytes(name, data))
    assert res.code == 0, res.err
    out = res.json
    assert out["word_count"] == TEXT_WORDS
    assert out["docs"][0]["encoding_used"] == encoding
    assert ("encoding_fallback" in codes(out)) is fallback
    assert "replacement_chars" not in codes(out)
    assert out["exposed"]["contraction_per_1k"] == round(1000.0 / TEXT_WORDS, 4)


def test_latin1_bytes(cli, write_bytes):
    # 0x81 is undefined in cp1252, so cp1252 strict fails and latin-1 is used.
    data = "naïve résumé text".encode("latin-1") + b" \x81 here.\n"
    out = cli("profile", write_bytes("latin1.txt", data)).json
    assert out["docs"][0]["encoding_used"] == "latin-1"
    assert "encoding_fallback" in codes(out)
    assert out["word_count"] == 4


def test_utf16_bom_bad_surrogate_uses_replacement(cli, write_bytes):
    data = codecs.BOM_UTF16_LE + "Good words here.".encode("utf-16-le") + b"\x00\xd8" + " More.".encode("utf-16-le")
    out = cli("profile", write_bytes("bad16.txt", data)).json
    assert out["docs"][0]["encoding_used"] == "utf-16-le"
    assert "replacement_chars" in codes(out)
    assert out["word_count"] == 4


@pytest.mark.parametrize("bom", [b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff"])
def test_utf32_rejected(run_script, write_bytes, bom):
    path = write_bytes("u32.txt", bom + "hi".encode("utf-32-le" if bom[0] == 0xFF else "utf-32-be"))
    res = run_script("profile", path)
    assert res.code == 2
    assert "UTF-32 text is not supported. Save it as UTF-8: u32.txt" in res.err
    assert "Traceback" not in res.err
    assert len(res.err.strip().splitlines()) == 1


def test_binary_png_rejected(run_script, write_bytes):
    png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + bytes(range(256)) * 4
    res = run_script("profile", write_bytes("picture.png", png))
    assert res.code == 2
    assert res.err.strip() == "Error: This looks like a binary file, not text: picture.png"
    assert res.out == ""


def test_control_bytes_rejected(cli, write_bytes):
    res = cli("profile", write_bytes("ctrl.bin", b"\x01\x02\x03\x04ab" * 10))
    assert res.code == 2
    assert "binary" in res.err


def test_missing_file_exit_2(run_script, tmp_path):
    res = run_script("profile", tmp_path / "nope.txt")
    assert res.code == 2
    assert "File not found: nope.txt" in res.err
    assert "Traceback" not in res.err


def test_errors_name_basename_only(cli, tmp_path):
    res = cli("profile", tmp_path / "deep" / "folder" / "missing.txt")
    assert "deep" not in res.err and "missing.txt" in res.err


@pytest.mark.parametrize("data", [b"", b"   \n\t\n  \r\n\n"])
def test_empty_and_whitespace(cli, write_bytes, data):
    res = cli("profile", write_bytes("empty.txt", data))
    assert res.code == 0
    out = res.json
    assert out["word_count"] == 0 and out["sentence_count"] == 0 and out["paragraph_count"] == 0
    assert all(v is None for v in out["exposed"].values())
    assert len(out["exposed"]) == 28
    c = codes(out)
    assert "very_low_word_count" in c and "low_word_count" not in c
    assert c.count("value_undefined") == 1
    assert "NaN" not in res.out and "Infinity" not in res.out


def test_empty_view_all_has_null_function_words(cli, write_bytes):
    out = cli("profile", write_bytes("empty.txt", b""), "--view", "all").json
    assert len(out["scoring_only"]["function_word_freq"]) == 150
    assert all(v is None for v in out["scoring_only"]["function_word_freq"].values())
    assert out["scoring_only"]["char3_freq"] == {}


def test_one_sentence(cli, write_bytes):
    out = cli("profile", write_bytes("one.txt", b"This is the only sentence I wrote today.\n")).json
    e = out["exposed"]
    assert out["sentence_count"] == 1 and out["word_count"] == 8
    assert e["sentence_length_mean"] == 8.0
    assert e["sentence_length_sd"] is None
    assert e["sentence_length_p10"] == e["sentence_length_p50"] == e["sentence_length_p90"] == 8
    assert "value_undefined" in codes(out) and "few_sentences" in codes(out)


def test_no_punctuation(cli, write_bytes):
    data = b"just some words with no marks at all\nand another line of them\n\nnew paragraph here too\n"
    out = cli("profile", write_bytes("nopunct.txt", data)).json
    e = out["exposed"]
    assert out["word_count"] == 17
    assert out["sentence_count"] == 2  # each paragraph end closes a sentence
    assert out["paragraph_count"] == 2
    assert e["comma_per_1k"] == 0.0 and e["question_per_1k"] == 0.0
    assert e["question_sentence_share"] == 0.0


def test_low_word_count_warning(cli, write_bytes):
    words = ("word " * 500).encode("ascii")
    out = cli("profile", write_bytes("five.txt", words)).json
    c = codes(out)
    assert "low_word_count" in c and "very_low_word_count" not in c


def test_multiple_files_and_docs(cli):
    out = cli("profile", FIXTURES / "golden.txt", FIXTURES / "worked_example.txt").json
    assert out["doc_count"] == 2
    assert out["word_count"] == 140
    assert [d["name"] for d in out["docs"]] == ["golden.txt", "worked_example.txt"]


def test_streamed_matches_in_memory(cli, analyze, write_bytes, monkeypatch):
    para = (FIXTURES / "golden.txt").read_bytes().replace(b"\r\n", b"\n")
    data = para * 40
    path = write_bytes("medium.txt", data)
    normal = cli("profile", path, "--view", "all").json
    monkeypatch.setattr(analyze, "STREAM_THRESHOLD", 1000)
    monkeypatch.setattr(analyze, "PARTIAL_PARAGRAPH_CHARS", 200)
    streamed = cli("profile", path, "--view", "all").json
    assert "large_input_streamed" in codes(streamed)
    assert normal["exposed"] == streamed["exposed"]
    assert normal["scoring_only"] == streamed["scoring_only"]
    assert normal["sentence_count"] == streamed["sentence_count"]


def test_streamed_restarts_with_next_codec(cli, analyze, write_bytes, monkeypatch):
    monkeypatch.setattr(analyze, "STREAM_THRESHOLD", 1000)
    data = b"Plain ascii text here. " * 200 + "café at the end.\n".encode("cp1252")
    out = cli("profile", write_bytes("late.txt", data)).json
    assert out["docs"][0]["encoding_used"] == "cp1252"
    assert out["word_count"] == 4 * 200 + 4


def test_huge_file_streamed(cli, write_bytes):
    """A real file over 5 MB is streamed and counted correctly."""
    unit = b"The quick brown fox jumps over the lazy dog. It was fine.\n\n"  # 12 words, 2 sentences
    reps = (5 * 1024 * 1024) // len(unit) + 1000
    path = write_bytes("huge.txt", unit * reps)
    out = cli("profile", path).json
    assert "large_input_streamed" in codes(out)
    assert out["word_count"] == 12 * reps
    assert out["sentence_count"] == 2 * reps
    assert out["paragraph_count"] == reps


def test_long_paragraph_without_blank_lines(cli, analyze, write_bytes, monkeypatch):
    monkeypatch.setattr(analyze, "PARTIAL_PARAGRAPH_CHARS", 100)
    data = b"One two three. Dr. Who came by e.g. today. " * 50
    out_small = cli("profile", write_bytes("p.txt", data)).json
    assert out_small["sentence_count"] == 100
    assert out_small["paragraph_count"] == 1
