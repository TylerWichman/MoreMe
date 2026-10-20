# Blind A/B (Step 5)

The user reads two drafts of the same message and picks the one that sounds more like them. One draft used my-voice and one did not. A script decides which one is A and which is B, and keeps that hidden until the user picks.

The test is blind to the user, not to Claude: Claude wrote the "with" draft and could recognize it. That is why the wording of the A/B message is fixed and nothing else may be said until the pick.

## Picking the task

Ask for a short real message the user needs to write soon. Offer two or three suggestions based on interview question 1, for example:

- Emails: "An email to a coworker asking to move Thursday's meeting to Friday."
- Posts: "A short post saying you finished a course and what you learned."
- Cover letters: "The opening paragraph of a cover letter for a job you want."
- Messages: "A text to a friend saying you'll be 20 minutes late."

If the user names none or says "you pick", use the first suggestion. Save the task text exactly as given (or the suggestion you used) to `moreme-output/ab-task.md`.

## The shared rule

Both drafts get exactly this rule:

```
Write only the message itself, as plain text. No title, no notes before or after it, no Markdown. Keep it under 150 words unless the task says otherwise.
```

## The "without" draft (subagent)

Start a subagent with the Task or Agent tool (a general-purpose agent). Its prompt is exactly:

```
<task text from ab-task.md>

Write only the message itself, as plain text. No title, no notes before or after it, no Markdown. Keep it under 150 words unless the task says otherwise.

Do not use any skills.
```

Nothing else goes in the prompt: no interview answers, no samples, no report, no voice notes, no mention of MoreMe or my-voice. "Do not use any skills." matters because the user may already have a my-voice skill installed from an earlier run.

Save the subagent's reply to `moreme-output/draft-without.md` unchanged. If it added a line like "Here's the draft:" before the message, remove only that line.

## The "with" draft

Read `moreme-output/my-voice/SKILL.md`, then write the task as the user, following that skill and the shared rule. Save it to `moreme-output/draft-with.md`.

## Shuffle and show

```
PREFIX ab-shuffle --out moreme-output
PREFIX ab-present moreme-output
```

`ab-shuffle` picks the labels at random and saves them in `ab-mapping.json`. It prints only `{"labels": ["A", "B"], ...}`. Never open, read, Glob for, or print `ab-mapping.json` before the pick.

While you work, say only something like "Writing two drafts now. This takes about a minute." Do not say which draft you are writing.

## The A/B message (fixed)

Your next chat message after `ab-present` is exactly three parts and nothing else:

```
Here are two drafts of the same message. One used your new voice skill and one didn't.

<the full ab-present output, reprinted word for word: the line "Draft A", a blank line, draft A, a blank line, the line "Draft B", a blank line, draft B>

Which sounds more like you? Type A or B.
```

- Claude Code may collapse command output, so the user only reads what you reprint. Reprint all of it.
- No notes on length, tone, style, the skill, "with", or "without". No "take your time", no hints, no follow-up text.
- If the user replies with anything other than A or B (a question, "both", "neither"), answer only: "Type A or B." If they then decline to pick, log `status=skipped reason=no_pick` and go to Step 6.

## Reveal

```
PREFIX ab-reveal moreme-output --pick A
```

(or `--pick B`). It saves `ab-result.json` and prints which draft was which. Give a one-line result:

- Picked the "with" draft: "You picked A. Draft A was the one written with your voice skill."
- Picked the other one: "You picked B. Draft B was written without your voice skill. Close results are common with short messages."

After the reveal you may answer questions about the drafts. Do not argue with the pick.

## When it cannot be fully blind

Say it in one sentence, before showing the drafts, then still show both drafts labeled A and B and ask the same question.

- **No subagent** (the Task or Agent tool is not available): "This comparison is not fully blind, because I have to write both drafts myself in this chat." Write the "without" draft first, from the task text and the shared rule only, before reading `my-voice/SKILL.md` again. Then use `ab-shuffle`, `ab-present`, and `ab-reveal` as usual. Log `status=degraded reason=not_blind_no_subagent`.
- **No Python** (Step 3 was degraded): "This comparison is not fully blind, because without Python there is no script to hide which draft is which." Show the "without" draft as A and the "with" draft as B, and reveal after the pick. Log `status=degraded reason=not_blind_no_python`. Write the result to `moreme-output/ab-result-estimated.md`.

## Running the A/B again

`ab-reveal` refuses to run twice in the same folder, so an earlier result is never overwritten. If `moreme-output/ab-result.json` already exists (Glob for it before Step 5), use a new folder `moreme-output/ab-run-2/` (then `ab-run-3/`) for `ab-task.md`, `draft-with.md`, `draft-without.md`, and all three `ab-` commands, for example `PREFIX ab-shuffle --out moreme-output/ab-run-2`.
