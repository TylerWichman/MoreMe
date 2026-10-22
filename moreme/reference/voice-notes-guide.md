# Writing voice-notes.md (Step 4)

`moreme-output/voice-notes.md` is the only part of my-voice that Claude writes. `analyze.py build-skill` reads it, checks it, adds the measured numbers, and writes `my-voice/SKILL.md` and `my-voice.zip`. Never write or edit those two yourself.

## Format

Six `##` headings, exactly these, in this order. Text outside them is ignored.

| Heading | What goes there | Count |
|---|---|---|
| `## How I sound` | Plain sentences in the first person, from the interview and the report | 3 to 5 sentences |
| `## Do` | Lines starting with `- `, each concrete and checkable | 5 to 8 lines |
| `## Don't` | Lines starting with `- ` | 3 to 6 lines |
| `## Avoid words` | One word or short phrase per line: the user's pet peeves from interview question 2 | 0 to 20 lines |
| `## Examples` | `[conversation.txt]` on its own line, then an excerpt copied exactly from that file | 3 to 5 excerpts, 40 to 120 words each |
| `## Adjust by channel` | Lines starting `Email:`, `Post:`, `Cover letter:` | 1 to 3 sentences each |

## Writing good notes

- Write as the user ("I keep emails short"), not about them.
- Be specific to this person. "Warm and friendly" alone is useless. "I open with the person's name and get to the point in the first sentence" is useful.
- Do and Don't lines must be things a reader could check in a draft: "Ask at most one question per email", "Sign off with just 'Thanks, Sam'", "No bullet points in emails".
- Names: write the user's name into a sign-off rule only if they gave it in the interview or the chat, or signed their samples with it. Never take it from a username, a folder path, or system details. Without a known name, describe the sign-off without one, for example "Sign off with just 'Thanks,'".
- Read the `## Check-in after the report` answer in `interview.md`. If the user said something is off, reflect it in How I sound, Do, or Don't. Never change or argue with the measured numbers.
- You may use the report's numbers in plain words ("Most of my sentences are 8 to 15 words"). Do not invent numbers.
- Pet-peeve words go only under Avoid words, never in Don't. The skill adds its own line telling Claude to avoid that list.
- Your own text (every section except Examples and Avoid words) must not contain long dashes or hype words. Write plainly.
- Channel lines: if the user never writes one of the three channels, still write one sentence, for example "Cover letter: Same voice, a little more formal, still short sentences."

## Copying excerpts exactly

`build-skill` checks that each excerpt appears word for word in the named file, `samples/conversation.txt`. To pass:

- Read `conversation.txt` first and copy from it, not from your memory of the chat.
- Keep every character: typos, capital letters, punctuation, emoji, spacing.
- Copy one continuous stretch. Do not join pieces from different places or add "..." for skipped text.
- If no single answer reaches 40 words, an excerpt may run across two answers next to each other, copied exactly, blank line included.
- Stay inside one paragraph when you can. Line breaks inside an excerpt must match the file.
- Aim for 60 to 100 words so small counting differences do not push you outside 40 to 120.
- Pick excerpts that show the user's habits: a typical opening, a sign-off, a sentence with their usual punctuation. Use different answers when you can; the longest answers work best.

## Example

```
## How I sound
I write short, friendly emails and get to the point fast. I sound like I'm talking to a coworker I like. I use contractions and keep sentences under 20 words. I almost never use exclamation marks.

## Do
- Put the main request or news in the first sentence.
- Use contractions like I'm, don't, and we'll.
- Keep most sentences between 8 and 15 words.
- Open with "Hi <name>," and sign off with "Thanks, Sam".
- Use plain words a coworker would say out loud.

## Don't
- No bullet points in emails.
- Don't apologize for writing ("Sorry to bother you").
- Don't end with "Let me know if you have any questions."

## Avoid words
circle back
synergy
I hope this email finds you well

## Examples
[conversation.txt]
<60 to 100 words copied exactly from one answer>
[conversation.txt]
<60 to 100 words copied exactly from another answer>
[conversation.txt]
<60 to 100 words copied exactly from a third answer>

## Adjust by channel
Email: Two or three short paragraphs. First name in the greeting.
Post: One short paragraph, a bit looser. One emoji at most.
Cover letter: Same plain voice, a little more formal. Still no long sentences.
```

