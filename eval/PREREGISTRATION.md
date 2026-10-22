# Eval pre-registration (frozen)

Status: frozen before any held-out text was drafted against or scored. The hash block below says `status: frozen`; the harness refuses held-out drafting and held-out scoring if any listed file's hash differs (`eval/harness/prereg.py`, `require_frozen`). Nothing here changed after the first held-out run started.

## Question

Do drafts written in Claude Code with a persona's generated my-voice skill installed measure closer to that writer than drafts written without it, on style measures the skill never saw?

## Personas and data

- K = 6 personas: `modern-a`, `modern-b` (modern, licensed), `era-c`, `era-d`, `era-e`, `era-f` (public domain in the USA). Sources and licenses: `eval/corpus/PROVENANCE.md`, `eval/corpus/LICENSE-CORPUS.md`.
- Split: whole documents, `eval/split.py` with seed `moreme-eval-split-v1`, recorded in `eval/split.json`. Minimum words per persona: 3,000 train, 1,000 dev, 3,000 held-out (all met).
- Reference statistics: `eval/reference_stats.json`, built from 1,000-word train chunks only.
- Persona run order (modern and era-diverse interleaved): `modern-a`, `era-c`, `modern-b`, `era-d`, `era-e`, `era-f`.
- Degrade rule: if usage limits stop the run, the result set is the first N personas in this order with all their arms and reps complete (N >= 4). Reps, tasks, and arms are never reduced for a persona, and personas are never skipped or reordered after results are seen.

## Skills

Each persona's my-voice skill is produced by the shipped `moreme/SKILL.md`, driven headless by `eval/e2e/run_moreme.py` with a simulated interviewee whose samples are that persona's train split only, in a scratch project that holds train files only. Generated skills are committed under `eval/skills/<persona-id>/`. Interview answers are simulated; this is a disclosed confound.

## Tasks

- 8 held-out tasks per persona (48 in all) in `eval/tasks/tasks.json` (ids `<persona>-heldout-NN`), plus 8 dev tasks per persona used only for the dev smoke and template iterations.
- Each task names a topic and a channel (email, post, note). Topics come from held-out document titles where a title names a topic, else from the persona's register line in `PROVENANCE.md`. No held-out text is read to write a task.
- Prompt template, identical in every arm: `Write {channel_phrase} about {topic}. Aim for about {words} words. Reply with the {noun} only.`
- Target length = median held-out document word count recorded in `eval/split.json`, clamped to 120-400 words. All six personas clamp to 400 words.

## Arms

| Arm | What changes | Reps per task |
|---|---|---|
| `without` | task prompt only | 2 |
| `with` | same prompt; the persona's my-voice skill in the scratch project's `.claude/skills/` | 2 |
| `samples-pasted` | same prompt after 3 fixed train excerpts (150 words each, drawn with seed `moreme-samples-pasted-v1`) | 1 |

- Model: `claude-sonnet-5-5`, passed as `--model` on every call; the model id and Claude Code version reported by each init event are saved per draft.
- Arm order: the 5 units of a task run in an order shuffled with `random.Random("moreme-arm-order-v1:<persona>:<task id>")`, saved in the run manifest.
- Draft units are single-shot `claude -p` calls with `--no-session-persistence` under the AD-006 isolation profile (`eval/lib/childrun.py`).
- Invocation mode: **auto** (unchanged prompt in every arm), decided in Phase 0. Switch check: if the dev smoke's invocation rate for the real generated my-voice is below 80%, the mode becomes explicit before this file is frozen: `with` prompts start with `Use my-voice skill:` and `without` and `samples-pasted` prompts start with the neutral prefix `Please do the task:` (same length). Measured dev rate: 16 of 16 `with` drafts invoked my-voice (100%), dev smoke on persona modern-a, 2026-10-20. That persona's skill was built with the earlier paste-based sample step; the later guided-writing step changes how samples are collected, not how the finished skill is invoked. Mode in force: **auto**.

