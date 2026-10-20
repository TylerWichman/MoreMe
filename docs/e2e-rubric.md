# MoreMe end-to-end run rubric (v1)

A run passes only if every item R1 to R10 passes. The reviewer is a clean-room agent that sees SKILL.md, this rubric, the transcript, `run-log.md`, and the output folder, and nothing else.

- **R1-R6 Stage exits.** For each stage 1 to 6, `run-log.md` has a `stage=N` line with `status=passed`, and the transcript shows the check named in SKILL.md actually happened (for example, R3: `profile.json` exists with schema_version "1"). `status=degraded` fails R3 in the reference run, which has Python available. `status=skipped` fails.
- **R7 Script calls.** Every analyze.py call exits 0 and no output contains "Traceback". Discovery probes (`--version` on missing candidates) are exempt. `build-skill` reaches `ok: true` within 3 runs, and `my-voice/SKILL.md` and `my-voice.zip` were written only by `build-skill` (no Write or Edit tool call on them, no other zip command).
- **R8 No unexpected tool or permission failures.** Zero tool errors or permission denials, except: (a) Python discovery probes for candidates that do not exist; (b) denials of writes outside the scratch project that the run should never attempt are failures, not exceptions.
- **R9 No unnecessary clarification turns.** Zero assistant turns that ask the user something SKILL.md already answers or that the user already answered (for example, asking which file format to use, asking for the samples again after they were saved, asking whether to run analysis). The five interview questions, at most two allowed follow-ups, the A/B pick, the task for the A/B, the install choice, and (only when `install` reported an existing `my-voice`) whether to replace it are expected questions. The reviewer lists every assistant question and classifies it expected or unnecessary with a one-line reason.
- **R10 Blind A/B integrity (blind to the user).** (a) `ab-mapping.json` is not read or printed by the model before `ab-reveal`. (b) `ab-present` ran, and the assistant's next chat message is the fixed opening line, then the `ab-present` output reprinted verbatim (the reviewer compares the two texts), then the fixed question. (c) Nothing in that message, or between it and the user's pick, hints which draft is which: no mention of length, style, the skill, "with", or "without". Exempt from this check: the fixed opening line required by (b) and the verbatim `ab-present` reprint (the drafts may contain any words). The rule applies to all other text in that message, including the fixed question, and to anything between that message and the user's pick. (d) The "without" draft came from a subagent whose prompt contains only the task text, the shared length/format rule, and "Do not use any skills." (prompt quoted in the transcript). (e) The A/B pick in this run is an LLM's choice and is not evidence of quality. The model wrote the "with" draft, so the A/B is blind to the user, not to the model; (b) and (c) are what keep it blind.

Record: run id, date, CLI version, model id, exact flags, persona id and sample source, per-item pass/fail with transcript line references, reviewer verdict.

## Reviewer note on R9 (orchestrator, 2026-10-20)

The criteria above are copied from the creative brief (FROZEN 6) and do not change. Two more questions that SKILL.md itself requires also count as expected under R9:

- the yes/no question after `install` reports `project_is_home` (switch to the personal folder);
- the "pick up at step N, or start over" question, asked only when `moreme-output/run-log.md` already exists.

Also expected: `run-log.md` `check=` values contain no spaces, and `time=` may be a date only (`YYYY-MM-DD`), because SKILL.md tells the model not to run a command to get the time.

## Chat-visible stage lines (T-011, 2026-10-20)

This note sharpens how R1-R6 are judged. It does not add an item. The R1-R6 criterion "the transcript shows the check named in SKILL.md actually happened" includes the lines SKILL.md tells the model to show the user, so the reviewer checks them where the user would see them.

The user sees only main-thread assistant chat text. In `transcript.md` that is the blocks headed exactly `**Assistant:**`. Text that appears only in `run-log.md`, inside a tool call's input (such as a Write of `run-log.md`), in a tool result, or in a subagent block was never shown to the user and does not count.

For each stage N from 1 to 6, the stage's R item passes only if the chat text shows:

1. the stage's opening line (what happens next and about how long it takes), before the stage's first Write, Edit, Bash, or Agent call;
2. the exact done line `Step N of 6 done: <Name>.`, after the stage's last tool call and before any tool call of the next stage.

Also required: for R2, the running word count of the samples in chat; for R3, the analysis report shown in chat (the content of `report.txt`, not only a Read of it), or the labeled estimate on the no-Python path.

The reviewer records, per stage, the transcript line of the opening line, the done line, and (stages 2 and 3) the shown result. The driver adds a mechanical cross-check to `manifest.json` (`chat_visibility`); the reviewer's judgment decides.

Why: in run `e2e-20261020-r1` the reviewer passed R1-R10 although the done lines for stages 2 and 3, the Step 2 word count, the Step 3 opening line, and the Step 3 report never appeared in chat. They existed only in `run-log.md` and in tool calls, so the user would have seen several minutes of silence. That run's record stays as it was scored; later runs are scored with this note.
