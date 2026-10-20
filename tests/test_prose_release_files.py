"""The shipped skill prose passes the prose checker, and the checker stays stdlib-only (T-004)."""

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHECKER = REPO / "tools" / "check_prose.py"

spec = importlib.util.spec_from_file_location("check_prose", str(CHECKER))
cp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cp)

# Standard library modules check_prose.py may import (all exist on Python 3.8).
ALLOWED_IMPORTS = {"argparse", "fnmatch", "re", "sys", "pathlib"}
NETWORK_MODULES = {"socket", "http", "urllib", "ftplib", "smtplib", "ssl", "requests", "asyncio"}


def test_default_targets_cover_skill_files():
    files = [cp.rel_display(f) for f in cp.iter_files(cp.DEFAULT_TARGETS)]
    assert "moreme/SKILL.md" in files
    assert "moreme/templates/my-voice/SKILL.md.tmpl" in files
    refs = [f for f in files if f.startswith("moreme/reference/")]
    assert len(refs) >= 2


def test_zero_violations_in_release_prose():
    checked, violations = cp.check_paths(cp.DEFAULT_TARGETS)
    assert checked, "nothing was checked"
    assert violations == [], "\n".join(str(v) for v in violations)


def test_cli_default_run_passes():
    r = subprocess.run([sys.executable, str(CHECKER)], cwd=str(REPO),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert r.returncode == 0, r.stdout.decode("utf-8") + r.stderr.decode("utf-8")
    assert "0 violation(s)" in r.stdout.decode("utf-8")


def test_checker_imports_only_allowed_stdlib():
    tree = ast.parse(CHECKER.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add((node.module or "").split(".")[0])
    assert names <= ALLOWED_IMPORTS, names - ALLOWED_IMPORTS
    assert not (names & NETWORK_MODULES)


def test_exempt_file_entries_have_reasons():
    for raw in (REPO / "tools" / "prose_exempt.txt").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        assert "#" in line, "exemption without a reason: " + line
