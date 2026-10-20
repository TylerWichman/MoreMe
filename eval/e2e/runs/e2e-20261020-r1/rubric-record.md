<!-- Corpus-derived content (persona era-c). Source texts are in the public domain in the USA. Sources: eval/corpus/PROVENANCE.md -->

# Rubric record: e2e-20261020-r1

> Home folder path replaced with ~ by tools/sanitize_artifacts.py (the OS user name, personal names, and email addresses are also replaced: [user], [name], [email]).

Scored against `docs/e2e-rubric.md` (FROZEN 6 plus the orchestrator R9 note) by a clean-room reviewer agent (`claude -p`, tools Read, Glob, Grep only, in a scratch folder holding only SKILL.md, the rubric, the transcript, and the output folder). Raw verdict: `review.json`. Line numbers refer to `transcript.md` in this folder.

| Field | Value |
|---|---|
| Run id | e2e-20261020-r1 |
| Date | 2026-10-20 |
| CLI version | 2.1.303 (Claude Code) |
| Model id | claude-sonnet-5-5 |
| Exact flags | see `transcript.md` header and `manifest.json` (`skill_flags_first`, `skill_flags_later`, `interviewee_flags`) |
| Persona / sample source | era-c / public-domain texts by Elinore Pruitt Stewart (Letters of a Woman Homesteader, 1914, Project Gutenberg eBook #16623) |
| Reviewer flags | `--model claude-sonnet-5-5 --no-session-persistence --tools=Read,Glob,Grep --setting-sources project --strict-mcp-config --permission-mode default --permission-prompts none` |
| Reviewer verdict | pass |

## Items

| Item | Result | Evidence | Reason |
|---|---|---|---|
| R1 | pass | transcript.md lines 114-127, 294-306, 309-315; run-log.md line 1: stage=1 name=interview status=passed check=answers=5,followups=0 | The .gitignore was written first. The five questions were asked one per message (lines 132-194). interview.md was saved with 0 follow-ups. The log line is status=passed and the chat line 'Step 1 of 6 done: Interview.' was shown. |
| R2 | pass | transcript.md lines 322-466 (three Reads, then Writes of sample-01/02/03.txt); line 474 and run-log.md line 2: stage=2 status=passed check=files=3,words_about=3300 | Three sample files were saved and the word total was logged. 3,300 is an estimate against the 3,839 measured, which SKILL.md allows. The floor of 3 pieces and 300 words was met. The chat line 'Step 2 of 6 done: Sample.' and the running word count were never shown, but the rubric's checkable condition (3 or more files, word total logged) is met. |
| R3 | pass | transcript.md lines 496-516: Python 3.11.9, then analyze.py --version printed schema_version '1'. Lines 522-566: profile and report ran with ok:true, and report.txt was read. Line 573 and run-log.md line 3: stage=3 status=passed check=profile_json_schema_1,words=3839 | The first probe worked, the confirm call returned schema_version '1', the profile and report calls exited 0, and the log says passed, not degraded. The chat line 'Step 3 of 6 done: Analysis.' was never shown. The report was also never shown to the user in chat, which SKILL.md requires. Neither is a rubric condition. |
| R4 | pass | transcript.md lines 744-773: voice-notes.md written, then build-skill returned ok:true on run 1. Line 780 and run-log.md line 4: stage=4 status=passed check=build_skill_ok,runs=1. Lines 902-904: 'Step 4 of 6 done: Generate.' | build-skill reached ok:true on the first run. The generated my-voice/SKILL.md was read at lines 963-1070 and my-voice.zip exists in output/. The chat summary of the skill was given. |
| R5 | pass | transcript.md lines 1223-1241: ab-reveal returned picked_arm 'with'. Line 1249 and run-log.md line 5: stage=5 status=passed check=ab_result_json,picked_arm=with. Line 1264: 'Step 5 of 6 done: Blind A/B.' | ab-result.json exists in output/, the reveal ran, and the log says passed. |
| R6 | pass | transcript.md lines 1285-1313: install returned ok:true with route project, and a Glob found .claude\skills\my-voice\SKILL.md. Line 1320 and run-log.md line 6: stage=6 status=passed check=install_ok,route=project. Line 1337: 'Step 6 of 6 done: Install.' | The install exited ok:true, the installed SKILL.md was confirmed by Glob, and the route was logged. The check instructions and the closing note were given. |
| R7 | pass | transcript.md lines 496-516, 535-548, 757-773, 1144-1177, 1228-1241, 1290-1299: every analyze.py call returned JSON or plain output with no Traceback | Every analyze.py call succeeded. Python discovery needed only one probe. build-skill reached ok:true on run 1. No Write or Edit tool call touched my-voice/SKILL.md or my-voice.zip. The profile+report, build-skill, ab-shuffle+ab-present, ab-reveal and install calls all succeeded, though two were chained with &&. |
| R8 | pass | Every tool result in transcript.md lines 78-1340 is a success message or file content. None is an error or a permission denial. | No tool errors and no denials. There were no failed probes and no writes outside the scratch project. |
| R9 | pass | Assistant questions at transcript.md lines 138, 152, 166, 180, 194, 314, 906-912, 1208, 1270 | Every question is one SKILL.md expects, and none was already answered. See r9_questions. |
| R10 | pass | (a) No Read, Glob or print of ab-mapping.json anywhere in the transcript. The Glob at lines 942-950 was for ab-result.json only. (b) Tool output at lines 1154-1176 versus assistant message at lines 1182-1208. (d) Agent prompt at line 1080. | (a) ab-mapping.json was never read before ab-reveal. (b) The next chat message after ab-present is the fixed opening line, then the ab-present output, then 'Which sounds more like you? Type A or B.' The reprint matches the tool output character for character: Draft A is the 'Margaret, Well, the first snow...' letter signed 'Love, [name]', and Draft B is the 'Dear Margaret...' letter signed 'Warmly, [name]'. All blank lines and paragraph breaks are the same. (c) The message has no hints beyond the exempt fixed opening line, and there was no text between it and the pick 'A'. (d) The subagent prompt was exactly the task text, a blank line, the shared rule, a blank line, and 'Do not use any skills.' The reply was saved to draft-without.md, with the harness indentation removed. |

## R9 question list

| Line | Question | Class | Reason |
|---|---|---|---|
| 138 | What do you mostly use AI to help you write? For example emails, posts, or cover letters. | expected | Interview question 1. |
| 152 | Who usually reads it? | expected | Interview question 2. |
| 166 | Pick three words for how you want to sound. | expected | Interview question 3. |
| 180 | What bugs you most in drafts AI writes for you? Words, phrases, or habits. | expected | Interview question 4. |
| 194 | Any habits you always or never have? For example sign-offs, emoji, or exclamation marks. | expected | Interview question 5. |
| 314 | Paste three or more things you wrote yourself, or give file paths (step 2 request). | expected | SKILL.md step 2 asks for the samples. This is the first request, and nothing had been supplied yet. |
| 906 | What's a short real message you need to write soon? (with three suggestions and a 'you pick' option) | expected | The A/B task question that SKILL.md step 5 requires. |
| 1208 | Which sounds more like you? Type A or B. | expected | The fixed A/B pick question. |
| 1270 | Which one do you want? (project folder or personal folder, or upload to claude.ai) | expected | The install choice that SKILL.md step 6 requires. |

## Reviewer notes

All ten items pass on the rubric's stated conditions. Some SKILL.md details were skipped but are not rubric items. The chat lines 'Step 2 of 6 done: Sample.' and 'Step 3 of 6 done: Analysis.' were never shown. The Step 3 opening line was never said. The report.txt contents were never shown to the user with the connecting sentences. The Step 4 opening line was never said. The running word count was not given in Step 2. The post-reveal message also added a note that 'Margaret' and '[name]' were placeholders. That comes after the pick, so it does not affect blindness. The model also chained two commands with && in a few Bash calls, which still matched the allowed prefixes and exited 0.
