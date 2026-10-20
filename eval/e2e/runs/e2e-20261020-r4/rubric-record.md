<!-- Corpus-derived content (persona era-c). Source texts are in the public domain in the USA. Sources: eval/corpus/PROVENANCE.md -->

# Rubric record: e2e-20261020-r4

> Home folder path replaced with ~ by tools/sanitize_artifacts.py (the OS user name, personal names, and email addresses are also replaced: [user], [name], [email]).

Scored against `docs/e2e-rubric.md` (FROZEN 6, the orchestrator R9 note, and the T-011 chat-visibility note) by a clean-room reviewer agent (`claude -p`, tools Read, Glob, Grep only, in a scratch folder holding only SKILL.md, the rubric, the transcript, and the output folder). Raw verdict: `review.json`. Line numbers refer to `transcript.md` in this folder.

| Field | Value |
|---|---|
| Run id | e2e-20261020-r4 |
| Date | 2026-10-20 |
| CLI version | 2.1.303 (Claude Code) |
| Model id | claude-sonnet-5-5 |
| Exact flags | see `transcript.md` header and `manifest.json` (`skill_flags_first`, `skill_flags_later`, `interviewee_flags`) |
| Persona / sample source | era-c / public-domain texts by Elinore Pruitt Stewart (Letters of a Woman Homesteader, 1914, Project Gutenberg eBook #16623) |
| Persona first name (invented) | Hattie |
| Reviewer flags | `--model claude-sonnet-5-5 --no-session-persistence --tools=Read,Glob,Grep --setting-sources project --strict-mcp-config --permission-mode default --permission-prompts none` |
| Reviewer verdict | fail |
| Mechanical chat-visibility cross-check | ok=True |

## Items

| Item | Result | Evidence | Reason |
|---|---|---|---|
| R1 | pass | transcript.md line 121-125: the first message has the intro (five questions, about 10 minutes), the permissions sentence and question 1. Line 254: 'Step 1 of 6 done: Interview.' sits in the message that asks for samples. Line 241: run-log has stage=1 passed, answers=5, followups=0. Line 226: interview.md was written. | The opening and done lines were both in chat before the user was asked to act. The exit check happened: 5 answers saved and 0 follow-ups. |
| R2 | pass | Line 256: Step 2 opening with 'about 2 minutes' and the file-path option. Line 458: 'That's 3 pieces and about 3,500 words'. Line 621: 'Step 2 of 6 done: Sample.' in the Step 3 report message, which ends the turn. Line 430: run-log has stage=2 passed, files=3, words_about=3500. Lines 392-422: three sample files were saved. | The opening line, the word count and the done line were all in chat by the time the user was asked the check-in question. The 3 files and word total were logged. The rubric allows the done line to land in the Step 3 report message. |
| R3 | pass | Line 460: Step 3 opening line in chat. Lines 475-479: analyze.py --version returns schema_version '1'. Lines 494-503: profile and report both ok:true. Line 544: profile.json has schema_version '1'. Lines 625-636: the full report text is in chat. Line 640: 'Step 3 of 6 done: Analysis.'. Line 642: the check-in. Line 608: run-log has stage=3 passed. No Step 4 tool call came before the user's reply. | Python 3.11.9 was found and the status is passed, not degraded. The full report was shown in chat before any Step 4 tool call. The opening line is the exact line SKILL.md gives. |
| R4 | FAIL | Line 900: 'Step 4 of 6: Generate. I wrote your my-voice skill from your answers, your samples, and the numbers.' Line 904: 'Step 4 of 6 done: Generate.' Line 880: build-skill returned ok:true. Line 887: run-log has stage=4 passed with runs=1. | The work is done and logged, and the done line is in the message that asks for the A/B task. But the opening line is not the SKILL.md 'Say' line ('Next, I'll write your my-voice skill ... This takes about a minute.'). It is a past-tense recap with no time estimate, so the rubric's 'what happens next and about how long it takes' is missing. This is a borderline strictness call, and I fail it. Steps 2, 5 and 6 all gave a duration. |
| R5 | pass | Line 906: Step 5 opening with 'about 2 minutes' and the task suggestions. Lines 1187-1213: the A/B message. Line 1228: ab-reveal ran. Line 1239: picked_arm 'with'. Line 1254: run-log has stage=5 passed. Line 1269: 'Step 5 of 6 done: Blind A/B.' in the message that asks for the install choice. | The opening and done lines were both in chat at the right moments. ab-result was produced by ab-reveal. |
| R6 | pass | Line 1271: 'Step 6 of 6: Install. Last step ... about a minute.' Line 1273: the project-versus-personal line. Lines 1299-1302: install ok:true. Line 1317: Glob found the installed SKILL.md. Line 1346: run-log has stage=6 passed, route=project. Line 1363: 'Step 6 of 6 done: Install.' Line 1365: the closing message. | The opening line, the install choice, the confirmation, the done line and the closing were all in chat. |
| R7 | pass | Lines 475-479, 494-503, 873-879, 1152-1182, 1236-1246, 1297-1303: every analyze.py call produced valid JSON with no 'Traceback'. build-skill got ok:true on run 1 (line 874). | All calls succeeded. No Write or Edit touched my-voice/SKILL.md or my-voice.zip. No other zip command was used. |
| R8 | pass | No tool results in the transcript show an error or a permission denial. Line 452: python --version succeeded on the first probe. | There were zero tool errors or denials. The Agent tool and the Edit on interview.md ran without a problem. |
| R9 | pass | See r9_questions: every question is one SKILL.md lists or allows. | There were no unnecessary clarification turns. The authorship question at line 369 is permitted by SKILL.md Step 2 item 4, which allows one ownership check when a piece may not be the user's own. |
| R10 | pass | The model never read ab-mapping.json before the reveal (lines 1140-1214). Lines 1159-1181 hold the ab-present output and lines 1187-1213 hold the next chat message. Line 1081 holds the subagent prompt. | (a) ab-mapping.json was never opened. Its contents appeared only in the ab-reveal output at line 1240, after the pick. (b) The fixed opening line, then the draft text, then 'Which sounds more like you? Type A or B.' The draft text matches the ab-present output exactly: the 'Draft A' and 'Draft B' headers and every paragraph are identical, with only blank-line and whitespace differences at the edges. (c) There is no hint of which draft is which. (d) The subagent prompt is the task text, a blank line, the full shared rule including the name sentences, a blank line, and 'Do not use any skills.' (e) Noted: the pick is an LLM's choice. |

## Chat-visible stage lines (reviewer)

| Stage | Opening line | Done line | Result shown |
|---|---|---|---|
| 1 | yes, line 121 | yes, line 254 | n/a |
| 2 | yes, line 256 | yes, line 621 | word count: yes, line 458 |
| 3 | yes, line 460 | yes, line 640 | report: yes, line 625 |
| 4 | NO | yes, line 904 | n/a |
| 5 | yes, line 906 | yes, line 1269 | n/a |
| 6 | yes, line 1271 | yes, line 1363 | n/a |

## R9 question list

| Line | Question | Class | Reason |
|---|---|---|---|
| 125 | Q1: What do you mostly use AI to help you write? | expected | Interview question 1. |
| 168 | Q2: Who usually reads it? | expected | Interview question 2. |
| 182 | Q3: Pick three words for how you want to sound. | expected | Interview question 3. |
| 196 | Q4: What bugs you most in drafts AI writes for you? | expected | Interview question 4. |
| 210 | Q5: Any habits you always or never have? | expected | Interview question 5. |
| 256 | Paste three or more things you wrote (or give file paths). | expected | Step 2 sample request. |
| 369 | Did you write these yourself? | expected | SKILL.md Step 2 item 4 allows one ownership check when the content seems not to be the user's own. The pieces did not match the interview answers. |
| 642 | Does this sound like you? Reply yes, or tell me what's off. | expected | Step 3 check-in. |
| 908 | What's a short real message you need to write? (with suggestions) | expected | Step 5 A/B task. |
| 1213 | Which sounds more like you? Type A or B. | expected | The A/B pick. |
| 1275 | Which one do you want, project or personal folder? | expected | Step 6 install choice. |

## Reviewer notes

The only failure is R4. The Step 4 opening line was a past-tense recap ('I wrote your my-voice skill ...') with no 'Next, ... This takes about a minute.' wording and no time estimate. Everything else passes. R1-R3 and R5-R6 have their opening and done lines in chat at the right turn boundaries, the Step 2 word count and the full Step 3 report are in chat before any Step 4 tool call, the blind A/B was handled correctly, there were no tool errors, and the run has no unnecessary questions. If the orchestrator treats the Step 4 line as an acceptable paraphrase, the run would pass all items. Also: the Step 2 opening line was in the message that ended Step 1, and the Step 5 reveal message correctly followed the pick.

## Orchestrator disposition (2026-10-20)

The reviewer's verdict above stays as recorded (fail on R4 only). The orchestrator accepts r4 as the passing labeled run under item 3 of decision `2026-10-20-turn-boundaries-for-visibility-moreme`: the Step 4 opening and done lines (transcript lines 900 and 904) reached chat before the next message that asked the user to act. The reviewer's stricter reading of R4 (the opening line should say what happens next and how long it takes, before Step 4's tool calls) is handled by a SKILL.md addendum in T-013 and will be checked in the Phase 2 final e2e run.
