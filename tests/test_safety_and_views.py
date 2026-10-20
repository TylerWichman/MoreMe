"""Stdlib-only, no network, no subprocess/eval/exec, exposed/scoring-only separation, CLI basics."""

import ast
import importlib.util
import json
import subprocess
import sys

import pytest

from conftest import ANALYZE, FIXTURES, REPO

# Standard-library modules analyze.py may import (all exist in CPython 3.8).
STDLIB_ALLOWED = {
    "argparse", "codecs", "collections", "datetime", "decimal", "io", "json", "math", "os", "re",
    "secrets", "shutil", "statistics", "sys", "tempfile", "traceback", "unicodedata", "zipfile",
    "pathlib",
}
NETWORK_MODULES = {
    "socket", "ssl", "http", "urllib", "ftplib", "smtplib", "poplib", "imaplib", "telnetlib",
    "asyncio", "socketserver", "xmlrpc", "requests", "urllib3", "aiohttp", "webbrowser", "select",
    "selectors", "nntplib", "subprocess", "multiprocessing",
}
FORBIDDEN = ("scoring_only", "function_word_freq", "char3_freq", "delta_fw", "char3_cosine", "reference_stats")


def _tree():
    return ast.parse(ANALYZE.read_text(encoding="utf-8"))


def test_only_stdlib_imports():
    names = set()
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            names.add(node.module.split(".")[0])
    assert names <= STDLIB_ALLOWED, names - STDLIB_ALLOWED
    assert not names & NETWORK_MODULES


def test_no_dynamic_code_or_dynamic_imports():
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("eval", "exec", "compile", "__import__"), node.func.id
        if isinstance(node, ast.Attribute):
            assert node.attr not in ("system", "popen", "import_module"), node.attr


def test_no_network_module_loaded_at_runtime(tmp_path):
    """Run every command path once in a clean interpreter and check sys.modules."""
    script = tmp_path / "probe.py"
    script.write_text(
        "import importlib.util, sys, io, contextlib\n"
        "spec = importlib.util.spec_from_file_location('a', sys.argv[1])\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "with contextlib.redirect_stdout(io.StringIO()):\n"
        "    m.main(['--version']); m.main(['profile', sys.argv[2], '--view', 'all'])\n"
        "ok = {'urllib', 'urllib.parse'}  # pathlib imports urllib.parse (string parsing only)\n"
        "bad = sorted(n for n in sys.modules if n.split('.')[0] in set(sys.argv[3].split(',')) and n not in ok)\n"
        "print(','.join(bad))\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(script), str(ANALYZE), str(FIXTURES / "golden.txt"), ",".join(sorted(NETWORK_MODULES))],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.decode().strip() == ""


def test_exposed_view_has_exactly_28_keys_and_no_forbidden_tokens(cli, analyze):
    res = cli("profile", FIXTURES / "golden.txt")
    data = res.json
    assert list(data["exposed"]) == list(analyze.EXPOSED_KEYS)
    assert len(data["exposed"]) == 28
    assert "scoring_only" not in data
    assert data["view"] == "exposed"
    for token in FORBIDDEN:
        assert token not in res.out
    # no function word appears as a key anywhere in the exposed output
    keys = set()

    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                keys.add(k)
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(data)
    assert not keys & set(analyze.FUNCTION_WORDS)


def test_exposed_view_out_file_has_no_forbidden_tokens(cli, tmp_path):
    out = tmp_path / "profile.json"
    res = cli("profile", FIXTURES / "golden.txt", "--out", out)
    assert res.code == 0
    assert res.json == {"ok": True, "out": str(out), "warnings": json.loads(out.read_text("utf-8"))["warnings"]}
    text = out.read_text(encoding="utf-8")
    for token in FORBIDDEN:
        assert token not in text


def test_view_all_shape(cli, analyze):
    data = cli("profile", FIXTURES / "golden.txt", "--view", "all").json
    so = data["scoring_only"]
    assert list(so) == ["function_word_freq", "char3_freq"]
    assert list(so["function_word_freq"]) == list(analyze.FUNCTION_WORDS)
    assert 0 < len(so["char3_freq"]) <= 300
    assert all(len(g) == 3 for g in so["char3_freq"])
    assert so["function_word_freq"]["the"] == round(10 / 119 * 1000, 4)  # "the" appears 10 times in golden.txt


def test_function_word_list_rules(analyze):
    words = analyze.FUNCTION_WORDS
    assert len(words) == 150 and len(set(words)) == 150
    exposed_pronouns = {"i", "me", "my", "mine", "myself", "we", "us", "our", "ours", "ourselves",
                        "you", "your", "yours", "yourself", "yourselves"}
    assert not set(words) & exposed_pronouns
    assert all("'" not in w and w == w.lower() for w in words)


def test_profile_object_shape(cli):
    data = cli("profile", FIXTURES / "golden.txt").json
    assert list(data) == ["schema_version", "analyze_version", "view", "word_count", "sentence_count",
                          "paragraph_count", "doc_count", "docs", "exposed", "warnings"]
    assert data["schema_version"] == "1" and data["analyze_version"] == "1.0.0"
    for value in data["exposed"].values():
        if isinstance(value, float):
            assert round(value, 4) == value


def test_version(run_script):
    res = run_script("--version")
    assert res.code == 0
    data = res.json
    assert data["analyze_version"] == "1.0.0" and data["schema_version"] == "1"
    assert data["python"] == "{0}.{1}.{2}".format(*sys.version_info[:3])


def test_utf8_stdout_regardless_of_console(run_script, write_bytes):
    path = write_bytes("café — notes.txt", "Hello there \U0001F642.\n".encode("utf-8"))
    res = run_script("profile", path)  # decoded as strict UTF-8 by the fixture
    assert res.code == 0
    assert "café — notes.txt" in res.out


def test_help_text_is_plain(run_script):
    res = run_script("--help")
    assert res.code == 0
    lowered = res.out.lower()
    assert "—" not in res.out
    for word in ("seamless", "leverage", "robust", "unlock", "empower", "magic"):
        assert word not in lowered


def test_no_command_exit_2(cli):
    res = cli()
    assert res.code == 2


def test_internal_error_one_line_and_debug_traceback(cli, analyze, monkeypatch):
    def boom(args):
        raise RuntimeError("something broke")

    monkeypatch.setattr(analyze, "cmd_profile", boom)  # build_parser reads the name at call time
    res = cli("profile", FIXTURES / "golden.txt")
    assert res.code == 1
    assert res.err.strip() == "Internal error (RuntimeError): something broke"
    assert "Traceback" not in res.err
    res = cli("profile", FIXTURES / "golden.txt", "--debug")
    assert res.code == 1
    assert "Traceback" in res.err


def test_check_prose_banned_list_matches():
    path = REPO / "tools" / "check_prose.py"
    if not path.is_file():
        pytest.skip("tools/check_prose.py not present")
    spec = importlib.util.spec_from_file_location("check_prose", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from conftest import analyze_module

    assert tuple(module.BANNED_PHRASES) == tuple(analyze_module.BANNED_PHRASES)


@pytest.mark.parametrize("rel", ["moreme/templates", "moreme/SKILL.md", "moreme/reference", "docs/example-run", "eval/skills"])
def test_forbidden_tokens_absent_from_skill_facing_files(rel):
    root = REPO / rel
    if not root.exists():
        pytest.skip(rel + " not present yet")
    files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file() and p.suffix in (".md", ".tmpl", ".txt")]
    for path in files:
        text = path.read_text(encoding="utf-8").lower()
        for token in FORBIDDEN:
            assert token not in text, "{0} contains {1}".format(path, token)
