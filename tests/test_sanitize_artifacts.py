"""tools/sanitize_artifacts.py with made-up machine values (no real ones)."""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "eval"))
import sanitize_artifacts as sa  # noqa: E402
from lib import artifacts  # noqa: E402

AT = "@"  # example addresses are split so tracked files hold none

WIN = {"home": "C:\\Users\\zqxjones", "users": ["zqxjones"], "names": ["Zqxjones", "Brindleford"],
       "emails": ["zqx.private" + AT + "example.net"]}
POSIX = {"home": "/home/zqxjones", "users": ["zqxjones"], "names": ["Zqxjones"], "emails": []}


@pytest.fixture
def s():
    return sa.Sanitizer(WIN)


@pytest.mark.parametrize("raw,clean", [
    ("C:\\Users\\zqxjones\\AppData\\Local\\Temp", "~\\AppData\\Local\\Temp"),
    ("c:\\users\\ZQXJONES\\x", "~\\x"),
    ("C:/Users/zqxjones/Documents", "~/Documents"),
    ("/c/Users/zqxjones/.claude", "~/.claude"),
    ("Edit(//c/Users/zqxjones/.claude/**)", "Edit(~/.claude/**)"),
    ("\"cwd\": \"C:\\\\Users\\\\zqxjones\\\\AppData\"", "\"cwd\": \"~\\\\AppData\""),
    ("file:///C:/Users/zqxjones/a.txt", "file:///~/a.txt"),
    ("C%3A%5CUsers%5Czqxjones%5Cx", "~%5Cx"),
    ("C:\\Users\\zqxjones", "~"),
    ("in Users\\zqxjones\\x", "in ~\\x"),
])
def test_home_path_forms(s, raw, clean):
    assert s.sanitize(raw)[0] == clean


def test_project_folder_slug(s):
    raw = "C--Users-zqxjones-AppData-Local-Temp-moreme-e2e-r1 and c--users-zqxjones-Documents"
    out, counts = s.sanitize(raw)
    assert out == "HOME-AppData-Local-Temp-moreme-e2e-r1 and HOME-Documents"
    assert counts["slug"] == 2


def test_names_case_sensitive_whole_word(s):
    out, counts = s.sanitize("Warmly, Zqxjones\nZqxjones Brindleford wrote. ZqxjonesBrindleford is a handle.")
    assert out == "Warmly, [name]\n[name] [name] wrote. ZqxjonesBrindleford is a handle."
    assert counts["name"] == 3


def test_username_any_case(s):
    assert s.sanitize("whoami: zqxjones / ZQXJONES")[0] == "whoami: [user] / [user]"


def test_username_inside_other_word_is_kept(s):
    assert s.sanitize("zqxjonesy and xzqxjones")[0] == "zqxjonesy and xzqxjones"


def test_emails(s):
    out, counts = s.sanitize("a zqx.private" + AT + "example.net b other" + AT + "mail.org c "
                             "123+handle@users.noreply.github.com d handle@users.noreply.github.com")
    assert out == "a [email] b [email] c 123+handle@users.noreply.github.com d handle@users.noreply.github.com"
    assert counts["email"] == 2


def test_findings_match_sanitize(s):
    raw = "C:\\Users\\zqxjones\\x Zqxjones zqxjones a" + AT + "b.io C--Users-zqxjones-y"
    kinds = sorted(k for k, _, _ in s.findings(raw))
    assert {"email", "home", "name", "slug", "username"} <= set(kinds)
    clean = s.sanitize(raw)[0]
    assert s.findings(clean) == []


def test_sanitized_output_is_stable(s):
    raw = "C:\\Users\\zqxjones\\x Zqxjones a" + AT + "b.io"
    once = s.sanitize(raw)[0]
    assert s.sanitize(once)[0] == once


def test_json_stays_valid(s):
    obj = {"cwd": "C:\\Users\\zqxjones\\AppData\\Local\\Temp\\moreme-e2e\\r1", "sig": "Love, Zqxjones"}
    text = s.sanitize(json.dumps(obj))[0]
    back = json.loads(text)
    assert back == {"cwd": "~\\AppData\\Local\\Temp\\moreme-e2e\\r1", "sig": "Love, [name]"}


