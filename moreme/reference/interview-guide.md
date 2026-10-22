# Interview guide (Step 1)

The interview gives MoreMe two things a script cannot measure: what the user writes with AI, and what they dislike in AI drafts. It takes about a minute. Everything else comes from how they type in Step 2.

## The two questions

Ask one per message, in this order. Small changes in wording are fine. Do not add questions.

| # | Question | What it feeds |
|---|---|---|
| 1 | What do you mostly use AI to help you write? For example emails, posts, or cover letters. | A/B task suggestions, the "Adjust by channel" section |
| 2 | What bugs you most in drafts AI writes for you? Words, phrases, or habits. | "Avoid words" (single words and short phrases), Don't rules (habits) |

Before question 1, the first message also gives the plain overview, the time (about 12 to 15 minutes), and the permissions sentence from SKILL.md, word for word. It also says everything the user types counts as writing, so they should type the way they normally do.

The two answers are the start of the writing sample. After the second one, save them (the user's words only) to `moreme-output/samples/conversation.txt`; Step 2 adds to that file (see `samples-and-analysis.md`).

## Follow-ups

At most 1 follow-up in the interview, and only when an answer is empty or says nothing usable, like "idk" or "anything". Ask once with an example: "No problem. Is it more like work emails, or posts for social media?" If it still gets no clear answer, accept what you have and move on.

The user may answer both questions in one message. Count both as answered. Do not ask again.

## interview.md format

Write it once, after the second answer. Copy the user's words exactly, typos included.

```
# Interview

## 1. What do you mostly use AI to help you write?
<answer, word for word>

## 2. What bugs you most in AI drafts
<answer>

## Follow-ups
<question asked>: <answer>   (or "None")
```

After the Step 3 report, add the user's reply to the check-in question ("Does this sound like you? Reply yes, or tell me what's off.") at the end of the file, word for word:

```
## Check-in after the report
<answer>
```

## Turning answers into notes (used in Step 4)

- Question 2 words and short phrases ("synergy", "I hope this finds you well") go under `## Avoid words`, one per line. Habits ("too many bullet points") become Don't lines.
- Habits the user shows in Step 2 (sign-offs, emoji, exclamation marks, how they open) become concrete Do and Don't rules, for example "Sign off with just my first name".
- The check-in answer: if the user says part of the report is off ("I use more questions than that"), put the correction into How I sound, Do, or Don't. It never changes the measured numbers, which come from analyze.py. A plain "yes" changes nothing.
