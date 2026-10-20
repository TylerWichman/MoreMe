# Samples and analysis (Steps 2 and 3)

## What counts as a sample

- Something the user wrote themselves: emails, messages, posts, cover letters, essays, notes.
- Each piece is saved as its own file, `moreme-output/samples/sample-01.txt` and up, numbered in the order received.
- Save the text exactly as the user wrote it. Keep typos, line breaks, emoji, and odd spacing. Those are part of how they write.
- If one paste holds several pieces separated by `---` or clear breaks (different greetings and sign-offs), save each piece as its own file.
- Leave out things that are not the user's words when they are obvious and separate: a quoted email they replied to, a forwarded header, a signature block with phone numbers. If you are unsure, keep the text.
- Text written mostly by AI is a weak sample. If the user says a piece was AI-drafted, ask once whether they have something they wrote alone. If not, keep it.

### File paths (Claude Code)

- Read each file with the Read tool and save its text as a sample. Plain text (`.txt`), Markdown (`.md`), and PDF files work.
- Word files (`.docx`), Pages files, and images: ask the user to open the file and paste the text instead. Do not try to convert them with a command.
- A folder path: ask which files in it are theirs, or take up to 10 text files from it.

## Word counts

- Floor: 3 pieces and 300 words in total.
- Under 1,000 words: the numbers will be rough. Say so once.
- 1,000 words or more: steadier numbers. There is no upper limit, but 5 to 10 pieces is plenty.
- In Step 2 your count is an estimate. In Step 3 the script gives the real count in `profile.json` (`word_count`). If the real count is under 300, say the numbers are very rough and continue.

## Python discovery (Step 3)

The order matters. On Windows, `python3` often opens a Microsoft Store page instead of running Python, so it is tried last and only if both other probes failed.

| Probe | Works when the output shows | Counts as failed when |
|---|---|---|
| `python --version` | `Python 3.8` or higher | command not found, empty output, a Store message, Python 2.x or 3.7 and older |
| `py -3 --version` | same | same (the `py` launcher exists only on Windows) |
| `python3 --version` | same, and only tried if both above failed | same |

Then confirm with `<probe without --version> SKILL_DIR/analyze.py --version`. It prints JSON like `{"analyze_version": "1.0.0", "schema_version": "1", "python": "3.11.9", ...}`. If this fails, try the next probe.

Never install Python, open the Store, change settings, or try other commands. If nothing works, use the no-Python path below and tell the user in one sentence. In the closing message you can add: "If you install Python 3.8 or newer later, run MoreMe again to get measured numbers."

## Explaining the report

`report.txt` is already in plain words. Show it as it is, then add one or two sentences that link it to the interview, for example: "You said you want to sound direct. Your typical sentence is 11 words, which fits that."

- Do not add numbers the report does not show.
- If the report lists warnings (little text, odd characters in a file), repeat the main one in plain words.
- `metrics-glossary.md` explains each number if the user asks.

## No-Python estimate

When no Python works, say so in one sentence, for example: "I couldn't find Python on this computer, so I'll describe your style by reading your samples instead. These notes are estimated by Claude, not measured." Then read the samples and write `moreme-output/report.txt` yourself:

```
Estimated by Claude, not measured

Sentence length: <short / medium / long, with a rough typical length in words>
Paragraphs: <short or long, how many sentences>
Punctuation: <commas, exclamation marks, questions, dashes: often, sometimes, rarely>
Contractions: <often or rarely uses words like I'm and don't>
Tone: <one or two sentences>
Other habits: <greetings, sign-offs, emoji, capital letters>
```

Every line is a description, not a measurement. Do not write numbers with decimals. The run log gets `status=degraded reason=no_python`. Show this report in the Step 3 report message with the same check-in question.
