"""The CI workflow exists, parses (when PyYAML is available), and has the frozen matrix."""

import re

import pytest

from conftest import REPO

CI = REPO / ".github" / "workflows" / "ci.yml"


def test_ci_text_contract():
    text = CI.read_text(encoding="utf-8")
    assert "not run until the repo is pushed" in text
    assert re.search(r"uses: astral-sh/setup-uv@v\d+", text)
    assert re.search(r"uses: actions/checkout@v\d+", text)
    assert "uses: actions/setup-python" not in text
    assert "os: [ubuntu-latest, macos-latest, windows-latest]" in text
    assert 'python-version: ["3.8", "3.11", "3.13"]' in text
    assert '"pytest<8.4"' in text
    assert "\t" not in text


def test_ci_yaml_parses():
    yaml = pytest.importorskip("yaml")
    data = yaml.safe_load(CI.read_text(encoding="utf-8"))
    job = data["jobs"]["test"]
    matrix = job["strategy"]["matrix"]
    assert matrix["os"] == ["ubuntu-latest", "macos-latest", "windows-latest"]
    assert matrix["python-version"] == ["3.8", "3.11", "3.13"]
    uses = [s.get("uses", "") for s in job["steps"]]
    assert any(u.startswith("astral-sh/setup-uv@") for u in uses)
    assert all("@" in u for u in uses if u)
