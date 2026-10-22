# Proof

Each "done" item from the release goal, with the evidence for it and what was not done.

| Done item | Status | Evidence |
|---|---|---|
| `moreme/SKILL.md` runs end to end in Claude Code: interview, sample, analysis, generated my-voice skill, blind A/B, install | Done, headless on Windows, with one rubric item failed (see evidence) | Reference run [eval/e2e/runs/e2e-20261022-r8/](../eval/e2e/runs/e2e-20261022-r8/): full transcript, manifest, and [rubric record](../eval/e2e/runs/e2e-20261022-r8/rubric-record.md). All six stages ran and the installed skill validated. The clean-room reviewer passed R1 to R9 and failed R10 on one point: a repeated step line at the top of the A/B message, with no hint about which draft was which. The skill was then changed to rule that out. The next run, [e2e-20261022-r9](../eval/e2e/runs/e2e-20261022-r9/rubric-record.md), failed four items because Claude did not show the style report in chat that time, so runs vary. |
| `analyze.py` has pytest tests, handles edge cases, runs on Windows, macOS, and Linux with Python 3.8+ | Done on Windows; macOS and Linux not run | Test results below. Edge cases in `tests/test_encodings_edge_cases.py` include empty and whitespace-only input, one sentence, no punctuation, huge files (streamed), UTF-16 with BOM, Latin-1, UTF-32 and binary files (rejected), control bytes, and missing files. `tests/test_safety_and_views.py` checks that `analyze.py` imports only the standard library and loads no network module. The CI workflow for all three systems (`.github/workflows/ci.yml`) is written and parses, but has not run, because the repo has not been pushed. |
| Eval harness over 3+ personas, with and without the skill, scored with `analyze.py` metrics, results in the README | Done | 6 personas, 240 held-out drafts, all valid. Method frozen before any held-out draft: [eval/PREREGISTRATION.md](../eval/PREREGISTRATION.md). Results: [eval/results/heldout/report.md](../eval/results/heldout/report.md) and the README section "Does it work?". |
| README has a demo, a before/after, and install steps per platform | Done | [README.md](../README.md): demo GIF (rendered from a headless transcript, and labeled that way), before/after pair picked by the pre-registered median rule, install steps for Claude Code in one project, Claude Code in every project (Windows, macOS, and Linux paths), and claude.ai. |
| ChatGPT and Gemini path | Not done (descoped) | Dropped at the owner's request: Claude only for now. The README lists it as future work. |
| Clean git history and a v1.0.0 tag | See the tag | History rewritten before tagging so every commit uses the GitHub noreply identity and no commit holds personal paths or raw logs. Tag `v1.0.0`. |

## Test results

Full suite, local, Windows 11, 2026-10-22:

| Interpreter | pytest | Passed | Skipped | Failed |
|---|---|---|---|---|
| CPython 3.8.20 | 8.3.5 | 537 | 5 | 0 |
| CPython 3.11.9 | 9.1.1 | 538 | 4 | 0 |
| CPython 3.12.10 | 9.1.1 | 538 | 4 | 0 |

Skipped tests:

- `tests/test_perf.py::test_profile_timing` (3 sizes): runs only with `MOREME_PERF=1`. Timings: [docs/test-output/perf.txt](test-output/perf.txt).
- `tests/test_harness_evidence.py`: one check needs raw stream-json logs, which are kept outside the repo.
- Python 3.8 only: `tests/test_ci_workflow.py::test_ci_yaml_parses`, because PyYAML is not installed there.

The suite includes a privacy check on every tracked file (`tests/test_repo_privacy.py`) and a prose check on user-facing text (`tools/check_prose.py`: no long dashes or stock AI phrases).

## Eval table

| | Right writer picked |
|---|---|
| Without the skill | 21% |
| With the skill | 35% |
| Writer's own passages added to every prompt | 52% |

Pre-registered headline: with the skill, a style measure the skill never saw picked the right writer for 35% of drafts, compared with 21% without it (difference 14.6 points, 95% CI 4.2 to 26.0; chance is 17%). The skill was used in 94 of 96 drafts where it was installed. Deviations (a Claude Code update mid-run, a rate-limit check fix, a call budget overrun) and changes made after scoring are listed in the preregistration.

## Generated my-voice skill

[docs/example-run/my-voice/SKILL.md](example-run/my-voice/SKILL.md), written by `analyze.py build-skill` in run `e2e-20261022-r8`. The six persona skills used in the eval are in `eval/skills/`.

## Not verified

- macOS and Linux: CI is written but has not run.
- claude.ai: the install steps follow Anthropic's help pages and were not tried.
- Real users: every run used a simulated writer, so the 12 to 15 minute estimate has not been timed with a person.
