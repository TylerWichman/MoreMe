<!-- Corpus-derived content (persona era-c). Source texts are in the public domain in the USA. Sources: eval/corpus/PROVENANCE.md -->

# Rubric record: e2e-20261021-r6

> Home folder path replaced with ~ by tools/sanitize_artifacts.py (the OS user name, personal names, and email addresses are also replaced: [user], [name], [email]).

Scored against `docs/e2e-rubric.md` (FROZEN 6, the orchestrator R9 note, and the T-011 chat-visibility note) by a clean-room reviewer agent (`claude -p`, tools Read, Glob, Grep only, in a scratch folder holding only SKILL.md, the rubric, the transcript, and the output folder). Raw verdict: `review.json`. Line numbers refer to `transcript.md` in this folder.

| Field | Value |
|---|---|
| Run id | e2e-20261021-r6 |
| Date | 2026-10-21 |
| CLI version | 2.1.303 (Claude Code) |
| Model id | claude-sonnet-5-5 |
| Exact flags | see `transcript.md` header and `manifest.json` (`skill_flags_first`, `skill_flags_later`, `interviewee_flags`) |
| Persona / sample source | era-c / public-domain texts by Elinore Pruitt Stewart (Letters of a Woman Homesteader, 1914, Project Gutenberg eBook #16623) |
| Persona first name (invented) | Hattie |
| Reviewer flags | `--model claude-sonnet-5-5 --no-session-persistence --tools=Read,Glob,Grep --setting-sources project --strict-mcp-config --permission-mode default --permission-prompts none` |
| Reviewer verdict | pass |
| Mechanical chat-visibility cross-check | ok=True |

## Items

| Item | Result | Evidence | Reason |
|---|---|---|---|
| R1 | pass | transcript.md lines 119-127: the first message has the introduction (five questions, writing prompts, about 12 to 15 minutes), the permissions sentence and question 1. Line 354: 'Step 1 of 6 done: Interview.' opens the first writing prompt. run-log.md line 1 has stage=1 status=passed with answers=5,followups=0. | The introduction was in the first message. The done line appeared by the first writing prompt. Both interview files were written (lines 306-335). No follow-ups were asked. |
| R2 | pass | Opening line at 356 ('Next, a few short writing prompts... about 5 minutes'). Word counts shown at 358, 389, 420 and 451. Done line at 579, in the Step 3 report message that ends the turn. run-log.md line 2 has stage=2 status=passed. | The opening line, the running word counts and the done line were all visible by the time the user was asked to act. The done line is allowed to land in the report message. The chat said about 330 words while the measured total was 288, which counts as the allowed estimate. The corpus share of 0.752 meets the 75% threshold. |
| R3 | pass | Lines 579-605: the Step 2 done line, the opening line 'Next, MoreMe's measuring script reads your samples...', 'Here is what MoreMe measured...', the full report text, a tying sentence, 'Step 3 of 6 done: Analysis.', the check-in question, and Step 4's opening line. Tool calls at 475-514 show python --version, analyze.py --version with schema_version '1', then profile and report with ok true. run-log.md line 3 has stage=3 status=passed. | The report was shown in chat before any Step 4 tool call. The Step 4 tool calls start at 616, after the user's reply. The check-in question comes after the done line, as SKILL.md orders it. |
| R4 | pass | Opening line at 605, in the Step 3 report message: 'Next, I'll write your my-voice skill. It takes about a minute.' The build-skill result at 818-825 shows ok true with the zip. Done line at 955: 'Step 4 of 6 done: Generate.' in the A/B task message. run-log.md line 4 has stage=4 status=passed with runs=1. | build-skill reached ok true on the first run. The done line and the two-to-three sentence summary are in the message that asks for the A/B task. |
| R5 | pass | Opening line at 959 ('Next, a quick test... about 2 minutes'). The A/B message is at 1250-1276. Line 1404: 'Step 5 of 6 done: Blind A/B.' comes with the install question at 1410. run-log.md line 5 has stage=5 status=passed with picked_arm=with. | ab-reveal ran and wrote ab-result.json (1291-1309). The done line is in the install-question message, the latest allowed spot. It came after the user's A pick, not after a later message. |
| R6 | pass | Opening line at 1406 ('Last step: putting my-voice where Claude can find it...') and the folder line at 1408. The install result at 1432-1438 shows ok true. The Glob at 1445-1452 confirmed SKILL.md. Done line at 1477, in the closing message. run-log.md line 6 has stage=6 status=passed with route=project. | The opening line and the exact folder sentence were shown, and the install was confirmed. The done line is in the closing message, as SKILL.md allows. |
| R7 | pass | Every analyze.py call (lines 490, 509, 805, 1207, 1291, 1425) returned a JSON result with no Traceback. build-skill returned ok true on run 1 (820). The transcript shows no Write or Edit on my-voice/SKILL.md or the zip; the Write at 797 targets voice-notes.md. | All script calls succeeded. The skill and zip were written only by build-skill. |
| R8 | pass | The transcript shows no tool errors or permission denials. Each tool result is a success, a file listing or normal output. | No unexpected failures. The only Read calls were on skill reference files, which are part of the skill and not user files. |
| R9 | pass | See r9_questions. All questions are the five interview questions, three writing prompts, the check-in, the A/B task, the A/B pick and the install choice. | No unnecessary questions. The third writing prompt was asked at an estimated 245 words, under 300. No paste or file request was made. The model asked no resume question, and none was needed because run-log.md did not exist yet. |
| R10 | pass | (a) No Read, Glob or print of ab-mapping.json appears before ab-reveal. The only mapping appears in the ab-reveal output at 1303-1306, after the pick. (b) The ab-present output at 1222-1244 matches the reprint at 1252-1274 character for character, ignoring whitespace. The opening line at 1250 and the question at 1276 are the fixed text. (c) The A/B message has no hints, and nothing sits between it and the pick. (d) The Agent prompt at 1132 is the task text, the full shared rule and 'Do not use any skills.' only. | The A/B message was the fixed three parts. The 'without' draft came from a clean subagent. The model had briefly written 'Dear Anna' in the 'with' draft and replaced it with 'Dear friend' at 1193, before the draft was shown. This does not affect blindness. |

## Chat-visible stage lines (reviewer)

| Stage | Opening line | Done line | Result shown |
|---|---|---|---|
| 1 | yes, line 122 | yes, line 354 | n/a |
| 2 | yes, line 356 | yes, line 579 | word count: yes, line 451 |
| 3 | yes, line 581 | yes, line 601 | report: yes, line 585 |
| 4 | yes, line 605 | yes, line 955 | n/a |
| 5 | yes, line 959 | yes, line 1404 | n/a |
| 6 | yes, line 1406 | yes, line 1477 | n/a |

## R9 question list

| Line | Question | Class | Reason |
|---|---|---|---|
| 126 | Question 1: What do you mostly use AI to help you write? | expected | Interview question 1. |
| 169 | Question 2: Who usually reads it? | expected | Interview question 2. |
| 183 | Question 3: Pick three words for how you want to sound. | expected | Interview question 3. |
| 197 | Question 4: What bugs you most in drafts AI writes for you? | expected | Interview question 4. |
| 211 | Question 5: Any habits you always or never have? | expected | Interview question 5. |
| 358 | Writing prompt 1: tell me about the last time you wrote to your old friend in the city, or something about your week. | expected | The first writing prompt, at about 85 words, follows from the interview answers. |
| 389 | Writing prompt 2: write the short note you'd leave a neighbor about a dog digging in the garden. | expected | A writing prompt at about 165 words, under 300, and it follows from the neighbors mentioned in the interview. |
| 420 | Writing prompt 3: explain to a friend how you'd get through a rainy Saturday, with an honest opinion and a reason. | expected | A writing prompt at about 245 words, under 300. |
| 603 | Does this sound like you? Reply yes, or tell me what's off. | expected | The fixed Step 3 check-in. |
| 961 | What's a short, real message you need to write soon? (three suggestions given) | expected | The task request for the A/B. |
| 1276 | Which sounds more like you? Type A or B. | expected | The fixed A/B question. |
| 1410 | Which one do you want? The project folder is the default. | expected | The install choice. |

## Reviewer notes

All of R1 to R10 pass. Small blemishes that do not fail any item: (1) line 453 shows stray chat text, 'Log Step 2, then find Python.' (2) Line 451 says 'About 330 of 300 words so far'; the measured total was 288, below 300, which the report notes as rough. The model's estimate was high, but it falls under the allowed 'an estimate is fine'. (3) Step 2 ended after 3 prompts on the estimated count, though the true count was 288. (4) The simulated user's role-played share is 24.8%, so the corpus share of 0.752 only just meets the 75% threshold for a reference run. (5) The 'without' draft's sign-off was 'Warmly,' with no name, as required. (6) The Step 5 done line was shown in the install-question message after the pick, which is allowed.

## Sample composition

Words the simulated user typed before the Step 2 done line: 215 from verbatim corpus passages (p12, p6, p10), 71 role-played (interview answers). Corpus share 0.752, which meets the 75% rule for a reference run.
