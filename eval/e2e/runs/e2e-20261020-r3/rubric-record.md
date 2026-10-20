<!-- Corpus-derived content (persona era-c). Source texts are in the public domain in the USA. Sources: eval/corpus/PROVENANCE.md -->

# Rubric record: e2e-20261020-r3

> Home folder path replaced with ~ by tools/sanitize_artifacts.py (the OS user name, personal names, and email addresses are also replaced: [user], [name], [email]).

Status: incomplete, scored fail without a reviewer call. The driver stopped at the ledger-wide call cap (60) after 17 calls, at the blind A/B pick, so stages 5 and 6 never ran. The cap is now per driver command (30).

Run with SKILL.md from commit df27331 (T-012). Persona era-c, invented first name Hattie, model claude-sonnet-5-5, CLI 2.1.303, flags as in `transcript.md` and `manifest.json`.

Mechanical chat-visibility cross-check (`manifest.json`), confirmed by reading `transcript.md`:

| Stage | Opening line | Done line | Result shown |
|---|---|---|---|
| 1 | NO: Skill, then Glob and Write of `.gitignore` before any chat text; the first chat text is question 1 | yes | n/a |
| 2 | yes (after the Step 1 done line) | NO | word count: NO (none in chat; the mechanical check reads true only because stage 2 never closed and the Step 4 summary mentions 17 words) |
| 3 | NO separate line; stages 2 to 4 ran as 13 tool calls with no chat text | NO | report: NO (0 of 10 report lines in chat) |
| 4 | no chat text before its tool calls | yes | summary shown |
| 5 | yes | not reached | not reached |
| 6 | not reached | not reached | not reached |

Result: R1 and R3 fail as in r2, and R2 now fails too (no done line). The Step 1 message and the Step 3 report sub-step from T-012 were not followed. 17 calls, 0 invalid units, guard 0 new entries, 1 new session folder.