## build-skill errors and how to fix them

`build-skill` prints `{"ok": false, "errors": [...]}` and writes nothing when something is wrong. Fix `voice-notes.md` and run it again (at most 3 runs in total). Do not ask the user.

| Error code | What it means | Fix |
|---|---|---|
| `notes_section_missing` | A heading is missing or misspelled | Use the six headings exactly as above, with `## ` |
| `notes_count_out_of_range` | Too many or too few sentences, lines, or excerpts in a section | Check the counts table above |
| `excerpt_not_verbatim` | An excerpt is not an exact copy of the named file | Read that sample file again and copy a stretch exactly |
| `excerpt_length` | An excerpt is under 40 or over 120 words | Pick a longer or shorter stretch, about 60 to 100 words |
| `banned_word` | A hype word is in your own text | Replace it with a plain word |
| `em_dash` | A long dash is in your own text | Use a comma, period, colon, or parentheses |
| `forbidden_token` | An internal eval term got into the notes | Remove it |
| `description_too_long`, `body_too_long` | The skill is too long | Shorten How I sound, Do, Don't, and the excerpts |
| `unknown_placeholder` | Text in double curly braces | Remove the curly braces from your notes |
| Other codes | See the message text | Fix what the message names |

After 3 failed runs, tell the user in plain words what is still wrong. See `troubleshooting.md`.

## The default avoid list

`build-skill` adds these to "Words I avoid" for everyone, minus any the user's own samples use, plus the user's own pet peeves. They are the stock words and phrases that make drafts sound machine-written.

<!-- avoid-words:start -->
- seamless, seamlessly
- leverage, leveraging
- unlock
- empower
- game-changer, game changer
- delve
- robust
- elevate
- revolutionize, revolutionary
- cutting-edge
- supercharge
- effortless, effortlessly
- unleash
- transformative
- next-level
- world-class
- best-in-class
- magic, magical
- in today's
- it's worth noting
- dive into
- deep dive
- say goodbye to
- whether you're
- look no further
- take your writing to the next level
<!-- avoid-words:end -->

## No-Python path: writing my-voice/SKILL.md by hand

Only when Step 3 found no Python. Read `SKILL_DIR/templates/my-voice/SKILL.md.tmpl` and write `moreme-output/my-voice/SKILL.md` from it:

- Keep the frontmatter, headings, table rows, markers, and fixed lines exactly as in the template.
- Every number cell in "Measured profile": `not measured`. For example `| A typical sentence | not measured |`.
- Replace the "Measured by MoreMe analyze.py ..." line with: `Not measured: Python was not available. These notes are estimated by Claude from N words on YYYY-MM-DD.`
- `{{notes.how_i_sound}}`, `{{notes.do}}`, `{{notes.dont}}`, `{{notes.channels}}`: the matching sections of your notes.
- `{{notes.examples}}`: each excerpt as a line `From conversation.txt:`, then the excerpt exactly, with a blank line between excerpts.
- `{{notes.avoid_words}}`: the default list above, one item per line starting with `- ` (leave out any the user's samples use), then the user's own pet peeves.
- `{{rules.dash_line}}`: "Do not use long dashes. Use commas, periods, colons, or parentheses instead." If the samples clearly use long dashes, write "Long dashes are fine. My samples use them." instead.
- `{{meta.moreme_version}}`: `v1.0.0`. `{{meta.date}}`: today's date.
- No placeholder in double curly braces may be left in the file.

Tell the user there is no zip this time, so the claude.ai upload needs them to zip the `my-voice` folder themselves (steps in `install.md`).
