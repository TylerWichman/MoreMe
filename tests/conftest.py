"""Shared helpers for the analyze.py tests.

Every test that installs a skill uses a fake home folder under tmp_path; the
real home folder is never touched.
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
ANALYZE = REPO / "moreme" / "analyze.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
TEMPLATE = REPO / "moreme" / "templates" / "my-voice" / "SKILL.md.tmpl"


def _load():
    spec = importlib.util.spec_from_file_location("moreme_analyze", str(ANALYZE))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


analyze_module = _load()


@pytest.fixture
def analyze():
    return analyze_module


class Result(object):
    def __init__(self, code, out, err):
        self.code = code
        self.out = out
        self.err = err

    @property
    def json(self):
        return json.loads(self.out)


@pytest.fixture
def cli(capsys):
    """Run analyze.main in-process and return Result(code, stdout, stderr)."""

    def run(*args):
        capsys.readouterr()
        code = analyze_module.main([str(a) for a in args])
        captured = capsys.readouterr()
        return Result(code, captured.out, captured.err)

    return run


@pytest.fixture
def run_script():
    """Run analyze.py as a real process (UTF-8 decoding of its output is strict)."""

    def run(*args, **kwargs):
        env = dict(os.environ)
        env.pop("PYTHONIOENCODING", None)
        env.pop("PYTHONUTF8", None)
        env.update(kwargs.pop("env", {}) or {})
        proc = subprocess.run(
            [sys.executable, str(ANALYZE)] + [str(a) for a in args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=kwargs.pop("cwd", None),
        )
        return Result(proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8"))

    return run


@pytest.fixture
def write_bytes(tmp_path):
    def write(name, data):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    return write


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "fakehome"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("MOREME_TEST_GUARD", raising=False)
    return home
