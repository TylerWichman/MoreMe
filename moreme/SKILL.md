---
name: moreme
description: Builds a personal writing-voice skill called my-voice from the user's own writing. It asks five short questions, reads three or more things the user wrote, measures their style with a small local Python script, writes the my-voice skill, shows a blind A/B of two drafts, and helps install it. Use it when the user asks to make Claude write like them, sound more like them, learn their writing style or voice, or create a voice skill.
allowed-tools: Bash(python --version), Bash(py -3 --version), Bash(python3 --version), Bash(python .claude/skills/moreme/analyze.py:*), Bash(py -3 .claude/skills/moreme/analyze.py:*), Bash(python3 .claude/skills/moreme/analyze.py:*), Bash(python ~/.claude/skills/moreme/analyze.py:*), Bash(py -3 ~/.claude/skills/moreme/analyze.py:*), Bash(python3 ~/.claude/skills/moreme/analyze.py:*), Write(moreme-output/**), Edit(moreme-output/**)
---

# MoreMe

MoreMe walks the user through six steps in about 10 minutes and leaves them with a skill called my-voice. Follow the steps in order. Do not skip, merge, or reorder them.

## Show every step in chat (required)

The user sees only your chat text; tool calls and their output are hidden or collapsed. Put what the user must see in the message that ends your turn (the one that asks them to act):

1. **Step lines.** Each step's opening line (the "Say" line at the top of each step) and its done line `Step N of 6 done: <Name>.` appear in chat no later than the next message that asks the user to act. Earlier, before the step's tool calls, is better.
2. **Where they land at the latest.** Step 1: opening in the first message, done line in the message asking for samples. Steps 2 and 3: in the Step 3 report message, which ends with the check-in question. Step 4: in the message asking for the A/B task. Step 5: in or before the install question. Step 6: in the closing message.
3. **Results in chat.** Step 2's word count and Step 3's full report go in your chat text. Reading a file does not show it to the user.

These lines are updates, not extra questions. Ask only the questions this file lists.

## How to talk to the user

- Plain, short sentences. Second person ("Paste three things you wrote"). No jargon.
- No long dashes (the U+2014 character). Use commas, periods, colons, or parentheses.
- No hype and no exclamation marks. Do not praise the user's writing.
- Ask one question per message. Never ask something this file already answers: where to save files, which file format to use, whether to run the script, whether to continue to the next step.
- Never show scoring details from the eval or any number the report does not show.

## Ground rules

- **Output folder:** always `moreme-output/` in the current project folder. Do not ask where to save. All files below live in it.
- **Working folder:** run every command from the project folder. Never use `cd`. Always pass paths that start with `moreme-output/`.
- **Saving files:** use the Write tool for new files and Write or Edit for changes. Never use Bash to write, copy, move, or delete files.
- **Skill files:** `my-voice/SKILL.md` and `my-voice.zip` are made only by `analyze.py build-skill`. Never write, edit, or zip them yourself (except the no-Python path in Step 4).
- **Checking whether a file exists:** use Glob, not Read, so a missing file is not an error.
- **The user's name:** never take it from a username, a file or folder path, the environment, or other system details. Use a name only if the user gave it in the interview or this chat, or signed their samples with it. Otherwise sign drafts with their usual sign-off and no name, or leave them unsigned.
- **Earlier run:** right after the user's first answer (never before it), Glob for `moreme-output/run-log.md`. If it exists, read it and follow "Picking up an earlier run" in `reference/troubleshooting.md`. If not, go on with Step 1.

### Stage exit lines

Every step ends with two things, in this order:

1. A new last line in `moreme-output/run-log.md` (Write it again with all earlier lines, or use Edit).
2. Then a chat line, exactly: `Step N of 6 done: <Name>.` The names are Interview, Sample, Analysis, Generate, Blind A/B, Install.

The run-log line:

```
stage=N name=<name> status=passed check=<what was checked> time=<time>
```

- `<name>` is one of: `interview`, `sample`, `analysis`, `generate`, `blind-ab`, `install`.
- `status` is `passed`, or `degraded reason=<reason>`, or `skipped reason=<reason>`. Reasons and checks use no spaces (use `_`).
- `<time>` is the current local date and time as `YYYY-MM-DDTHH:MM` if you know it, else the date as `YYYY-MM-DD`. Do not run a command to get it.

### The script command (PREFIX)

Steps 3 to 6 call `analyze.py`, a small Python script in this skill's folder (Claude Code shows the folder when the skill starts).

- In the current project's `.claude/skills/moreme`: SKILL_DIR is `.claude/skills/moreme`.
- In the personal skills folder (in your home folder): SKILL_DIR is `~/.claude/skills/moreme`.
- On claude.ai or anywhere else: SKILL_DIR is the full folder path you were given.

In Claude Code, write SKILL_DIR exactly in one of the first two forms, with forward slashes, never as a full `C:\...` or `/Users/...` path, so MoreMe's permission rules match and the user sees fewer prompts.

PREFIX is the Python command found in Step 3 plus `SKILL_DIR/analyze.py`, for example `python .claude/skills/moreme/analyze.py`. Use the exact same PREFIX for every later call.

## Step 1 of 6: Interview (about 3 minutes)

1. **First reply: no tools at all.** It is one message, in this order: in your own plain words, MoreMe asks five short questions, reads a few things the user wrote, measures their style, and makes a skill called my-voice, in about 10 minutes; then the permissions sentence below, word for word; then question 1 (item 3). End your turn there.

   In Claude Code:

   > Claude Code may ask your permission a few times while MoreMe works. It may ask before saving files in a folder called moreme-output. It may also ask before running a small measuring script that came with MoreMe. Choose Yes. The script works only with your MoreMe files and sends nothing over the internet.

   On claude.ai:

   > Claude will run a small measuring script that came with MoreMe. It runs in Claude's sandbox, not on your computer. Your samples go there under Anthropic's terms.

2. **After the user's first answer:** Glob for an earlier run (Ground rules). Then Write `moreme-output/.gitignore` with the single line `*` (keeps samples out of git), before saving anything else. Then ask question 2.
3. Ask these five questions, one per message, in this order. Keep the wording close to this:
   1. "What do you mostly use AI to help you write? For example emails, posts, or cover letters."
   2. "Who usually reads it?"
   3. "Pick three words for how you want to sound."
   4. "What bugs you most in drafts AI writes for you? Words, phrases, or habits."
   5. "Any habits you always or never have? For example sign-offs, emoji, or exclamation marks."
4. Follow-ups: at most 2 in the whole interview, and only when an answer is empty or contradicts another answer. Otherwise accept the answer as given. Details and examples: `reference/interview-guide.md`.
5. After the last answer, Write `moreme-output/interview.md` with each question and the user's answer copied word for word (format in the interview guide).

**Exit check:** 5 answers saved in `interview.md`, follow-ups 2 or fewer. Log it, for example `stage=1 name=interview status=passed check=answers=5,followups=0 time=...`. Then write `Step 1 of 6 done: Interview.` as chat text.

## Step 2 of 6: Sample (about 2 minutes)

1. Say: "Next, paste three or more things you wrote yourself, like emails or posts. This takes about 2 minutes." In Claude Code, add that they can give file paths instead. They can paste one piece per message, or all at once with `---` on a line between pieces.
2. Save each piece exactly as written to `moreme-output/samples/sample-01.txt`, `sample-02.txt`, and so on. Do not fix typos, spacing, or punctuation. For file paths, Read the file and save its text the same way. For files you cannot read (like Word), ask the user to paste the text.
3. After saving each paste (or all the files the user named), write the running count as chat text: "That's 2 pieces and about 450 words so far." Count words yourself; an estimate is fine here.
4. If a piece is clearly not the user's own writing (a news article, a form letter), ask once whether they wrote it. If they say yes, keep it.
5. **Floor: 3 pieces and 300 words in total.**
   - Below the floor: say how many more words or pieces are needed and ask once more, for example: "That's 210 words so far. MoreMe needs at least 300. Can you paste one or two more?"
   - Still below after that: offer "continue with rough numbers". If they agree, continue and log `status=degraded reason=below_floor`. If they would rather stop, see "If the user wants to stop".
   - Between 300 and 1,000 words: continue, and say once that the numbers will be rough.

**Exit check:** 3 or more files in `samples/`, word total logged. Log it, for example `stage=2 name=sample status=passed check=files=3,words_about=1200 time=...`. Then write `Step 2 of 6 done: Sample.` as chat text.

## Step 3 of 6: Analysis (about 1 minute)

1. Say exactly: "Next, MoreMe's measuring script reads your samples. If Claude Code asks, choose Yes." (On claude.ai, leave out the second sentence.)
2. **Find Python.** Run these probes one at a time, in this order. Stop at the first one that works:
   1. `python --version`
   2. `py -3 --version`
   3. `python3 --version`, only if both of the others failed.

   A probe works only if its output shows `Python 3.8` or higher. Empty output, an error, a message about the Microsoft Store, or Python 2 or 3.7 and older all count as failed. Do not install anything or try any other command.
3. **Confirm.** Run `<probe command without --version> SKILL_DIR/analyze.py --version`. It must exit 0 and print JSON with `"schema_version": "1"`. If it fails, go back and try the next probe. This command, minus `--version`, is PREFIX.
4. **Measure.** List every sample file by name:

   ```
   PREFIX profile moreme-output/samples/sample-01.txt moreme-output/samples/sample-02.txt moreme-output/samples/sample-03.txt --out moreme-output/profile.json
   PREFIX report moreme-output/profile.json --out moreme-output/report.txt
   ```

5. Read `moreme-output/report.txt`. Then log Step 3 in `run-log.md` (exit check below).
6. **Report message (ends your turn),** in this order:
   - `Step 2 of 6 done: Sample.` and this step's opening line, if not written yet
   - the line: Here is what MoreMe measured in your writing:
   - the full text of `report.txt`, copied word for word (the user cannot see what Read returns)
   - one or two plain sentences tying it to their interview answers (if the report says there was very little text, say again that the numbers are rough)
   - `Step 3 of 6 done: Analysis.`
   - the question: Does this sound like you? Reply yes, or tell me what's off.

   Then stop and wait for the reply. No Step 4 tool call before it.
7. **Save the answer.** Add it to the end of `moreme-output/interview.md` under `## Check-in after the report`, word for word. Accept it as given, with no follow-up. Step 4 uses it.

**If no probe works or the version is too old:** say so in one sentence and follow "No-Python estimate" in `reference/samples-and-analysis.md`: you write `report.txt` yourself, labeled estimated by Claude, not measured, and show it in the item 6 message. Log `status=degraded reason=no_python`. Steps 4 and 5 then use their no-Python paths.

**If analyze.py exits 2:** it prints one line saying what is wrong (for example a file that is not text). Tell the user in plain words, fix that one thing (usually: ask them to paste that piece as text and save it again), and run the command once more. Exit 1 or a second failure: see `reference/troubleshooting.md`.

**Exit check:** `profile.json` exists, the command exited 0, and its `schema_version` is "1" (or the degraded path is labeled). Log it before the report message, for example `stage=3 name=analysis status=passed check=profile_json_schema_1,words=1180 time=...`. The done line goes in the report message (item 6).

## Step 4 of 6: Generate (about 1 minute)

1. Say: "Next, I'll write your my-voice skill from your answers, your samples, and the numbers. This takes about a minute."
2. Write `moreme-output/voice-notes.md` with exactly these six headings, in this order, and nothing important outside them:

   ```
   ## How I sound
   ## Do
   ## Don't
   ## Avoid words
   ## Examples
   ## Adjust by channel
   ```

   Read `reference/voice-notes-guide.md` (counts, wording, copying excerpts exactly) before writing. Counts: 3 to 5 sentences; 5 to 8 and 3 to 6 "- " lines; question 4's pet peeves, one per line; 3 to 5 excerpts (`[sample-NN.txt]`, then 40 to 120 words copied exactly); `Email:`, `Post:`, `Cover letter:` lines of 1 to 3 sentences. No long dashes or hype words in your own text. If the Step 3 check-in says something is off, reflect it in How I sound, Do, or Don't; never change the measured numbers.
3. Run:

   ```
   PREFIX build-skill moreme-output/profile.json moreme-output/voice-notes.md --samples moreme-output/samples --out moreme-output
   ```

4. Read the JSON it prints. `"ok": true` means it wrote `my-voice/SKILL.md` and `my-voice.zip`. If `"ok": false`, fix `voice-notes.md` using the listed errors (codes in the guide) and run `build-skill` again. At most 3 runs in total, without asking the user. After the third failed run, show the errors in plain words and see `reference/troubleshooting.md`.
5. In the message that asks for the A/B task (Step 5), tell the user in two or three sentences what the skill says about them (for example their typical sentence length and two Do rules). Do not paste the whole file.

**No-Python path (Step 3 was degraded):** write `moreme-output/my-voice/SKILL.md` yourself from `SKILL_DIR/templates/my-voice/SKILL.md.tmpl`, as `reference/voice-notes-guide.md` describes. Tell the user there is no zip file this time. Log `status=degraded reason=no_python`.

**Exit check:** `build-skill` printed `"ok": true`, and `my-voice/SKILL.md` and `my-voice.zip` exist. Log it, for example `stage=4 name=generate status=passed check=build_skill_ok,runs=1 time=...`. Then write `Step 4 of 6 done: Generate.` as chat text, at the latest at the top of the A/B task message.

## Step 5 of 6: Blind A/B (about 2 minutes)

This step shows the user two drafts of the same message, one written with my-voice and one without, and they pick the one that sounds more like them. Full details: `reference/blind-ab.md`.

1. In the same message as the Step 4 done line and summary, say: "Next, a quick test. I'll write the same short message two ways, and you pick the one that sounds more like you. This takes about 2 minutes." Then ask for a short real message they need to write, and offer two or three suggestions based on their interview answers. If they name none, use the first suggestion.
2. Write the task text, as the user gave it, to `moreme-output/ab-task.md`. (If `moreme-output/ab-result.json` already exists, use `moreme-output/ab-run-2/`; see `reference/blind-ab.md`.)
3. The shared rule for both drafts (use the same words in both): "Write only the message itself, as plain text. No title, no notes before or after it, no Markdown. Keep it under 150 words unless the task says otherwise. Never take a name from a username, a file path, or system details. If you do not know the writer's name, sign off without one."
4. **"Without" draft.** Start a subagent (the Task or Agent tool). Its whole prompt is the task text, a blank line, the shared rule, a blank line, and `Do not use any skills.` Nothing else: no interview answers, no samples, no voice notes. Save its reply, unchanged, to `moreme-output/draft-without.md`.
5. **"With" draft.** Read `moreme-output/my-voice/SKILL.md` and write the same task as the user, following that file and the shared rule. Sign with a name only as "The user's name" in Ground rules allows. Save it to `moreme-output/draft-with.md`.
6. Run, in this order:

   ```
   PREFIX ab-shuffle --out moreme-output
   PREFIX ab-present moreme-output
   ```

   Never open, read, or print `ab-mapping.json`. The script keeps the labels hidden until the user picks.
7. **Your next chat message is exactly this and nothing else:**
   - the line: Here are two drafts of the same message. One used your new voice skill and one didn't.
   - the full `ab-present` output, reprinted word for word (command output may be hidden, so the user only sees what you reprint)
   - the line: Which sounds more like you? Type A or B.

   Do not add anything about length, style, the skill, "with", or "without", in that message or before the user picks. If they reply with something other than A or B, answer only: "Type A or B."
8. After they pick, run `PREFIX ab-reveal moreme-output --pick A` (or `--pick B`). Read the JSON and give a one-line result, for example: "You picked A. Draft A was the one written with your voice skill." If they picked the other draft, say so plainly, and add that close results are common with short messages.

**When it cannot be fully blind:** if you cannot start a subagent, or there is no Python, say in one sentence that this comparison is not fully blind and why, then follow `reference/blind-ab.md`. Log `status=degraded reason=not_blind_no_subagent` or `reason=not_blind_no_python`.

**If the user does not want the test:** do not push. Log `status=skipped reason=user_declined` and go to Step 6.

**Exit check:** `ab-result.json` exists, or the not-blind sentence was shown and logged. Log it, for example `stage=5 name=blind-ab status=passed check=ab_result_json,picked_arm=with time=...`. Then write `Step 5 of 6 done: Blind A/B.` as chat text.

## Step 6 of 6: Install (about 1 minute)

1. Say: "Last step: putting my-voice where Claude can find it. This takes about a minute."
2. **In Claude Code,** show this line first, word for word: "Project folder: my-voice works only in this project. Personal folder: it works in every project." Then ask which one they want (project folder is the default), and mention they can also upload it to claude.ai.
3. Run the command for their choice:
   - Project folder: `PREFIX install moreme-output/my-voice`
   - Personal folder: `PREFIX install moreme-output/my-voice --personal`
4. Read the JSON it prints:
   - `"ok": true`: Glob for `SKILL.md` in the `installed` folder to confirm it.
   - `"reason": "project_is_home"`: do not stop or retry the same command. Say: "Claude Code is open in your home folder, so this project folder is also your personal skills folder. Choose the personal folder instead, and my-voice will work in every project." If they say yes, run the `--personal` command.
   - Exit 2, already installed: ask once, "You already have a my-voice skill there. Replace it with the new one?" On yes, add `--replace`. On no, say the new skill stays in `moreme-output/my-voice/`.
   - Any other exit 2: give the one-line reason in plain words. Do not copy the files another way. Offer the steps in `reference/install.md`.
5. **On claude.ai, or if they choose it:** give the upload steps from `reference/install.md` and offer `my-voice.zip` as a file to download. Say in one sentence that these steps come from Anthropic's help pages, untested by MoreMe's author.
6. Tell them how to check it works ("How to check it works" in `reference/install.md`).

**Exit check:** the chosen route is logged; for either Claude Code route, `install` printed `"ok": true` and the installed `SKILL.md` exists. Log it, for example `stage=6 name=install status=passed check=install_ok,route=project time=...` (`route=project`, `route=personal`, `route=claude-ai`, or `route=manual`). Then write `Step 6 of 6 done: Install.` as chat text.

Then close in two or three sentences: where their files are (`moreme-output/`, which git ignores), that they can run MoreMe again any time with new samples, and nothing more.

## If the user wants to stop

At any point, if the user says stop, cancel, or later: stop at once. Say in one or two sentences what is saved in `moreme-output/` and that they can pick up later by saying "I'd like to make my voice skill". Log `status=skipped reason=user_stopped` for the current step. Do not argue or ask again.

## Reference files

In SKILL_DIR/reference/. Read one when a step points to it: `interview-guide.md`, `samples-and-analysis.md`, `metrics-glossary.md` (every report number in plain words), `voice-notes-guide.md`, `blind-ab.md`, `install.md`, `troubleshooting.md` (every failure path and what to say).
