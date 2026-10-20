# Interview guide (Step 1)

The interview gives MoreMe the things a script cannot measure: what the user writes, who reads it, how they want to sound, and what they dislike in AI drafts. It should take about 3 minutes.

## The five questions

Ask one per message, in this order. Small changes in wording are fine. Do not add questions.

| # | Question | What it feeds |
|---|---|---|
| 1 | What do you mostly use AI to help you write? For example emails, posts, or cover letters. | A/B task suggestions, the "Adjust by channel" section |
| 2 | Who usually reads it? | "How I sound", channel notes |
| 3 | Pick three words for how you want to sound. | "How I sound", Do rules |
| 4 | What bugs you most in drafts AI writes for you? Words, phrases, or habits. | "Avoid words" (single words and short phrases), Don't rules (habits) |
| 5 | Any habits you always or never have? For example sign-offs, emoji, or exclamation marks. | Do and Don't rules |

Before question 1, the first message also gives the plain overview, the time (about 10 minutes), and the permissions sentence from SKILL.md, word for word.

## Follow-ups

At most 2 follow-ups in the whole interview. Ask one only when:

- **An answer is empty or says nothing usable**, like "idk" or "anything". Ask once with an example: "No problem. Is it more like work emails, or posts for social media?"
- **Two answers contradict each other**, like "casual and short" in question 3 and "I always write long formal emails" in question 5. Ask once: "You said casual, and also that you write formal emails. Which should my-voice aim for?"

Do not follow up on short answers that are clear. "My boss" is a full answer to question 2. If a follow-up still gets no clear answer, accept what you have and move on.

The user may answer several questions in one message. Count those as answered and skip ahead. Do not ask them again.

## interview.md format

Write it once, after the last answer. Copy the user's words exactly, typos included.

```
# Interview

## 1. What do you mostly use AI to help you write?
<answer, word for word>

## 2. Who usually reads it?
<answer>

## 3. Three words for how you want to sound
<answer>

## 4. What bugs you most in AI drafts
<answer>

## 5. Habits you always or never have
<answer>

## Follow-ups
<question asked>: <answer>   (or "None")
```

## Turning answers into notes (used in Step 4)

- Question 4 words and short phrases ("synergy", "I hope this finds you well") go under `## Avoid words`, one per line. Habits ("too many bullet points") become Don't lines.
- Question 5 habits become concrete rules: "Sign off with just my first name", "No emoji in work email".
- Question 3 words describe a goal, not a measurement. Pair each with something checkable when you can, for example "direct" becomes "Put the request in the first sentence".
