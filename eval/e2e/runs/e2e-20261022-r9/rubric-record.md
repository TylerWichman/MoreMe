<!-- Corpus-derived content (persona era-c). Source texts are in the public domain in the USA. Sources: eval/corpus/PROVENANCE.md -->

# Rubric record: e2e-20261022-r9

> Home folder path replaced with ~ by tools/sanitize_artifacts.py (the OS user name, personal names, and email addresses are also replaced: [user], [name], [email]).

Scored against `docs/e2e-rubric.md` by a clean-room reviewer agent (`claude -p`, tools Read, Glob, Grep only, in a scratch folder holding only SKILL.md, the rubric, the transcript, and the output folder). Raw verdict: `review.json`. Line numbers refer to `transcript.md` in this folder.

Run after the R10 wording fix. Failed R2, R3, R4, and R10: in this run Claude did not show the Step 3 report in chat and the A/B reprint was not verbatim. Kept as evidence that runs vary.

| Field | Value |
|---|---|
| Run id | e2e-20261022-r9 |
| Date | 2026-10-22 |
| CLI version | 2.1.306 (Claude Code) |
| Model id | claude-sonnet-5-5 |
| Exact flags | see `transcript.md` header and `manifest.json` (`skill_flags_first`, `skill_flags_later`, `interviewee_flags`) |
| Persona / sample source | era-c / public-domain texts by Elinore Pruitt Stewart (Letters of a Woman Homesteader, 1914, Project Gutenberg eBook #16623) |
| Persona first name (invented) | Hattie |
| Sample composition | corpus share 0.794 (rule: at least 0.75) |
| Reviewer flags | `--model claude-sonnet-5-5 --no-session-persistence --tools=Read,Glob,Grep --setting-sources project --strict-mcp-config --permission-mode default --permission-prompts none` |
| Reviewer verdict | fail |
| Mechanical chat-visibility cross-check | ok=False |

## Items

| Item | Result | Evidence | Reason |
|---|---|---|---|
| R1 | pass | transcript.md lines 120-124 and 226 | The first message has the introduction, the permissions sentence and question 1. The Step 1 done line is at the top of the topic message. run-log has stage=1 passed (line 213). |
| R2 | fail | transcript.md lines 228-234, 265, 298, 329; no 'Step 2 of 6 done: Sample.' in any Assistant block | The opening line and running word counts (95, 160, 235) were shown in chat. The Step 2 done line never appeared in chat. The turn-7 message (line 499) asks the user to act and does not contain it. The log line was only written in a tool call (line 376). |
| R3 | fail | transcript.md lines 403 and 499; report.txt content appears only in a Read result (lines 463-476) | The opening line was shown (403). The report message at 499 does not include the report text, the sentences tying it to the interview, or 'Step 3 of 6 done: Analysis.'. It only says 'I've measured your writing...'. The report is required in chat before any Step 4 tool call. |
| R4 | fail | transcript.md lines 776-788; the 'Step 4 opening' line 'Next, I'll write your my-voice skill. It takes about a minute.' is absent from every Assistant block | The done line is shown (776). The Step 4 opening line was never shown, not even at the end of the report message, which was also the point where Step 3 should have ended. |
| R5 | pass | transcript.md lines 780, 1049-1073, 1241; run-log stage=5 line (1224) | The opening line is in the message at 780. The done line is at 1241, in the message that asks the install question. The Step 5 check happened: ab-result.json exists and the reveal ran. R10 separately fails because of the reprint. |
| R6 | pass | transcript.md lines 1243, 1245-1247, 1387; run-log stage=6 (1370) | The opening line, the project/personal line and the choice question are shown. The install returned ok:true and Glob confirmed SKILL.md. The done line is in the closing message. |
| R7 | pass | transcript.md lines 410-450, 726-740, 1009-1022, 1088-1113, 1262-1282 | Every analyze.py call exited 0 with no Traceback. build-skill reached ok:true on run 1. my-voice/SKILL.md and my-voice.zip were not written by any Write or Edit call. |
| R8 | pass | transcript.md Tool results throughout | No tool errors or permission denials. The one 'No files found' Glob result is a normal existence check, not a failure. |
| R9 | pass | see r9_questions | All questions asked were expected ones. No unnecessary clarification turns. |
| R10 | fail | transcript.md line 1041 (ab-present output: 'Write when you have a moment') versus line 1069 (assistant reprint: 'Write when you can'); the assistant admits the change at line 1239 | (a) ab-mapping.json was not read before the reveal (pass). (b) The reprint is not verbatim: Draft B's last paragraph differs, so this fails. (c) The message has no hints (pass). (d) The subagent prompt (line 951) is the task, the shared rule and 'Do not use any skills.' (pass). Item (b) fails, so R10 fails. |

## Chat-visible stage lines (reviewer)

| Stage | Opening line | Done line | Result shown |
|---|---|---|---|
| 1 | yes, line 120 | yes, line 226 | n/a |
| 2 | yes, line 228 | no | word count: yes, line 329 |
| 3 | yes, line 403 | no | report: no |
| 4 | no | yes, line 776 | n/a |
| 5 | yes, line 780 | yes, line 1241 | n/a |
| 6 | yes, line 1243 | yes, line 1387 | n/a |

## R9 question list

| Line | Question | Class | Reason |
|---|---|---|---|
| 124 | What do you mostly use AI to help you write? | expected | Interview question 1. |
| 167 | What bugs you most in drafts AI writes for you? | expected | Interview question 2. |
| 228 | Topic opener: tell me about something you could go on about... | expected | Step 2 topic question. |
| 265 | What did Mrs. Louderer have cooking, and what was the smell that stuck with you most? | expected | Follow-up drawn from the previous answer, running total 95 of 300. |
| 298 | How did you get all that food out to twelve camps? | expected | Follow-up drawn from the previous answer, running total 160 of 300. |
| 329 | What was it like out on the road that morning? | expected | Follow-up drawn from the previous answer, running total 235 of 300. |
| 499 | Does the report sound like you? Reply yes, or tell me what's off. | expected | Step 3 check-in. The report itself was not shown, which is a visibility failure under R3, not an unnecessary question. |
| 782 | What's a short, real message you need to write? (with suggestions) | expected | Task for the A/B. |
| 1073 | Which sounds more like you? Type A or B. | expected | Fixed A/B pick question. |
| 1247 | Which one do you want? Project folder (default) or personal. | expected | Install choice. |

## Reviewer notes

The run fails R2, R3, R4 and R10, for these reasons. (1) After the Step 3 work, the message at line 499 is a bare check-in. It lacks the Step 2 and Step 3 done lines, the Here is what MoreMe measured line, the report.txt text, the interview tie-in and the Step 4 opening line. (2) The Step 4 opening line never appears in chat. (3) The A/B reprint at line 1069 changed 'Write when you have a moment' to 'Write when you can', so it is not verbatim. The assistant later noticed and said so at line 1239, after the pick. The log lines in run-log.md for stages 2 to 4 cannot make up for these gaps. The sample composition in the header is corpus share 0.794, so the run counts as a reference run. I did not read run-log.md or the files in output/ directly. I judged from the transcript, which shows every run-log write and the output file list.
