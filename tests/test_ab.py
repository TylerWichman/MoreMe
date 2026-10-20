"""Blind A/B: ab-shuffle uses secrets and prints no mapping; ab-present and ab-reveal."""

import ast
import json
import re

from conftest import ANALYZE

WITH = "Hi Dana, quick one: can you send the file today? Cheers, Sam"
WITHOUT = "Dear Dana, I hope you are well. Could you please send the file at your convenience? Best regards."


def setup_drafts(folder):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "draft-with.md").write_text("\n" + WITH + "\n\n", encoding="utf-8")
    (folder / "draft-without.md").write_text(WITHOUT + "\n", encoding="utf-8")


def test_shuffle_uses_secrets_not_random():
    tree = ast.parse(ANALYZE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module)
    assert "secrets" in imported and "random" not in imported
    func = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "cmd_ab_shuffle"][0]
    calls = [n for n in ast.walk(func) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)]
    assert any(c.value.id == "secrets" for c in calls)


def test_shuffle_follows_secrets(cli, analyze, tmp_path, monkeypatch):
    for value, expected in ((0, "with"), (1, "without")):
        monkeypatch.setattr(analyze.secrets, "randbelow", lambda n, v=value: v)
        folder = tmp_path / str(value)
        cli("ab-shuffle", "--out", folder)
        assert json.loads((folder / "ab-mapping.json").read_text("utf-8"))["A"] == expected


def test_shuffle_prints_no_mapping(cli, tmp_path):
    res = cli("ab-shuffle", "--out", tmp_path / "out")
    assert res.code == 0
    assert res.json == {"labels": ["A", "B"], "warnings": []}
    assert "with" not in res.out
    mapping = json.loads((tmp_path / "out" / "ab-mapping.json").read_text("utf-8"))
    assert list(mapping) == ["schema_version", "A", "B", "created"]
    assert mapping["schema_version"] == "1"
    assert sorted([mapping["A"], mapping["B"]]) == ["with", "without"]


def test_shuffle_is_balanced_over_1000_runs(cli, tmp_path):
    with_on_a = 0
    for i in range(1000):
        folder = tmp_path / "r"
        cli("ab-shuffle", "--out", folder)
        with_on_a += json.loads((folder / "ab-mapping.json").read_text("utf-8"))["A"] == "with"
    assert 450 <= with_on_a <= 550, with_on_a


def test_present_format_and_no_labels(cli, tmp_path):
    folder = tmp_path / "ab"
    setup_drafts(folder)
    cli("ab-shuffle", "--out", folder)
    mapping = json.loads((folder / "ab-mapping.json").read_text("utf-8"))
    res = cli("ab-present", folder)
    assert res.code == 0
    drafts = {"with": WITH, "without": WITHOUT}
    expected = "Draft A\n\n{0}\n\nDraft B\n\n{1}\n".format(drafts[mapping["A"]], drafts[mapping["B"]])
    assert res.out == expected
    outside = res.out.replace(WITH, "").replace(WITHOUT, "")
    assert not re.search(r"\bwith(out)?\b", outside, re.IGNORECASE)
    assert "{" not in res.out


def test_present_needs_mapping_and_drafts(cli, tmp_path):
    folder = tmp_path / "ab"
    setup_drafts(folder)
    assert cli("ab-present", folder).code == 2
    cli("ab-shuffle", "--out", folder)
    (folder / "draft-without.md").unlink()
    res = cli("ab-present", folder)
    assert res.code == 2 and "draft-without.md" in res.err


def test_reveal_once(cli, tmp_path):
    folder = tmp_path / "ab"
    setup_drafts(folder)
    cli("ab-shuffle", "--out", folder)
    mapping = json.loads((folder / "ab-mapping.json").read_text("utf-8"))
    res = cli("ab-reveal", folder, "--pick", "b")  # lowercase accepted
    assert res.code == 0
    data = res.json
    assert list(data) == ["schema_version", "picked", "picked_arm", "mapping", "revealed", "warnings"]
    assert data["picked"] == "B" and data["picked_arm"] == mapping["B"]
    assert data["mapping"] == {"A": mapping["A"], "B": mapping["B"]}
    saved = json.loads((folder / "ab-result.json").read_text("utf-8"))
    assert "warnings" not in saved and saved["picked_arm"] == mapping["B"]
    again = cli("ab-reveal", folder, "--pick", "A")
    assert again.code == 2 and "already revealed" in again.err


def test_reveal_rejects_bad_pick(cli, tmp_path):
    folder = tmp_path / "ab"
    setup_drafts(folder)
    cli("ab-shuffle", "--out", folder)
    assert cli("ab-reveal", folder, "--pick", "C").code == 2
    assert not (folder / "ab-result.json").exists()
