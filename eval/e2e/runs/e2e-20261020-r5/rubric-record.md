<!-- Corpus-derived content (persona era-c). Source texts are in the public domain in the USA. Sources: eval/corpus/PROVENANCE.md -->

# Rubric record: e2e-20261020-r5

> Home folder path replaced with ~ by tools/sanitize_artifacts.py (the OS user name, personal names, and email addresses are also replaced: [user], [name], [email]).

Scored against `docs/e2e-rubric.md` (FROZEN 6, the orchestrator R9 note, and the T-011 chat-visibility note) by a clean-room reviewer agent (`claude -p`, tools Read, Glob, Grep only, in a scratch folder holding only SKILL.md, the rubric, the transcript, and the output folder). Raw verdict: `review.json`. Line numbers refer to `transcript.md` in this folder.

| Field | Value |
|---|---|
| Run id | e2e-20261020-r5 |
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
| R1 | pass | transcript.md line 121-125: first message has the introduction, the permissions sentence and question 1. Line 269: 'Step 1 of 6 done: Interview.' Line 256: run-log stage=1 status=passed. | The introduction was in the first message with question 1. The done line came at the top of the first writing prompt. The run-log line is passed with answers=5,followups=0. |
| R2 | pass | transcript.md line 271: Step 2 opening line. Line 273: 'About 190 of 300 words so far.' Line 437: 'Step 2 of 6 done: Sample.' Line 322: run-log stage=2 passed. | The opening line, the word count in chat and the done line (in the Step 3 report message, which is allowed) are all present. The samples reached 317 words, so the target was met. |
| R3 | FAIL | transcript.md lines 437-461: the report message has no 'Next, MoreMe's measuring script reads your samples. If Claude Code asks, choose Yes.' No other **Assistant:** block has it either. Line 457 is the done line. Lines 439-453 are the report. | The full report, the check-in question and 'Step 3 of 6 done: Analysis.' were shown, and profile.json was made with schema_version 1. But Step 3's own opening line never appeared in chat. The only 'Next, ...' line in that message is Step 4's opening line (line 461). Under the chat-visibility rule, a missing opening line fails the stage. |
| R4 | pass | transcript.md line 461: 'Next, I'll write your my-voice skill. It takes about a minute.' Line 731: 'Step 4 of 6 done: Generate.' Lines 704-710: build-skill ok:true. Line 718: run-log stage=4 passed. | The opening line was shown before the work. The done line came at the top of the A/B task message. build-skill reached ok:true on the first run. |
| R5 | pass | transcript.md line 735: Step 5 opening line. Line 1014-1040: A/B message. Line 1204: 'Step 5 of 6 done: Blind A/B.' Line 1189: run-log stage=5 passed. | The opening line was shown. The done line came in the message that also asks the install question, so it is not late. |
| R6 | pass | transcript.md line 1206: 'Last step: putting my-voice where Claude can find it...' Line 1297: 'Step 6 of 6 done: Install.' Lines 1233-1237: install ok:true. Line 1251: Glob found the installed SKILL.md. | The opening line, install ok:true, the installed SKILL.md confirmed, and the done line in the closing message are all present. |
| R7 | pass | transcript.md lines 343-361, 372-390, 701-710, 976-985, 1067-1081, 1229-1238: every analyze.py call returned normal JSON. There is no Traceback anywhere. | No analyze.py output shows an error. build-skill reached ok:true in 1 run. my-voice/SKILL.md and my-voice.zip were not written by any Write or Edit call, and no other zip command ran. |
| R8 | pass | No tool error or permission denial appears in the transcript. The only Python probe was `python --version` (line 336), which succeeded. | There were no tool errors or denials, and no writes outside the scratch project. |
| R9 | FAIL | transcript.md line 289: 'did you write that yourself just now, or is it from a book or an old letter?' | This question was unnecessary. The user had just typed the answer in this chat and the guided flow treats typed answers as the sample. SKILL.md doesn't list a provenance question, so it counts as an unneeded clarification turn. The assistant also praised the answer at line 289, though SKILL.md says not to praise. |
| R10 | pass | transcript.md lines 968-1009 (ab-present output) and 1014-1040 (chat message). The agent prompt is at line 909. Line 1055 is ab-reveal, run after the pick at line 1048. | (a) ab-mapping.json was not read or printed before ab-reveal. (b) The next chat message is the fixed opening line, the ab-present text, then the fixed question. The reprinted text matches the tool output character for character, apart from surrounding whitespace. (c) No hints were added between that message and the pick. (d) The subagent prompt is the task text, the shared rule and 'Do not use any skills.', and nothing else. (e) The pick is an LLM's choice and is not treated as evidence of quality. |

## Chat-visible stage lines (reviewer)

| Stage | Opening line | Done line | Result shown |
|---|---|---|---|
| 1 | yes, line 121 | yes, line 269 | n/a |
| 2 | yes, line 271 | yes, line 437 | word count: yes, line 273 |
| 3 | NO | yes, line 457 | report: yes, line 441 |
| 4 | yes, line 461 | yes, line 731 | n/a |
| 5 | yes, line 735 | yes, line 1204 | n/a |
| 6 | yes, line 1206 | yes, line 1297 | n/a |

## R9 question list

| Line | Question | Class | Reason |
|---|---|---|---|
| 125 | Question 1: What do you mostly use AI to help you write? | expected | Interview question 1. |
| 168 | Question 2: Who usually reads it? | expected | Interview question 2. |
| 182 | Question 3: Pick three words for how you want to sound. | expected | Interview question 3. |
| 196 | Question 4: What bugs you most in drafts AI writes for you? | expected | Interview question 4. |
| 210 | Question 5: Any habits you always or never have? | expected | Interview question 5. |
| 273 | First writing prompt: tell me about the last time something made you laugh out loud. | expected | Guided writing prompt that follows from the interview. The running total was about 190 of 300, so it was still needed. |
| 289 | Did you write that yourself just now, or is it from a book or an old letter? | unnecessary | The user typed the answer in this chat and the guided flow takes typed answers as the sample. SKILL.md has no provenance question. |
| 459 | Does this sound like you? Reply yes, or tell me what's off. | expected | Step 3 check-in. |
| 737 | What's a short, real message you need to write? (with 3 suggestions) | expected | Task for the A/B. |
| 1040 | Which sounds more like you? Type A or B. | expected | A/B pick. |
| 1210 | Which one do you want? (project folder or personal folder) | expected | Install choice. |

## Reviewer notes

R3 fails because Step 3's opening line ('Next, MoreMe's measuring script reads your samples. If Claude Code asks, choose Yes.') never appeared in chat. R9 fails because of the provenance question at line 289. R1, R2, R4, R5, R6, R7, R8 and R10 pass. The blind A/B was handled correctly, and the ab-present reprint matches the tool output. Step 2 finished after one writing prompt because the total reached 317 words, which is acceptable. The mechanical cross-check in the transcript header marked the Step 3 opening as True, probably because it matched Step 4's opening line; the reviewer's judgment is that the line is missing. Minor: the assistant praised the user's answer at line 289, which SKILL.md says not to do.
