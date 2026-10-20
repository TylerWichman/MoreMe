"""Timing curve for profile on 1, 5, and 10 MB (brief: under 5 s, 30 s, 60 s on the build host).

Skipped unless MOREME_PERF=1. Results are appended to docs/test-output/perf.txt.
"""

import os
import platform
import sys
import time

import pytest

from conftest import FIXTURES, REPO, analyze_module

pytestmark = [
    pytest.mark.perf,
    pytest.mark.skipif(os.environ.get("MOREME_PERF") != "1", reason="set MOREME_PERF=1 to run the timing test"),
]

LIMITS = {1: 5.0, 5: 30.0, 10: 60.0}


@pytest.mark.parametrize("megabytes", [1, 5, 10])
def test_profile_timing(tmp_path, megabytes):
    unit = (FIXTURES / "golden.txt").read_bytes().replace(b"\r\n", b"\n") + b"\n"
    target = megabytes * 1024 * 1024
    path = tmp_path / "big.txt"
    path.write_bytes(unit * (target // len(unit) + 1))
    start = time.perf_counter()
    profile = analyze_module.profile_files([str(path)], "all")
    elapsed = time.perf_counter() - start
    line = "{0} MB: {1:.2f} s, {2:,} words, Python {3}, {4}, {5} logical CPUs\n".format(
        megabytes, elapsed, profile["word_count"], platform.python_version(), platform.platform(), os.cpu_count())
    out = REPO / "docs" / "test-output" / "perf.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(str(out), "a", encoding="utf-8") as handle:
        handle.write(line)
    assert elapsed < LIMITS[megabytes], line
