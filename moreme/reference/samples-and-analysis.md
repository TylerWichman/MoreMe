# Samples and analysis (Steps 2 and 3)

## The sample is the conversation

MoreMe never asks for existing writing, pasted text, or files. The sample is what the user types in this chat:

- The two interview answers count. They are saved first.
- Then a conversation about a topic the user cares about: 4 to 7 answers (at most 10 questions), until the running total is about 300 words.
- Everything goes in one file, `moreme-output/samples/conversation.txt`: the user's words only, in order, word for word, a blank line between answers. Never add your prompts, labels, or fixes. Keep typos, line breaks, emoji, and odd spacing; they are part of how the user types.
- Every answer counts as the user's writing. Never ask whether they wrote it or where it came from; save it as typed.

## Finding a topic and following it

People type more, and more like themselves, about things they care about. So Step 2 starts by finding a topic, then keeps the user talking about it.

- **Openers.** Offer three, and let the user answer any of them or name their own: a team, hobby, show, or place they could talk about forever; something they changed their mind about lately; the best or worst thing that happened this week.
- **Follow-ups come from what they just said.** Pick one specific detail and ask about it. If they write about their baseball team's bullpen: "Who would you trade for, and why?" If they mention a trip: "What went wrong first?" Ask why, what happened next, what they would change, or how they would explain it to a friend.
- **Keep it a conversation.** One short, friendly question per message. React briefly to what they said only if it helps the next question; never praise or grade their writing.
- **When a thread runs dry.** Two short answers in a row: offer a different opener.

Start each question with the running total, for example "About 180 of 300 words so far." Interview answers count. Do not nag about length.

## Word counts

- Target: about 300 words in total, interview answers included. That is the floor for steady enough numbers.
- 300 to 1,000 words: the numbers are rough. The report says so; repeat it once in plain words.
- Your running count is an estimate. In Step 3 the script gives the real count in `profile.json` (`word_count`). If the real count is under 300, say the numbers are very rough and continue.
- The user wants to stop early: one sentence that fewer words make the measurement less reliable, and one more question offered. If they still want to stop, continue with what you have (`status=degraded reason=user_stopped_early`).

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

When no Python works, say so in one sentence, for example: "I couldn't find Python on this computer, so I'll describe your style by reading your answers instead. These notes are estimated by Claude, not measured." Then read `conversation.txt` and write `moreme-output/report.txt` yourself:

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