def test_posix_home():
    s = sa.Sanitizer(POSIX)
    assert s.sanitize("/home/zqxjones/proj and -home-zqxjones-proj")[0] == "~/proj and HOME-proj"


def test_discover_uses_runtime_values(monkeypatch):
    monkeypatch.setattr(sa, "_git_global", lambda key: {"user.name": "Zqx Brindleford",
                                                        "user.email": "zqx" + AT + "example.net"}[key])
    t = sa.discover(home="C:\\Users\\zqxjones", user="zqxjones", env={"MOREME_PRIVATE_TOKENS": "Quillon, ab"})
    assert t["users"] == ["zqxjones"]
    assert t["names"] == ["Zqxjones", "Zqx", "Brindleford", "Quillon"]
    assert t["emails"] == ["zqx" + AT + "example.net"]


def test_discover_skips_generic_ci_users_and_noreply(monkeypatch):
    monkeypatch.setattr(sa, "_git_global", lambda key: {"user.name": "",
                                                        "user.email": "1+h@users.noreply.github.com"}[key])
    t = sa.discover(home="/home/runner", user="runner", env={})
    assert t["users"] == [] and t["names"] == [] and t["emails"] == []
    assert "home" not in [kind for kind, _, _ in sa.Sanitizer(t).rules]


def test_discover_defaults_to_this_machine():
    t = sa.discover(use_git=False, env={})
    assert t["home"] == str(Path.home())


def test_disclose_markdown_once():
    text = "<!-- hdr -->\n\n# Title\n\nbody\n"
    once = sa.disclose_markdown(text)
    assert once.splitlines()[2:5] == ["# Title", "", "> " + sa.DISCLOSURE]
    assert sa.disclose_markdown(once) == once
    assert "home folder path replaced with ~ by tools/sanitize_artifacts.py" in sa.DISCLOSURE.lower()


def test_sanitize_file_and_cli(tmp_path, monkeypatch):
    monkeypatch.setattr(sa, "_DEFAULT", sa.Sanitizer(WIN))
    f = tmp_path / "a.md"
    f.write_text("path C:\\Users\\zqxjones\\x\n", encoding="utf-8")
    b = tmp_path / "b.bin"
    b.write_bytes(b"\x00\x01C:\\Users\\zqxjones")
    assert sa.main(["--check", str(f), str(b)]) == 1
    assert f.read_text(encoding="utf-8") == "path C:\\Users\\zqxjones\\x\n"
    assert sa.main(["--write", str(tmp_path)]) == 0
    assert f.read_text(encoding="utf-8") == "path ~\\x\n"
    assert b.read_bytes() == b"\x00\x01C:\\Users\\zqxjones"  # binary files are never rewritten
    assert sa.main(["--check", str(f)]) == 0


def test_artifacts_write_committed(tmp_path, monkeypatch):
    monkeypatch.setattr(sa, "_DEFAULT", sa.Sanitizer(WIN))
    p = artifacts.write_committed(tmp_path / "t.md", "# T\n\ncwd C:/Users/zqxjones/x\n", disclose=True)
    text = p.read_text(encoding="utf-8")
    assert "zqxjones" not in text and "cwd ~/x" in text and sa.DISCLOSURE in text
    j = artifacts.write_committed_json(tmp_path / "m.json", {"C:\\Users\\zqxjones": ["Zqxjones", 3]})
    assert json.loads(j.read_text(encoding="utf-8")) == {"~": ["[name]", 3]}


def test_evidence_root_resolution(tmp_path):
    assert artifacts.evidence_root(repo=tmp_path, env={"MOREME_EVIDENCE_DIR": str(tmp_path / "ev")}) == tmp_path / "ev"
    ws = tmp_path / "ws"
    (ws / "vault" / "clients").mkdir(parents=True)
    repo = ws / "inputs" / "MoreMe"
    repo.mkdir(parents=True)
    assert artifacts.evidence_root(repo=repo, env={}) == ws.resolve() / artifacts.VAULT_EVIDENCE
    lone = tmp_path / "lone" / "MoreMe"
    lone.mkdir(parents=True)
    assert artifacts.evidence_root(repo=lone, env={}) == lone.resolve() / ".evidence"
