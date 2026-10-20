"""cleanup_session_folders.py on a fake home with decoys. The real home is never used."""
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "eval"))
from lib import childrun  # noqa: E402

spec = importlib.util.spec_from_file_location("cleanup_session_folders",
                                              str(REPO / "eval" / "tools" / "cleanup_session_folders.py"))
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)

FAKE_TEMP = r"C:\Users\fakeuser\AppData\Local\Temp"
T = "C--Users-fakeuser-AppData-Local-Temp"

SHOULD_MATCH = [
    T + "-moreme-eval",
    T + "-moreme-eval-spike-s2-a-with-r1",
    T + "-moreme-e2e-run-20261020-1",
]
# Case variants live in their own fake home: NTFS is case-insensitive, so
# "...-MoreMe-eval" and "...-moreme-eval" cannot both exist in one folder (WIN-015).
CASE_DECOYS = [
    T + "-MoreMe-eval",
    T + "-MoreMe-eval-x",
    T + "-MOREME-E2E-r1",
    "c--Users-fakeuser-AppData-Local-Temp-moreme-eval",    # drive-letter case variant
]
DECOYS = [
    T,                                                     # bare temp entry
    T + "-moreme-evaluation",                              # not at a "-" boundary
    T + "-moreme-e2ex",
    "C--Users-fakeuser-Documents-OneShot-inputs-MoreMe-eval",  # the repo's own eval project
    "C--Users-fakeuser-Documents-OneShot-inputs-MoreMe",
    "C--Users-fakeuser-Documents-OneShot",
    "x-" + T + "-moreme-eval",                             # not anchored
]


def make_link(link, target):
    """Directory link: junction on Windows (no admin needed), else symlink."""
    if os.name == "nt":
        try:
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
            return "junction"
        except Exception:
            pass
    try:
        os.symlink(str(target), str(link), target_is_directory=True)
        return "symlink"
    except (OSError, NotImplementedError):
        return None


@pytest.fixture
def fake_home(tmp_path):
    home = tmp_path / "home"
    projects = home / ".claude" / "projects"
    projects.mkdir(parents=True)
    for n in SHOULD_MATCH + DECOYS:
        (projects / n).mkdir()
        (projects / n / "memory").mkdir()
    (projects / SHOULD_MATCH[2] / "session.jsonl").write_text("{}", encoding="utf-8")
    nest = projects / (T + "-other")
    (nest / (T + "-moreme-e2e-nested")).mkdir(parents=True)
    (projects / (T + "-moreme-e2e-a-file")).write_text("not a dir", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "canary.txt").write_text("keep", encoding="utf-8")
    return home, projects, outside


def run(home, *extra, capsys=None):
    code = cleanup.main(["--home", str(home), "--temp-dir", FAKE_TEMP] + list(extra))
    assert code == 0
    return json.loads(capsys.readouterr().out)


def test_prefixes_are_derived_from_temp_path():
    assert cleanup.prefixes(FAKE_TEMP) == [T + "-moreme-eval", T + "-moreme-e2e"]
    real = cleanup.prefixes()
    base = childrun.project_folder_name(childrun.temp_base())
    assert real == [base + "-moreme-eval", base + "-moreme-e2e"]


def test_dry_run_is_default_and_deletes_nothing(fake_home, capsys):
    home, projects, _ = fake_home
    before = sorted(os.listdir(str(projects)))
    out = run(home, capsys=capsys)
    assert out["mode"] == "dry-run"
    assert out["deleted"] == []
    assert sorted(out["matched"]) == sorted(SHOULD_MATCH)
    assert out["skipped_not_dir"] == [T + "-moreme-e2e-a-file"]
    assert sorted(os.listdir(str(projects))) == before


@pytest.mark.parametrize("name", DECOYS + CASE_DECOYS)
def test_decoys_never_match(name):
    assert not cleanup.name_matches(name, cleanup.prefixes(FAKE_TEMP))


def test_case_variant_folders_on_disk_are_kept(tmp_path, capsys):
    home = tmp_path / "home"
    projects = home / ".claude" / "projects"
    projects.mkdir(parents=True)
    for n in CASE_DECOYS[:3]:
        (projects / n).mkdir()
    out = run(home, "--delete", capsys=capsys)
    assert out["matched"] == [] and out["deleted"] == []
    assert sorted(os.listdir(str(projects))) == sorted(CASE_DECOYS[:3])


def test_delete_removes_only_matches(fake_home, capsys):
    home, projects, _ = fake_home
    out = run(home, "--delete", capsys=capsys)
    assert out["mode"] == "delete"
    assert sorted(out["deleted"]) == sorted(SHOULD_MATCH)
    left = set(os.listdir(str(projects)))
    for n in SHOULD_MATCH:
        assert n not in left
    for n in DECOYS:
        assert n in left and (projects / n / "memory").is_dir()
    assert (projects / (T + "-other") / (T + "-moreme-e2e-nested")).is_dir()
    assert (projects / (T + "-moreme-e2e-a-file")).is_file()


def test_matching_link_is_skipped_and_target_untouched(fake_home, capsys):
    home, projects, outside = fake_home
    kind = make_link(projects / (T + "-moreme-e2e-link"), outside)
    if kind is None:
        pytest.skip("cannot create a directory link here")
    out = run(home, "--delete", capsys=capsys)
    assert T + "-moreme-e2e-link" in out["skipped_links"]
    assert T + "-moreme-e2e-link" not in out["deleted"]
    assert (outside / "canary.txt").read_text(encoding="utf-8") == "keep"
    assert os.path.lexists(str(projects / (T + "-moreme-e2e-link")))


def test_link_inside_matched_folder_is_not_entered(fake_home, capsys):
    home, projects, outside = fake_home
    kind = make_link(projects / SHOULD_MATCH[0] / "escape", outside)
    if kind is None:
        pytest.skip("cannot create a directory link here")
    out = run(home, "--delete", capsys=capsys)
    assert SHOULD_MATCH[0] in out["deleted"]
    assert (outside / "canary.txt").read_text(encoding="utf-8") == "keep"


def test_projects_folder_that_is_a_link_is_refused(tmp_path, capsys):
    real = tmp_path / "real-projects"
    (real / (T + "-moreme-eval")).mkdir(parents=True)
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    if make_link(home / ".claude" / "projects", real) is None:
        pytest.skip("cannot create a directory link here")
    out = run(home, "--delete", capsys=capsys)
    assert "error" in out and out["deleted"] == []
    assert (real / (T + "-moreme-eval")).is_dir()
