"""reference-stats, compare, attribute, and report."""

import json

import pytest

from conftest import FIXTURES

PERSONA_A = (
    "The morning was cold and the river ran high. We walked along the bank, and the dog ran ahead of us. "
    "It was the kind of day that makes a person slow down. Nobody spoke for a while; the birds did the talking. "
)
PERSONA_B = (
    "Quick update: shipping is late again! Can you ping the vendor? I think they owe us a call. "
    "Honestly, I'm tired of chasing this. Let's fix it today, ok? Thanks so much!! "
)


def make_train(tmp_path, personas):
    train = tmp_path / "train"
    for pid, text, files in personas:
        folder = train / pid
        folder.mkdir(parents=True)
        for i in range(files):
            (folder / "doc{0:02d}.txt".format(i)).write_text(text * 6, encoding="utf-8")
    return train


@pytest.fixture
def refstats(tmp_path, cli):
    train = make_train(tmp_path, [("p-b", PERSONA_B, 3), ("p-a", PERSONA_A, 3)])
    out = tmp_path / "reference_stats.json"
    res = cli("reference-stats", train, "--chunk-words", "100", "--out", out)
    assert res.code == 0, res.err
    return out, res.json


def test_reference_stats_schema(refstats, analyze):
    path, printed = refstats
    data = json.loads(path.read_text(encoding="utf-8"))
    assert list(data) == ["schema_version", "analyze_version", "created", "source", "sd_type",
                          "function_words", "exposed", "excluded"]
    assert data["sd_type"] == "population"
    src = data["source"]
    assert src["split"] == "train" and src["chunk_words"] == 100
    assert src["personas"] == ["p-a", "p-b"]  # sorted
    assert src["total_chunks"] == sum(src["chunks_per_persona"].values()) == printed["total_chunks"]
    assert all(n >= 3 for n in src["chunks_per_persona"].values())
    assert list(data["function_words"]) == list(analyze.FUNCTION_WORDS)
    assert list(data["exposed"]) == list(analyze.EXPOSED_KEYS)
    for stat in list(data["function_words"].values()) + list(data["exposed"].values()):
        assert set(stat) == {"mean", "sd"}
    # neither persona uses long dashes, so that feature has zero spread and is excluded
    assert "em_dash_per_1k" in data["excluded"]
    assert all(not (data["function_words"].get(n) or data["exposed"].get(n))["sd"] for n in data["excluded"])
    assert printed["ok"] is True and printed["warnings"] == []


def test_chunks_are_exact_word_counts(analyze):
    text = "One two, three.\n\nFour five six seven! Eight nine ten eleven"
    chunks = analyze.chunk_text(text, 4)
    assert chunks == ["One two, three.\n\nFour", "five six seven! Eight"]


def test_reference_stats_needs_two_personas_and_three_chunks(tmp_path, cli):
    one = make_train(tmp_path / "one", [("solo", PERSONA_A, 3)])
    res = cli("reference-stats", one, "--chunk-words", "100", "--out", tmp_path / "r.json")
    assert res.code == 2 and "at least 2 persona" in res.err
    short = make_train(tmp_path / "short", [("a", PERSONA_A, 3), ("b", "Too short. ", 1)])
    res = cli("reference-stats", short, "--chunk-words", "100", "--out", tmp_path / "r.json")
    assert res.code == 2 and "Persona b has 0 chunks of 100 words; it needs at least 3." in res.err
    assert not (tmp_path / "r.json").exists()


def profile(cli, tmp_path, name, text, view="all"):
    src = tmp_path / (name + ".txt")
    src.write_text(text, encoding="utf-8")
    out = tmp_path / (name + ".json")
    assert cli("profile", src, "--view", view, "--out", out).code == 0
    return out


def test_compare_without_reference(cli, tmp_path):
    a = profile(cli, tmp_path, "a", PERSONA_A * 3)
    b = profile(cli, tmp_path, "b", PERSONA_B * 3)
    data = cli("compare", a, b).json
    assert data["exposed_distance"] is None and data["delta_fw"] is None
    assert all(v is None for v in data["per_feature"].values())
    assert data["char3_cosine"] is not None and 0 < data["char3_cosine"] <= 1
    assert "reference_stats_missing" in [w["code"] for w in data["warnings"]]


def test_compare_with_reference(cli, tmp_path, refstats, analyze):
    ref, _ = refstats
    a = profile(cli, tmp_path, "a", PERSONA_A * 3)
    b = profile(cli, tmp_path, "b", PERSONA_B * 3)
    data = cli("compare", a, b, "--reference-stats", ref).json
    assert list(data) == ["schema_version", "exposed_distance", "delta_fw", "char3_cosine", "per_feature", "warnings"]
    assert data["exposed_distance"] > 0 and data["delta_fw"] > 0
    assert data["per_feature"]["em_dash_per_1k"] is None
    codes = [w["code"] for w in data["warnings"]]
    assert "feature_excluded" in codes
    # hand check of one signed z difference
    stats = json.loads(ref.read_text("utf-8"))["exposed"]["comma_per_1k"]
    pa = json.loads(a.read_text("utf-8"))["exposed"]["comma_per_1k"]
    pb = json.loads(b.read_text("utf-8"))["exposed"]["comma_per_1k"]
    expected = (pa - stats["mean"]) / stats["sd"] - (pb - stats["mean"]) / stats["sd"]
    assert data["per_feature"]["comma_per_1k"] == round(expected, 4)
    same = cli("compare", a, a, "--reference-stats", ref).json
    assert same["exposed_distance"] == 0.0 and same["delta_fw"] == 0.0 and same["char3_cosine"] == 0.0


