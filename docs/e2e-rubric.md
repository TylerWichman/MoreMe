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

For each stage N from 1 to 6, the stage's R item passes only if the chat text shows, no later than the next assistant message that asks the user to act (the message that ends the assistant's turn and waits for a reply):

1. the stage's opening line (what happens next and about how long it takes). For Step 1 this is the introduction, which must be in the first message the user sees, the one with question 1;
2. the exact done line `Step N of 6 done: <Name>.`, after the stage's work. A done line that first appears after the user has replied to a later message is late and fails.

Also required: for R2, the running word count of the samples in chat; for R3, the analysis report shown in chat (the content of `report.txt`, not only a Read of it), or the labeled estimate on the no-Python path, before any Step 4 tool call.

Tool calls may run before these lines inside a turn. What counts is what the user has seen by the time they are asked to do something.

Expected questions under R9 also include the Step 3 check-in ("Does this sound like you? Reply yes, or tell me what's off.") and the resume question asked after the user's first answer when `moreme-output/run-log.md` already exists.

The reviewer records, per stage, the transcript line of the opening line, the done line, and (stages 2 and 3) the shown result. The driver adds a mechanical cross-check to `manifest.json` (`chat_visibility`); the reviewer's judgment decides.

Why: in run `e2e-20261020-r1` the reviewer passed R1-R10 although the done lines for stages 2 and 3, the Step 2 word count, the Step 3 opening line, and the Step 3 report never appeared in chat. They existed only in `run-log.md` and in tool calls, so the user would have seen several minutes of silence. That run's record stays as it was scored; later runs are scored with this note.

Revision (2026-10-20, decision `2026-10-20-turn-boundaries-for-visibility-moreme`): the first version of this note required each opening line before the stage's first tool call and each done line before the next stage's first tool call. Runs r2 and r3 showed the model writes chat text when it needs a reply and chains tool calls silently otherwise, whatever SKILL.md says. SKILL.md now puts the visible moments in messages that end a turn (a tool-free first turn; Step 3 ends with the report and a check-in question), and this note judges what the user has seen by the time they are asked to act. Strict tool-versus-text order inside one turn was a stand-in for that experience, not the experience itself. Runs r2 and r3 keep their records as scored.

R10(d) reading: "the shared length/format rule" means the whole shared rule quoted in SKILL.md Step 5, including its closing sentences about never taking a name from a username, a file path, or system details. Those sentences are part of the rule, not extra content.

## Guided writing sample (AMEND-003, T-015, 2026-10-20)

Since AMEND-003, MoreMe does not ask the user to paste or point to existing writing. Step 2 collects the sample as a guided writing conversation, and the five interview answers count toward it. The reviewer applies R1-R10 to this flow as follows.

- **No paste step.** Any request to paste text, attach a file, or point to a file path is an unnecessary question under R9, and a Read of a file the user did not type in this chat is a finding under R8.
- **Prompt loop.** After the interview, MoreMe asks writing prompts, one per message, each following from the user's previous answer, until the user's own typed words reach about 300 (interview answers included). Each such prompt is an expected question under R9. A prompt asked after the running total already passed about 300 words is unnecessary.
- **Progress cue.** A running word count shown in chat during Step 2 (for example "about 120 of 300 words so far") is the Step 2 word count required by R2 under the chat-visibility note.
- **Short answers.** A prompt that invites a longer answer after a very short one is expected; scolding the user is not.
- **Stop early.** If the user asks to stop before the target, one sentence saying that fewer words make the measurement less reliable is expected, and Step 2 may finish with what the user wrote and `status=degraded` with a reason. In the reference run the simulated user is told to keep writing, so a degraded Step 2 there fails R2; for real users it is a valid path.
- **Simulated user.** In e2e runs the simulated interviewee answers each writing prompt with verbatim passages of the persona's train-split texts, chosen to fit the prompt (whole paragraphs or whole sentences, never reworded), and answers interview questions in role. The transcript banner says so. How well a passage fits a prompt is not judged; the A/B pick and the passages' fit are agent choices, not evidence of quality. Interview answers in role are kept to about 15 words each and writing answers are single passages of 60 to 100 words, so the sample is mostly real writing.
- **Sample composition (run validity).** `manifest.json` records `sample_composition`: words the simulated user typed before the Step 2 done line, split into verbatim corpus passages and role-played answers. A run counts as a reference run only if corpus words are at least 75% of that total; a run below that is reported but not used as evidence, whatever its R1-R10 result. Added after r5, where role-played interview answers made up most of the sample.

Why: the operator changed how the sample is collected (AMEND-003: get users writing about things and adapt each prompt to their previous answer). The prompt loop is the core of the new Step 2, so its questions cannot count against R9.
