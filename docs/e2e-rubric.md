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