def test_compare_exposed_view_gives_view_not_all(cli, tmp_path, refstats):
    ref, _ = refstats
    a = profile(cli, tmp_path, "a", PERSONA_A * 3, view="exposed")
    b = profile(cli, tmp_path, "b", PERSONA_B * 3)
    data = cli("compare", a, b, "--reference-stats", ref).json
    assert data["delta_fw"] is None and data["char3_cosine"] is None
    assert data["exposed_distance"] is not None
    assert "view_not_all" in [w["code"] for w in data["warnings"]]


def test_compare_rejects_non_profile(cli, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{\"hello\": 1}", encoding="utf-8")
    assert cli("compare", bad, bad).code == 2
    bad.write_text("not json", encoding="utf-8")
    assert cli("compare", bad, bad).code == 2


def test_attribute(cli, tmp_path, refstats):
    ref, _ = refstats
    cands = tmp_path / "cands"
    cands.mkdir()
    profile(cli, cands, "p-a", PERSONA_A * 4)
    profile(cli, cands, "p-b", PERSONA_B * 4)
    for f in list(cands.glob("*.txt")):
        f.unlink()
    draft = profile(cli, tmp_path, "draft", PERSONA_B * 2)
    data = cli("attribute", draft, "--candidates", cands, "--reference-stats", ref).json
    assert data["predicted"] == "p-b"
    assert data["k"] == 2 and data["chance"] == 0.5
    assert list(data["deltas"]) == ["p-a", "p-b"]
    assert data["deltas"]["p-b"] < data["deltas"]["p-a"]


def test_attribute_ties_broken_by_sorted_id(cli, tmp_path, refstats):
    ref, _ = refstats
    cands = tmp_path / "cands"
    cands.mkdir()
    profile(cli, cands, "zeta", PERSONA_A * 4)
    profile(cli, cands, "alpha", PERSONA_A * 4)
    draft = profile(cli, tmp_path, "draft", PERSONA_B * 2)
    data = cli("attribute", draft, "--candidates", cands, "--reference-stats", ref).json
    assert data["deltas"]["alpha"] == data["deltas"]["zeta"]
    assert data["predicted"] == "alpha"


def test_attribute_input_errors(cli, tmp_path, refstats):
    ref, _ = refstats
    cands = tmp_path / "cands"
    cands.mkdir()
    profile(cli, cands, "only", PERSONA_A * 4)
    draft = profile(cli, tmp_path, "draft", PERSONA_B * 2)
    assert cli("attribute", draft, "--candidates", cands, "--reference-stats", ref).code == 2
    profile(cli, cands, "exposed-one", PERSONA_B * 4, view="exposed")
    res = cli("attribute", draft, "--candidates", cands, "--reference-stats", ref)
    assert res.code == 2 and "view all" in res.err
    exposed_draft = profile(cli, tmp_path, "draft2", PERSONA_B, view="exposed")
    assert cli("attribute", exposed_draft, "--candidates", cands, "--reference-stats", ref).code == 2


def test_report_worked_example(cli, tmp_path, analyze):
    prof = tmp_path / "p.json"
    cli("profile", FIXTURES / "worked_example.txt", "--out", prof)
    res = cli("report", prof)
    assert res.code == 0
    text = res.out
    assert "a typical sentence is 4 words" in text
    assert "Short ones are about 1 word and long ones about 8 words" in text
    assert "exclamation marks 47.6" in text
    assert "questions 20%" in text
    assert "start lowercase 80%" in text
    assert "fewer than 300 words" in text
    for token in ("scoring_only", "function_word_freq", "char3_freq", "delta_fw", "char3_cosine", "reference_stats"):
        assert token not in text
    assert "—" not in text
    assert analyze.find_banned(text) == []
    for word in analyze.FUNCTION_WORDS:
        assert "\"" + word + "\":" not in text


def test_report_empty_profile_and_out(cli, tmp_path, write_bytes):
    prof = tmp_path / "p.json"
    cli("profile", write_bytes("e.txt", b""), "--out", prof)
    out = tmp_path / "report.txt"
    res = cli("report", prof, "--out", out)
    assert res.json == {"ok": True, "out": str(out), "warnings": []}
    text = out.read_text(encoding="utf-8")
    assert "not measured (too little text)" in text
    assert "None" not in text


def test_report_passes_prose_checker_if_present(cli, tmp_path):
    import importlib.util
    from conftest import REPO

    checker = REPO / "tools" / "check_prose.py"
    if not checker.is_file():
        pytest.skip("tools/check_prose.py not present")
    prof = tmp_path / "p.json"
    cli("profile", FIXTURES / "golden.txt", "--out", prof)
    out = tmp_path / "report.txt"
    cli("report", prof, "--out", out)
    spec = importlib.util.spec_from_file_location("check_prose", str(checker))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text = out.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "—" not in text
    for phrase in module.BANNED_PHRASES:
        assert phrase not in lowered


def test_display_rules(analyze):
    d = analyze.display_value
    assert d("comma_per_1k", 47.619) == "47.6"
    assert d("comma_per_1k", 0.0) == "0.0"
    assert d("comma_per_1k", 0.25) == "0.3"  # half up, not banker's rounding
    assert d("emoji_per_1k", 2.45) == "2.5"
    assert d("sentence_length_p50", 4) == "4"
    assert d("paragraph_length_mean", 39.5) == "40"
    assert d("paragraph_length_mean", 7.0) == "7"
    assert d("question_sentence_share", 0.2) == "20%"
    assert d("lowercase_sentence_start_share", 0.125) == "13%"
    assert d("question_sentence_share", None) == "not measured (too little text)"
