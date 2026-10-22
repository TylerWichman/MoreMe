<!-- Corpus-derived content (persona era-c). Source texts are in the public domain in the USA. Sources: eval/corpus/PROVENANCE.md -->

# Rubric record: e2e-20261022-r8

> Home folder path replaced with ~ by tools/sanitize_artifacts.py (the OS user name, personal names, and email addresses are also replaced: [user], [name], [email]).

Scored against `docs/e2e-rubric.md` by a clean-room reviewer agent (`claude -p`, tools Read, Glob, Grep only, in a scratch folder holding only SKILL.md, the rubric, the transcript, and the output folder). Raw verdict: `review.json`. Line numbers refer to `transcript.md` in this folder.

Reference run for the current flow. R10 failed on one point: a repeated 'Step 4 of 6 done' line at the top of the A/B message (no hint about which draft is which). SKILL.md was then changed to say 'no step lines' in that message; that change was not re-run to a full pass.

| Field | Value |
|---|---|
| Run id | e2e-20261022-r8 |
| Date | 2026-10-22 |
| CLI version | 2.1.306 (Claude Code) |
| Model id | claude-sonnet-5-5 |
| Exact flags | see `transcript.md` header and `manifest.json` (`skill_flags_first`, `skill_flags_later`, `interviewee_flags`) |
| Persona / sample source | era-c / public-domain texts by Elinore Pruitt Stewart (Letters of a Woman Homesteader, 1914, Project Gutenberg eBook #16623) |
| Persona first name (invented) | Hattie |
| Sample composition | corpus share 0.916 (rule: at least 0.75) |
| Reviewer flags | `--model claude-sonnet-5-5 --no-session-persistence --tools=Read,Glob,Grep --setting-sources project --strict-mcp-config --permission-mode default --permission-prompts none` |
| Reviewer verdict | fail |
| Mechanical chat-visibility cross-check | ok=True |

## Items

| Item | Result | Evidence | Reason |
|---|---|---|---|
| R1 | pass | transcript.md line 122: the first message gives the intro, the permissions sentence and question 1. Line 294: 'Step 1 of 6 done: Interview.' run-log.md line 1: stage=1 status=passed answers=2. | The opening and done lines are in chat, the two answers were saved, and the stage is logged as passed. |
| R2 | pass | transcript.md line 296 (topic opener, 'about 8 minutes'); lines 331, 362, 393 ('About 110/190/270 of 300 words so far'); line 547 (done line); run-log line 2 passed, words_about=327. | The opening line, the running word counts and the done line were all shown in chat. The done line came in the Step 3 report message, which SKILL.md allows. |
| R3 | pass | transcript.md line 439 and line 549 (opening line); lines 553-567 (full report.txt text); line 571 (done line); line 573 (check-in). profile.json was built (lines 484-499) and --version showed schema_version 1 (line 469). run-log line 3 passed. | The full report was shown in chat before any Step 4 tool call, followed by the done line and the check-in question. |
| R4 | pass | transcript.md line 575 (Step 4 opening line); build-skill returned ok:true on the first run (lines 813-818); line 839 (done line); the A/B task message at lines 841-850 summarizes the skill. run-log line 4 passed, runs=1. | The opening line and done line were shown, and build-skill succeeded in one run. |
| R5 | pass | transcript.md line 843 (Step 5 opening line); line 1141 (A/B question); line 1305 (done line after the reveal); ab-result.json exists in output/. run-log line 5 passed. | The opening line was shown before the user was asked to act. The done line followed the reveal, which is where SKILL.md puts it. |
| R6 | pass | transcript.md line 1307 (Step 6 opening line and the project/personal choice line); install returned ok:true (lines 1341-1346); the Glob confirmed SKILL.md (line 1424); line 1449 (done line). run-log line 6 passed. | The opening line was shown with the install question, the install was confirmed, and the done line was shown in the closing message. |
| R7 | pass | transcript.md lines 453-471 (python --version; analyze.py --version); lines 484-499 (profile and report); line 813 (build-skill ok:true on run 1); lines 1171-1181 (ab-reveal); line 1341 (install). No output contains 'Traceback'. | Every analyze.py call exited cleanly and build-skill succeeded on its first run. The model did not Write or Edit my-voice/SKILL.md or my-voice.zip. |
| R8 | pass | No tool errors or denials anywhere in transcript.md. The only Python probe (line 446) succeeded. All Writes went inside moreme-output, and the Reads were of reference files, the user's own files and moreme-output files. | There were no tool failures or permission denials. |
| R9 | pass | See r9_questions: every question the assistant asked is expected. | There were no unnecessary clarification turns. The assistant never asked for pasted text, a file format or a save location. |
| R10 | fail | transcript.md lines 1112-1142: the message starts with 'Step 4 of 6 done: Generate.' before 'Here are two drafts of the same message. One used your new voice skill and one didn't.' ab-mapping.json was never read before ab-reveal (line 1156). The subagent prompt at line 896 is correct. Lines 1089-1109 and 1119-1139 match. | (a) passes: ab-mapping.json was not read before the reveal. (d) passes: the subagent prompt holds only the task text, the shared rule and 'Do not use any skills.' (c) passes: nothing in the message hints at which draft is which. (b) fails strictly: the ab-present reprint is identical to the tool output, but SKILL.md requires the message to be exactly the opening line, the reprint and the question, 'and nothing else'. This message adds a stray 'Step 4 of 6 done: Generate.' line in front. That line is a repeat, because it was already shown at line 839. It gives no hint, so this is a minor formatting deviation, scored as a fail on the literal reading. |

## Chat-visible stage lines (reviewer)

| Stage | Opening line | Done line | Result shown |
|---|---|---|---|
| 1 | yes, line 122 | yes, line 294 | n/a |
| 2 | yes, line 296 | yes, line 547 | word count: yes, line 331 |
| 3 | yes, line 439 | yes, line 571 | report: yes, line 553 |
| 4 | yes, line 575 | yes, line 839 | n/a |
| 5 | yes, line 843 | yes, line 1305 | n/a |
| 6 | yes, line 1307 | yes, line 1449 | n/a |

## R9 question list

| Line | Question | Class | Reason |
|---|---|---|---|
| 126 | What do you mostly use AI to help you write? For example emails, posts, or cover letters. | expected | Interview question 1. |
| 169 | What bugs you most in drafts AI writes for you? Words, phrases, or habits. | expected | Interview question 2. |
| 296 | Topic opener: 'Tell me about something you could go on about for a while...' with three openers. | expected | The Step 2 topic question. |
| 331 | Who was the merry party that flew past you, and what happened once you all got to the dance? | expected | A follow-up drawn from the user's last answer, asked at about 110 of 300 words. |
| 362 | What was the hall like inside, and who did you end up dancing with? | expected | A follow-up drawn from the user's last answer, asked at about 190 of 300 words. |
| 393 | Which of those dishes was your favorite, and how would you explain the whole spread to a friend who wasn't there? | expected | A follow-up drawn from the user's last answer, asked at about 270 of 300 words. It has two parts, but each part is a follow-up SKILL.md allows. |
| 573 | Does this sound like you? Reply yes, or tell me what's off. | expected | The Step 3 check-in. |
| 845 | What's a short real message you need to write? (with three suggestions) | expected | The task for the A/B. |
| 1141 | Which sounds more like you? Type A or B. | expected | The A/B pick. |
| 1311 | Which one do you want, project folder or personal folder? You can also upload it to claude.ai. | expected | The install choice. |

## Reviewer notes

R1-R9 pass. R10 fails on (b) only. The A/B message at transcript.md line 1112 opens with a repeated 'Step 4 of 6 done: Generate.' line, so it is not exactly the fixed opening line, the verbatim ab-present reprint and the fixed question. The reprint matches the tool output exactly, nothing hints at which draft is which, the 'without' subagent prompt is clean, and ab-mapping.json was not read before the reveal. Reviewers who read (b) as only about the reprint and the hints could pass this item. Run validity: the header gives a corpus share of 0.916, above the 0.75 threshold.
