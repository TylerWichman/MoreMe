# Troubleshooting

What to do when something goes wrong. Always tell the user in one or two plain sentences, then act. Never put a long error or a traceback into the chat.

## analyze.py results

| Result | Meaning | What to do |
|---|---|---|
| Exit 0 | Worked | Continue |
| Exit 2 | Bad input. One line on the error output says what | Tell the user in plain words, fix that one thing, run once more |
| Exit 1 | The script hit an internal problem | Run the same command once more. If it fails again, take the step's degraded path and say so |
| Command not found, or a Python error before any JSON | Wrong PREFIX | Repeat Python discovery from Step 3 once |

Common exit 2 messages:

- **"This looks like a binary file, not text"** or **"UTF-32 text is not supported"**: `conversation.txt` was not saved as plain text. Write it again from the user's answers in the chat and rerun `profile`.
- **A file or folder is missing:** check the path starts with `moreme-output/` and the file was saved. Save it, then rerun.
- **install: my-voice already exists:** ask once whether to replace it (see `install.md`).
- **install: a safety guard message:** this happens only in automated test setups. Tell the user the install was blocked by a safety setting and offer the manual steps in `install.md`. Do not try another way to copy the files.
- **ab-reveal: a result already exists:** use a new A/B folder (see "Running the A/B again" in `blind-ab.md`).

## By step

### Step 1

- The user answers several questions at once: count them as answered and skip ahead.
- The user asks what MoreMe does with their writing: in Claude Code, "Your answers are saved in a folder called moreme-output on your computer, and git ignores it. The measuring script runs on your computer and sends nothing over the internet. Claude sees what you type here, under Anthropic's terms." On claude.ai, use the claude.ai permissions sentence.

### Step 2

- Still under about 300 words after 10 questions: continue with what you have and log `status=degraded reason=below_floor`.
- The user wants to stop writing early: one sentence that fewer words make the measurement less reliable, offer one more question, then continue if they still want to stop (`status=degraded reason=user_stopped_early`).
- The user offers to paste existing writing or a file: thank them and say MoreMe measures how they type here, then ask the next question.
- Answers stay very short: offer a different opener, and keep questions concrete and easy ("What did you have for lunch, and was it good?"). Never scold.

### Step 3

- No Python, or Python older than 3.8: one sentence, then the estimate path (`samples-and-analysis.md`). Log `status=degraded reason=no_python`.
- `profile` warns about very little text: repeat that the numbers are rough, then continue.
- `profile` exits 1 twice: say "The measuring script hit a problem, so I'll estimate your style by reading your samples instead." Take the no-Python path for Steps 3 to 5. Log `status=degraded reason=analyze_error`.

### Step 4

- `build-skill` still fails after 3 runs: show the remaining errors in plain words, for example "One of the example passages didn't match your sample exactly." Then offer two choices: try once more with different excerpts, or stop here with the notes saved. Log `status=degraded reason=build_skill_failed` if they stop. Never write `my-voice/SKILL.md` by hand when Python works.

### Step 5

- The Task or Agent tool is not available: use the not-blind path in `blind-ab.md`.
- The user does not want the test: log `status=skipped reason=user_declined` and go to Step 6.

### Step 6

- The user does not use Claude Code or claude.ai: give the manual steps in `install.md`, log `route=manual`.
- The user is unsure which folder: suggest the project folder. They can run MoreMe again later and pick the personal folder.

## If the user wants to stop

Stop at once. Say what is saved, for example: "Your answers and samples are saved in moreme-output. Say "I'd like to make my voice skill" any time to pick up where you left off." Log `status=skipped reason=user_stopped` for the current step. Do not ask them to reconsider.

## Picking up an earlier run

Right after the user's first interview answer (the first reply uses no tools), Glob for `moreme-output/run-log.md`. If it exists:

1. Read it. Find the last step with `status=passed` (or `degraded`).
2. Tell the user in one sentence which steps are done, and ask once: "Pick up at step N, or start over?"
3. **Pick up:** start at the first step that has not passed. Read `interview.md`, the `samples/` files, and `report.txt` as needed. Python discovery runs again if Step 3 or later is next.
4. **Start over:** keep the answer they just gave to question 1 and go on with question 2. Then overwrite `interview.md`, the sample files, and the other files as each step runs (Write replaces them). Start `conversation.txt` fresh with the new answers. Add new lines to `run-log.md` below the old ones. If `ab-result.json` exists, the A/B uses a new folder (see `blind-ab.md`).

Never delete the user's files with a command.
