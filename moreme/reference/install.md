# Installing my-voice (Step 6)

my-voice is a folder with one file, `SKILL.md`. Claude finds it when it sits in a skills folder, or when it is uploaded to claude.ai. Each place is separate: installing in one does not add it to the others.

## Which route

| Route | Where it works | How | Status |
|---|---|---|---|
| Claude Code, project folder (default) | Only in the current project | `PREFIX install moreme-output/my-voice` | The route MoreMe's automated end-to-end test uses, on Windows |
| Claude Code, personal folder | Every project on this computer | `PREFIX install moreme-output/my-voice --personal` | Uses the same install command. Not run end to end by the author's automated tests |
| claude.ai | claude.ai chats, on a paid plan with code execution | Upload `my-voice.zip` | Written from Anthropic's help pages. Not run by the author |

Before asking, show this line word for word: "Project folder: my-voice works only in this project. Personal folder: it works in every project."

When you give the claude.ai steps, add one sentence: "These steps come from Anthropic's help pages, and MoreMe's author has not tested them on claude.ai." Do not call any route tested or verified beyond the status column.

## What install does

- Project folder: copies `moreme-output/my-voice/` to `.claude/skills/my-voice/` inside the current project.
- Personal folder: copies it to the `.claude/skills/my-voice/` folder in the user's home folder. The script finds the right place on Windows, macOS, and Linux. The user copies nothing by hand.
- It checks the skill first and refuses a broken one.
- It never overwrites an existing my-voice unless `--replace` is given.

## Reading the result

| Output | What to do |
|---|---|
| `"ok": true, "installed": "<folder>"` | Glob for `SKILL.md` in that folder to confirm it. Then explain how to check it works |
| `"ok": false, "reason": "project_is_home"` | Claude Code is open in the home folder, so the project folder is the personal folder. Say: "Claude Code is open in your home folder, so this project folder is also your personal skills folder. Choose the personal folder instead, and my-voice will work in every project." On yes, run the `--personal` command. Do not retry the same command |
| Exit 2, my-voice already exists | Ask once: "You already have a my-voice skill there. Replace it with the new one?" Yes: same command plus `--replace`. No: leave it; the new skill stays in `moreme-output/my-voice/` |
| Exit 2, the skill failed its check | Go back to Step 4 and run `build-skill` again. Do not edit `my-voice/SKILL.md` |
| Exit 2, any other message (including a safety guard message) | Tell the user the reason in one plain sentence. Do not copy the files another way. Offer the manual steps below |

## claude.ai upload steps

claude.ai needs a paid plan with code execution turned on.

1. Download `my-voice.zip` (in Claude Code it is in `moreme-output/`; on claude.ai, Claude offers it as a file to download).
2. In claude.ai, open Settings, then Features (in some versions this page is called Capabilities).
3. Find the Skills section and choose to upload a skill.
4. Upload `my-voice.zip` as it is. Do not unzip it or zip it again.
5. Make sure the my-voice skill is turned on.
6. Start a new chat and ask for a short draft.

On claude.ai itself, offer the zip as a download in the way the environment supports, for example by saving a copy to the outputs folder it provides. If there is no zip (the no-Python path), the user zips the `my-voice` folder: on Windows, right-click it and choose "Compress to ZIP file"; on a Mac, right-click and choose "Compress".

## Manual steps (other apps, or when install is blocked)

- Claude Code by hand: copy the folder `moreme-output/my-voice` into `<your project>/.claude/skills/` (project) or into `.claude/skills` inside your home folder (personal). Create the `skills` folder if it is not there. The result must be `.../skills/my-voice/SKILL.md`.
- Another app that supports Claude skills: follow its instructions for adding a skill folder or zip, and use `moreme-output/my-voice/` or `my-voice.zip`.

Log `route=manual` when the user takes these steps themselves.

## How to check it works

- Claude Code: start a new session (in this project for the project folder, or any project for the personal folder) and ask for a short draft, like an email to a friend. Claude should load my-voice on its own. If a draft doesn't sound like you, say "use my-voice".
- claude.ai: start a new chat and ask for a draft. If it does not seem to use your voice, say "use my-voice".
- To change the skill later, run MoreMe again with new samples and replace the old one.
