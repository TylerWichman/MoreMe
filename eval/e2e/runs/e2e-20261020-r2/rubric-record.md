<!-- Corpus-derived content (persona era-c). Source texts are in the public domain in the USA. Sources: eval/corpus/PROVENANCE.md -->

# Rubric record: e2e-20261020-r2

> Home folder path replaced with ~ by tools/sanitize_artifacts.py (the OS user name, personal names, and email addresses are also replaced: [user], [name], [email]).

Scored against `docs/e2e-rubric.md` (FROZEN 6, the orchestrator R9 note, and the T-011 chat-visibility note) by a clean-room reviewer agent (`claude -p`, tools Read, Glob, Grep only, in a scratch folder holding only SKILL.md, the rubric, the transcript, and the output folder). Raw verdict: `review.json`. Line numbers refer to `transcript.md` in this folder.

| Field | Value |
|---|---|
| Run id | e2e-20261020-r2 |
| Date | 2026-10-20 |
| CLI version | 2.1.303 (Claude Code) |
| Model id | claude-sonnet-5-5 |
| Exact flags | see `transcript.md` header and `manifest.json` (`skill_flags_first`, `skill_flags_later`, `interviewee_flags`) |
| Persona / sample source | era-c / public-domain texts by Elinore Pruitt Stewart (Letters of a Woman Homesteader, 1914, Project Gutenberg eBook #16623) |
| Persona first name (invented) | Hattie |
| Reviewer flags | `--model claude-sonnet-5-5 --no-session-persistence --tools=Read,Glob,Grep --setting-sources project --strict-mcp-config --permission-mode default --permission-prompts none` |
| Reviewer verdict | fail |
| Mechanical chat-visibility cross-check | ok=False |

## Items

| Item | Result | Evidence | Reason |
|---|---|---|---|
| R1 | FAIL | transcript.md lines 104-151: the Skill call, Glob and Write of .gitignore all run before any chat text. The first **Assistant:** block (line 150) is only 'Question 1 of 5: ...'. Done line at line 250. | Stage 1 has no chat opening line and no permissions sentence before its first tool call. run-log says passed, but the chat requirement fails. |
| R2 | pass | line 252: 'Next, paste three or more things you wrote yourself...about 2 minutes' comes before the first Write at line 382. Word count at line 430 ('3 pieces and about 3,100 words'). Done line at line 451. run-log line 2 is passed. | Opening, running word count and done line are all in chat in the right order. Three files were saved. |
| R3 | FAIL | line 453 opening, line 558 done. The report was only Read (lines 514-538). The next **Assistant:** block (556-561) has the done line and the Step 4 opening, with no report text. | The report.txt content and the sentences tying it to the interview never appeared in chat. profile.json and schema_version 1 were confirmed at lines 480-488. |
| R4 | pass | line 560 opening comes before the Read at line 563. build-skill ok:true at lines 746-753. Run-log write at 756. Chat summary at 774, done line at 776. | Opening, summary and done line are in chat in order. build-skill passed on run 1. |
| R5 | pass | line 778 opening and the task question come before the Glob at 796. ab-present at 1014-1056. Reveal at 1098. Done line at 1143, after the run-log write at 1123. | Opening and done line are in chat, and ab-result.json exists. |
| R6 | pass | line 1145 opening comes before the install call at 1160. install ok:true at 1172-1177. Glob confirms SKILL.md at 1191. Run-log write at 1215. Done line at 1237. | Opening and done line are in chat in order. The install check and the how-to-check-it-works text were done. |
| R7 | pass | analyze.py calls: --version (480-488), profile+report (499-511), build-skill (746-753), ab-shuffle+present (1023-1056), ab-reveal (1107-1120), install (1169-1178). No Traceback, all ok. Only the python --version probe was used, and it worked first time. | build-skill reached ok:true on run 1. No Write or Edit touched my-voice/SKILL.md or my-voice.zip, and no other zip command ran. |
| R8 | pass | No tool error or permission denial appears in the tool results I read (lines 96-1240). | I did not read lines ~700-726, which are the voice-notes Write call. Its result at line 732 shows success. |
| R9 | pass | See r9_questions. | Every question is an interview question, the sample-authorship check, the A/B task, the A/B pick or the install choice. |
| R10 | pass | The ab-present output (lines 1033-1055) matches the reprint at lines 1063-1085 exactly. The message at 1061 has the fixed opening, then the output, then 'Which sounds more like you? Type A or B.' (line 1087). The subagent prompt (line 955) is the task, the shared rule and 'Do not use any skills.' ab-mapping.json was never read or printed before ab-reveal at 1102. | (a), (b), (c) and (d) all hold. Nothing between the message and the pick hints at which draft is which. |

## Chat-visible stage lines (reviewer)

| Stage | Opening line | Done line | Result shown |
|---|---|---|---|
| 1 | NO | yes, line 250 | n/a |
| 2 | yes, line 252 | yes, line 451 | word count: yes, line 430 |
| 3 | yes, line 453 | yes, line 558 | report: NO |
| 4 | yes, line 560 | yes, line 776 | n/a |
| 5 | yes, line 778 | yes, line 1143 | n/a |
| 6 | yes, line 1145 | yes, line 1237 | n/a |

## R9 question list

| Line | Question | Class | Reason |
|---|---|---|---|
| 150 | Question 1 of 5: What do you mostly use AI to help you write? | expected | Interview question 1. |
| 164 | Question 2 of 5: Who usually reads it? | expected | Interview question 2. |
| 178 | Question 3 of 5: Pick three words for how you want to sound. | expected | Interview question 3. |
| 192 | Question 4 of 5: What bugs you most in drafts AI writes for you? | expected | Interview question 4. |
| 206 | Question 5 of 5: Any habits you always or never have? | expected | Interview question 5. |
| 365 | Did you write them yourself? | expected | SKILL.md step 2.4 allows one ownership check when a piece looks like it is not the user's writing. |
| 780 | What short, real message do you need to write? (with 3 suggestions) | expected | Task for the A/B. |
| 1087 | Which sounds more like you? Type A or B. | expected | The A/B pick. |
| 1149 | Which one do you want? (project or personal folder) | expected | Install choice. |

## Reviewer notes

Two chat-visibility failures. R1: Stage 1 has no opening line and no permissions sentence in chat before its first tool call, and the first visible text is already Question 1. R3: the Step 3 report was never reprinted in chat, and neither were the sentences tying it to the interview answers. The rest of the run is clean. The stage 2 and 4-6 lines, the script calls, the blind A/B and the install all check out. Minor: the Step 2 word estimate (~3,100) is lower than the measured 3,839, which SKILL.md allows.
