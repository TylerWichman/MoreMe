# Local pytest runs (Windows 11)

Summary of the full local test runs saved on 2026-10-20 at 09:34 to 09:36, one per interpreter. The full console logs list machine paths, so they are kept outside the repo; this page keeps the results.

| Interpreter | pytest | Passed | Skipped | Failed | Time |
|---|---|---|---|---|---|
| CPython 3.8.20 (uv) | 8.3.5 | 223 | 6 | 0 | 62.6 s |
| CPython 3.11.9 | 9.1.1 | 224 | 5 | 0 | 39.8 s |
| CPython 3.12.10 | 9.1.1 | 224 | 5 | 0 | 53.3 s |

Skipped tests, same on every interpreter unless noted:

- `tests/test_perf.py::test_profile_timing` (3 sizes): runs only with `MOREME_PERF=1`. Timings are in `perf.txt`.
- `tests/test_safety_and_views.py::test_forbidden_tokens_absent_from_skill_facing_files` (2 cases): the folders it checks (`docs/example-run`, `eval/skills`) did not exist yet.
- Python 3.8 only: `tests/test_ci_workflow.py::test_ci_yaml_parses`, skipped because the YAML module could not be imported there.

These counts are from before the e2e and privacy tests were added. Later runs are recorded in `docs/PROOF.md`.