## Per-call checks (a failed check makes the unit invalid; it is re-run, up to 3 attempts, and counted)

- Init event: `skills` equals `["my-voice"]` in `with` and `[]` otherwise; `plugins` and `mcp_servers` empty; `claude_code_version` 2.1.303; auto-memory not written.
- Tools used by a draft unit are a subset of `{Skill}`.
- Skill invariant: no Skill call other than `my-voice` in `with`, none in the other arms.
- Before each run, no dev or held-out file (by name or content hash) is in the scratch project; draft scratch projects hold only settings and, in `with`, the skill.
- After the runs, no 12-word shingle of any held-out document appears in generated skills, transcripts, or draft prompts.

## Draft extraction (identical for all arms)

1. Take the final assistant text message of the main thread.
2. Drop every line matching the code-fence regex `^\s*(?:```|~~~)`.
3. If the first non-empty line matches the preamble regex below, drop it, and drop one directly following Markdown rule line (`---`, `***`, `___`).
4. Strip surrounding blank space.

Preamble regex (case-insensitive):

```
^\s*(?:(?:sure|okay|ok|certainly|absolutely|of course)[,!.]?\s+)?(?:here(?:'s|’s| is| are)\b|below is\b|i(?:'ve|’ve| have) (?:written|drafted)\b)[^\n]{0,120}[:.]\s*$
```

Invalid units: an empty extracted draft, or a final message matching the fixed refusal and missing-skill regex list `INVALID_PATTERNS` in `eval/lib/childrun.py` (hashed below). Invalid units are logged, re-run, counted against the call budget, and reported.

## Metrics

All distances follow `analyze.py` (brief FROZEN 1 and FROZEN 2). Candidate profiles in the final run are each persona's held-out split.

- **Primary (in force):** nearest-persona attribution accuracy. Each draft is attributed to the persona whose held-out profile has the smallest `delta_fw` (ties by sorted id); correct if it is the target persona; chance = 1/6. Compared `with` vs `without`, paired by task.
- **Fallback primary (not in force):** mean `delta_fw` from each draft to the target persona's held-out profile (lower is closer), `with` vs `without`, paired by task.
- **Secondary, scoring-only:** mean `delta_fw` to target, and `char3_cosine` to target.
- **Secondary, exposed (the skill states these targets, so improvement is expected):** `exposed_distance` to target.
- Descriptive: attribution accuracy of the `without` arm per persona (base rate); `with` vs `samples-pasted`; per-protocol (`with` drafts where the skill was invoked). The primary analysis is intent-to-treat: every valid `with` draft counts.

## Validity gate (run on dev data, before freezing)

Each persona's dev text was cut into consecutive chunks at its target length (400 words) and attributed against train-split profiles with `delta_fw`. Held-out text was not opened. Full result: `eval/results/validity-gate.md` and `.json`.

| Persona | Chunks | Correct | Accuracy |
|---|---|---|---|
| era-c | 10 | 8 | 80.0% |
| era-d | 5 | 2 | 40.0% |
| era-e | 4 | 2 | 50.0% |
| era-f | 4 | 2 | 50.0% |
| modern-a | 5 | 5 | 100.0% |
| modern-b | 7 | 6 | 85.7% |
| Pooled | 35 | 25 | 71.4% |

Pooled accuracy 71.4% is above 2 x chance (33.3%), so attribution stays the primary metric. No persona was attributed below chance (16.7%). Persona-balanced accuracy is 67.6%. Errors lean toward `modern-a` (7 of 10 wrong chunks), which is disclosed as a known bias of the measure.

## Analysis

Unit: the task. Reps of an arm are averaged within a task. Paired difference per task = `with` minus `without`. Pooled estimate = mean over tasks. 95% interval: percentile bootstrap that resamples tasks with replacement within each persona, 10,000 resamples, seed 20261019 (`eval/harness/stats.py`).

Outcome rule for the primary (difference in percentage points): CI above 0 = gain; CI spans 0 = no clear difference; CI below 0 = loss. For the fallback, the change is expressed as a percent of the `without` mean distance, and a CI below 0 (closer) = gain.

## README sentences (verbatim; `eval/harness/report.py` fills the numbers)

Attribution primary:

- Gain: "With the skill, a style measure the skill never saw picked the right writer for {with_pct}% of drafts, compared with {without_pct}% without it (difference {diff} points, 95% CI {lo} to {hi}; chance is {chance_pct}%)."
- No clear difference: "With the skill, a style measure the skill never saw picked the right writer for {with_pct}% of drafts, compared with {without_pct}% without it. The 95% CI for the difference ({lo} to {hi} points) includes zero, so this test found no clear difference."
- Loss: "With the skill, a style measure the skill never saw picked the right writer for {with_pct}% of drafts, compared with {without_pct}% without it (difference {diff} points, 95% CI {lo} to {hi}). On this test the skill made drafts measure less like the writer."

Fallback primary (only if the gate had failed):

- Gain: "Drafts with the skill measured {pct_change}% closer to the writer's own held-out writing on a function-word measure the skill never saw (95% CI {lo}% to {hi}% change in distance)."
- No clear difference: "Drafts with the skill measured {pct_change}% {direction} the writer's own held-out writing on a function-word measure the skill never saw. The 95% CI ({lo}% to {hi}% change in distance) includes zero, so this test found no clear difference."
- Loss: "Drafts with the skill measured {pct_change}% further from the writer's own held-out writing on a function-word measure the skill never saw (95% CI {lo}% to {hi}% change in distance). On this test the skill made drafts measure less like the writer."
- Gate sentence: "Picking the writer from a draft-length chunk of their real text was right only {gate_pct}% of the time, so the eval uses distance to the writer instead."

Disagreement (added right after the headline if a secondary scoring-only metric's CI excludes zero in the direction opposite to the primary estimate): "Other style measures disagree: {metric} moved {direction} ({CI})."

The README headline reports only the primary. Per-persona results are descriptive; the README says the study is underpowered for per-persona conclusions.

## Before/after example (AD-008)

The README pair is taken verbatim from held-out outputs: the task whose paired `delta_fw` improvement (`without` mean minus `with` mean, reps averaged) is closest to the median across all tasks, not the best one; rep 1 of each arm; ties broken by task id.

## Call budget and usage

Pre-registered budget: about 690-710 child calls for the whole project, including persona skill generation and Phase 4/5 child runs. The harness writes every call to an append-only ledger (kept outside the repo, with the raw stream-json logs) and resumes from it; a torn last line is quarantined and its unit re-run. Before each batch it reads the newest `rate_limit_event` and does not start if the seven-day window is at 90% or more.

## Iteration rule

Up to 2 template iterations, judged only on dev-split attribution and `delta_fw`. Every iteration's numbers are kept in `eval/results/iterations/`. Negative results are reported, not dropped.

Iterations actually run: none. The template and SKILL.md were frozen as they stood after the guided-writing change, without tuning on dev results.

## Deviations after freezing

- 2026-10-21, `eval/harness/runner.py`: the pre-batch usage check treated a rejected rate-limit event as permanent, so the run could never resume after a usage limit. It now blocks only until that event's `resetsAt` time. This changes when a batch may start, not prompts, arms, draft extraction, scoring, or analysis. Persona modern-a's 40 held-out drafts were made before this change; the rest after. The runner.py hash below was refreshed for this change only.
- 2026-10-21, Claude Code auto-updated from 2.1.303 to 2.1.306 mid-run (the main install, not the child runs, which had auto-update off). The per-call check correctly rejected every later call, but the harness retried each one up to three times, spending about 230 calls without producing a draft. Changes: `eval/lib/childrun.py` reads the expected version from `MOREME_CLI_VERSION` (default 2.1.303), `eval/harness/runner.py` halts the batch on the first version mismatch instead of retrying, and `eval/harness/ledger.py` plus a `harness reopen` command append "reopen" rows so units that failed only on the version check run again (nothing is deleted from the ledger). The rest of the run uses Claude Code 2.1.306 with the same pinned model (`claude-sonnet-5-5`). The 32 valid modern-a drafts made on 2.1.303 are kept; every draft record and ledger row records the version that made it. No prompts, arms, extraction, scoring, or analysis changed.
- 2026-10-22, call budget: the held-out run used 475 calls for 240 units (all valid), and the whole project about 920 child calls (ledgers: 40 spike, 73 dev smoke, 336 end-to-end and persona skill generation, 475 held-out), against the planned 690-710. The overrun is the version-retry loss above plus end-to-end reruns for the turn-boundary and privacy fixes.

## Hashes

Files whose sha256 (line endings normalized to LF) must match before held-out scoring. Refreshed with `python -m harness prereg write-hashes` from `eval/`; frozen with `python -m harness prereg freeze`.

<!-- prereg-hashes:start -->
```
status: frozen
8f5bab84651b34213256a3b67cdf8e6ac131936a69b169fede35fd9a823baccd  moreme/SKILL.md
27bf967ffff45f0d4237def7f6f0e82eb635492e5ea9693aa10c3a09bfa8d9cd  moreme/templates/my-voice/SKILL.md.tmpl
29cbb05b9d63e53adf8679f87f8fed686cfefadec98a739e83086340f2e987c1  moreme/analyze.py
c97b54bf03279a7e26a025b72cca81180690eb46fbecf922eafbb20df3d3b136  eval/reference_stats.json
d4a2eb7f0bb23b3db3d175438d97242c02e2c23153430714f8b2363c4756de49  eval/split.json
b09442528547b65eb4ebc66cab28d50e8cb31b59b0d33dfae2acb41b6b996a27  eval/tasks/tasks.json
8c098d2e4441ceaec8e4cb4e5180f02604236eec811494ef87316a082c2d3cb5  eval/lib/childrun.py
2a5bf354a57bb402f3841f2b5ae896752c286c0657a7adbf2862b8fbe8de43e0  eval/harness/__init__.py
724935045d07bed153b9fcc10c5789d761195de627d99e3581182f8fa5baf895  eval/harness/__main__.py
ed8db316735ae1ceaf8c4988ee69139eb773357ca5d1926ca38f425a5d0874cc  eval/harness/common.py
ccf2783bf66c693713226b68cd0a7c15a4541ec1796d8933c312aded4b608074  eval/harness/evidence.py
bdd768f5d1d239b17769bdbde564fd41a0f3d2048605f4223ce39421d56403eb  eval/harness/extraction.py
d247facc05f4624ea006aa04a1c86e7c0465d0819b218c1646860f4a80d06aa6  eval/harness/leakage.py
62d02480668a89fd30cfdf6670ae4e76408f04cf169e98627f8af6415a51ebcd  eval/harness/ledger.py
03784699892832c09d3102f1c30369bf25a77d6351178b97a5b54774ab18fef6  eval/harness/prereg.py
eb75d24bd4eb2e377e99180f50ef00a422c2c0146287fe65e61ed84f45c2278b  eval/harness/report.py
729480dd85ad15c0c3ada4276e4c7fd06810e7b7ee4f967e11b3ea6d07ab5cbe  eval/harness/runner.py
b016e5ef1edb7f78e7fcd8064949525a6cdd68b05a753ead87d3bbd41bb87154  eval/harness/scoring.py
3d9db0f72c9537e3f375b666c584ed8968baf70cd3d320d67decda6490156292  eval/harness/stats.py
e9c9cd308670d27f8890fc54d268bb849dc12fca10e8ac3c2dd255dae64b0bee  eval/harness/tasks.py
0db98a81a11663c4a7b3b07f8d6a2182fe8ed996e34a771ef465ecc6d64dd01c  eval/harness/validity.py
```
<!-- prereg-hashes:end -->
