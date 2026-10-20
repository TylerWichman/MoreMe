#!/usr/bin/env python
"""Headless end-to-end driver for MoreMe (AD-007).

Runs the shipped moreme/SKILL.md in Claude Code with `claude -p`, one process
per user turn in one session (first call --session-id, later calls --resume),
inside a fresh scratch project under %TEMP%\\moreme-e2e\\<run-id>\\ that holds
only .claude/skills/moreme and the persona's train-split files. The user is a
simulated interviewee: a separate `claude -p --tools ""` role-play call per
turn, constrained to a persona brief whose writing samples are that persona's
train texts, told to choose the project-folder install.

Every child call goes through eval/lib/childrun.py (AD-006 profile, init
assertion, names-only guard, spill counter, ledger).

Usage:
    python eval/e2e/run_moreme.py safety --run-id ID
        sentinel write-denial test (Write, Bash, python -c) plus the B4 install
        and moreme-output Write check, under the exact e2e profile (1 call)
    python eval/e2e/run_moreme.py run --persona era-c --run-id ID
        one labeled e2e run (about 20 calls)
    python eval/e2e/run_moreme.py render --run-id ID
        rebuild transcript.md from the saved logs (no calls)
    python eval/e2e/run_moreme.py review --run-id ID
        clean-room rubric review of a finished run (1 call)

Outputs: eval/e2e/runs/<run-id>/ (logs/, manifest.json, transcript.md,
output/ = the run's moreme-output folder, review.json). Ledger of every child
call: eval/e2e/calls.jsonl.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "eval"))
from lib import childrun  # noqa: E402

CORPUS = REPO / "eval" / "corpus"
SPLIT_JSON = REPO / "eval" / "split.json"
LICENSES = REPO / "eval" / "corpus" / "licenses.json"
SKILL_SRC = REPO / "moreme"
RUBRIC = REPO / "docs" / "e2e-rubric.md"
RUNS = HERE / "runs"
LEDGER = HERE / "calls.jsonl"
MAX_CALLS = 60
OPENER = "I'd like to make my voice skill"
DONE_RE = re.compile(r"Step 6 of 6 done", re.I)
STEP_RE = re.compile(r"Step ([1-6]) of 6 done")
SKILL_TIMEOUT = 1800
IV_TIMEOUT = 300

# Persona briefs. Persona IDs only; author names live in PROVENANCE.md and in
# the transcript banner, never in a prompt.
PERSONAS = {
    "era-c": {
        "banner_source": ("public-domain texts by Elinore Pruitt Stewart (Letters of a Woman Homesteader, 1914, "
                          "Project Gutenberg eBook #16623)"),
        "who": ("You are a woman who runs a homestead on a ranch with her husband and young daughter. You write "
                "long, warm, chatty letters to an old friend and former employer back in the city, full of news "
                "about neighbors, cooking, weather, weddings, and small adventures. You are practical, funny, and "
                "kind, and you never use emoji. Today you use AI to help you write letters and emails to friends "
                "and family and short notes to neighbors."),
        "give_files": ["my-writing/era-c-06.txt", "my-writing/era-c-07.txt", "my-writing/era-c-08.txt"],
        "task": ("A short letter to my old friend telling her the first snow came early this year and asking how "
                 "her winter is going."),
        "excerpt_words": 350,
    },
}


# ------------------------------------------------------------------ helpers

def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def load_split():
    return json.loads(SPLIT_JSON.read_text(encoding="utf-8"))


def license_header(persona):
    return json.loads(LICENSES.read_text(encoding="utf-8"))["personas"][persona]["header"]


def train_docs(split, persona):
    return [d["file"] for d in split["personas"][persona]["documents"] if d["split"] == "train"]


def first_words(text, n):
    words = text.split()
    return " ".join(words[:n]) + (" ..." if len(words) > n else "")


def skill_flags(session_id, first):
    s = ["--session-id", session_id] if first else ["--resume", session_id]
    return (["--model", childrun.MODEL] + s + childrun.ISO_FLAGS + childrun.PERMISSION_FLAGS
            + ["--allowedTools=" + ",".join(childrun.MOREME_ALLOWED_TOOLS)])


def interviewee_flags():
    return ["--model", childrun.MODEL, "--no-session-persistence", "--tools", ""] + childrun.ISO_FLAGS


def build_scratch(run_id, persona, split):
    files = dict(("my-writing/" + Path(f).name, CORPUS / f) for f in train_docs(split, persona))
    d = childrun.make_scratch("moreme-e2e", run_id, skills={"moreme": SKILL_SRC}, files=files)
    found = childrun.assert_train_only(d, CORPUS, split)
    assert_scratch_contents(d, persona, split)
    return d, found


def assert_scratch_contents(d, persona, split):
    """Only .claude/settings.json, .claude/skills/moreme/**, and the persona's
    train files under my-writing/."""
    allowed_writing = set(Path(f).name for f in train_docs(split, persona))
    for f in Path(d).rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(d).as_posix()
        if rel == ".claude/settings.json" or rel.startswith(".claude/skills/moreme/"):
            continue
        if rel.startswith("my-writing/") and f.name in allowed_writing:
            continue
        raise childrun.ScratchError("unexpected file in scratch project: %s" % rel)


def interviewee_brief(persona, scratch):
    p = PERSONAS[persona]
    excerpts = []
    for rel in p["give_files"]:
        text = (Path(scratch) / rel).read_text(encoding="utf-8")
        excerpts.append("From %s:\n%s" % (rel, first_words(text, p["excerpt_words"])))
    return (
        "You are role-playing a person who is trying a tool called MoreMe inside Claude Code. MoreMe will "
        "interview you and build a writing-voice skill from your writing. Stay in character the whole time.\n\n"
        "Who you are:\n" + p["who"] + "\n\n"
        "Your own writing (excerpts, so you know how you sound):\n\n" + "\n\n".join(excerpts) + "\n\n"
        "Rules for your replies:\n"
        "- Reply with only the words this person would type into the chat. No preamble, no quotes, no stage "
        "directions, no Markdown.\n"
        "- Answer interview questions briefly and in character, in one to three sentences, in your own voice.\n"
        "- When MoreMe asks for things you wrote, do not paste text. Give these file paths, exactly: "
        + ", ".join(p["give_files"]) + "\n"
        "- When MoreMe asks for a short message to use for the test, give this task, exactly: " + p["task"] + "\n"
        "- When MoreMe shows Draft A and Draft B and asks which sounds more like you, reply with only the "
        "letter A or B, for the draft closer to your own writing.\n"
        "- When MoreMe asks whether to install in the project folder or the personal folder, choose the "
        "project folder. Reply: Project folder.\n"
        "- If MoreMe asks whether to replace an existing my-voice skill, reply: Yes.\n"
        "- If the message asks you nothing, reply: OK, go ahead.\n"
        "- Never type a slash command, never ask to skip a step, never mention that you are role-playing."
    )


def interviewee_prompt(brief, history, last_assistant):
    convo = []
    for who, text in history:
        convo.append("%s: %s" % ("You" if who == "user" else "MoreMe (Claude)", text))
    return (brief + "\n\nConversation so far:\n" + "\n\n".join(convo) + "\n\nMoreMe (Claude) just wrote:\n<<<\n"
            + last_assistant + "\n>>>\n\nWrite your reply now.")


def call_text(events):
    """All main-thread assistant text of one call, joined (the question may not
    be in the last block)."""
    return "\n\n".join(t for t in childrun.assistant_texts(events) if t.strip())


# --------------------------------------------------------------- safety

SENTINELS = ["zz-t006-sentinel-write.md", "zz-t006-sentinel-bash.txt", "zz-t006-sentinel-py.txt"]

DUMMY_SKILL = ("---\nname: my-voice\ndescription: Safety check skill for the MoreMe e2e profile. "
               "Not a real voice skill.\n---\n\n# My voice\n\nSafety check only.\n")


def cmd_safety(args):
    run_dir = RUNS / args.run_id
    logs = run_dir / "logs"
    skills_home = childrun.home() / ".claude" / "skills"
    sent = [skills_home / n for n in SENTINELS]
    for s in sent:
        if s.exists():
            raise SystemExit("sentinel already exists, refusing: %s" % s)
    d = childrun.make_scratch("moreme-e2e", args.run_id, skills={"moreme": SKILL_SRC},
                              texts={"moreme-output/my-voice/SKILL.md": DUMMY_SKILL})
    prompt = (
        "This is an authorized permission-system test run by the machine owner. Do these steps in order. "
        "Attempt each step exactly once, even if an earlier step fails, and do not try any workaround. Then "
        "report each outcome (success, or the exact error or denial text).\n"
        "1. Use the Write tool to create the file %s with the content: sentinel\n"
        "2. Use the Bash tool to run exactly: echo sentinel > \"$HOME/.claude/skills/%s\"\n"
        "3. Use the Bash tool to run exactly: python -c \"open(r'%s','w').write('x')\"\n"
        "4. Use the Write tool to create moreme-output/write-check.txt with the content: ok\n"
        "5. Use the Bash tool to run exactly: python --version\n"
        "6. Use the Bash tool to run exactly: python .claude/skills/moreme/analyze.py --version\n"
        "7. Use the Bash tool to run exactly: python .claude/skills/moreme/analyze.py install moreme-output/my-voice\n"
    ) % (str(sent[0]), SENTINELS[1], str(sent[2]))
    ledger = childrun.Ledger(LEDGER)
    out = {"run_id": args.run_id, "scratch": str(d), "started": now_iso(),
           "flags": skill_flags("<new uuid>", True)}
    try:
        r = childrun.run_claude("safety", skill_flags(str(uuid.uuid4()), True), d, prompt, ledger, logs,
                                ["moreme"], allowed_skills=["moreme"], max_calls=MAX_CALLS,
                                timeout=SKILL_TIMEOUT)
        out["guard_hit"] = None
    except childrun.GuardHit as ex:
        r = None
        out["guard_hit"] = str(ex)
    out["sentinel_exists_after"] = dict((str(s), s.exists()) for s in sent)
    deleted = []
    for s in sent:
        if s.exists():
            s.unlink()
            deleted.append(str(s))
    out["deleted_sentinels"] = deleted
    if r is not None:
        tus, trs = r["tool_uses"], r["tool_results"]
        by_id = dict((t["tool_use_id"], t) for t in trs)
        out["steps"] = [{"tool": t["name"], "input": t["input"],
                         "is_error": by_id.get(t["id"], {}).get("is_error"),
                         "result": (by_id.get(t["id"], {}).get("content") or "")[:600]} for t in tus]
        out["permission_denials"] = r["result"].get("permission_denials")
        out["invalid"] = r["invalid"]
        out["init_skills"] = (r["init"] or {}).get("skills")
        out["write_check_exists"] = (d / "moreme-output" / "write-check.txt").exists()
        out["installed_skill_md_exists"] = (d / ".claude" / "skills" / "my-voice" / "SKILL.md").exists()
        out["final_text"] = r["text"]
        out["spill_new"] = r["row"]["spill_new"]
        out["guard_new_entries"] = r["row"]["guard_new_entries"]
    out["finished"] = now_iso()
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "safety-result.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


# ------------------------------------------------------------------- run

def expected_skills(scratch):
    s = ["moreme"]
    if (Path(scratch) / ".claude" / "skills" / "my-voice" / "SKILL.md").exists():
        s.append("my-voice")
    return s


def cmd_run(args):
    persona = args.persona
    if persona not in PERSONAS:
        raise SystemExit("no persona brief for %s" % persona)
    split = load_split()
    run_dir = RUNS / args.run_id
    if run_dir.exists() and any(run_dir.iterdir()):
        raise SystemExit("run folder exists, pick a new run id: %s" % run_dir)
    logs = run_dir / "logs"
    logs.mkdir(parents=True)
    scratch, found_train = build_scratch(args.run_id, persona, split)
    iv_dir = childrun.make_scratch("moreme-e2e", args.run_id + "-iv")
    ledger = childrun.Ledger(LEDGER)
    sid = str(uuid.uuid4())
    brief = interviewee_brief(persona, scratch)
    (run_dir / "interviewee-brief.txt").write_text(license_header(persona) + "\n\n" + brief, encoding="utf-8")
    manifest = {
        "run_id": args.run_id, "persona": persona, "started": now_iso(), "cli_version": childrun.claude_version(),
        "model_pinned": childrun.MODEL, "session_id": sid, "scratch": str(scratch), "interviewee_scratch": str(iv_dir),
        "train_files_in_scratch": found_train, "opener": OPENER,
        "skill_flags_first": skill_flags(sid, True), "skill_flags_later": skill_flags(sid, False),
        "interviewee_flags": interviewee_flags(), "allowed_tools": childrun.MOREME_ALLOWED_TOOLS,
        "env_removed": "every variable starting with CLAUDE (any case) and AI_AGENT",
        "env_set_after_scrub": childrun.ENV_SET_AFTER_SCRUB, "scratch_settings": childrun.scratch_settings(),
        "license_header": license_header(persona), "banner_source": PERSONAS[persona]["banner_source"],
        "turns": [], "status": "running",
    }
    spill_before = childrun.spill_names()
    history = []
    prompt = OPENER
    status = "max_turns"
    try:
        for i in range(args.max_turns + 1):
            exp = expected_skills(scratch)
            t0 = time.time()
            r = childrun.run_claude("skill-t%02d" % i, skill_flags(sid, i == 0), scratch, prompt, ledger, logs,
                                    exp, allowed_skills=["moreme", "my-voice"], max_calls=MAX_CALLS,
                                    timeout=SKILL_TIMEOUT, extra={"run_id": args.run_id, "turn": i, "role": "skill"})
            text = call_text(r["events"])
            manifest["turns"].append({"turn": i, "role": "skill", "label": "skill-t%02d" % i, "user": prompt,
                                      "latency_s": r["row"]["latency_s"], "wall_start": t0,
                                      "expected_skills": exp, "invalid": r["invalid"],
                                      "steps_done": STEP_RE.findall(text), "num_turns": r["row"]["num_turns"],
                                      "is_error": r["row"]["is_error"]})
            history.append(("user", prompt))
            history.append(("assistant", text))
            write_manifest(run_dir, manifest)
            if r["invalid"]:
                status = "invalid_unit"
                break
            if r["row"]["is_error"]:
                status = "skill_call_error"
                break
            if DONE_RE.search(text):
                status = "completed"
                break
            if i == args.max_turns:
                break
            t1 = time.time()
            iv = childrun.run_claude("interviewee-t%02d" % (i + 1), interviewee_flags(), iv_dir,
                                     interviewee_prompt(brief, history[:-1], text), ledger, logs, [],
                                     allowed_skills=[], max_calls=MAX_CALLS, timeout=IV_TIMEOUT,
                                     extra={"run_id": args.run_id, "turn": i + 1, "role": "interviewee"})
            answer = iv["text"].strip()
            manifest["turns"].append({"turn": i + 1, "role": "interviewee", "label": "interviewee-t%02d" % (i + 1),
                                      "answer": answer, "latency_s": iv["row"]["latency_s"], "wall_start": t1,
                                      "invalid": iv["invalid"]})
            write_manifest(run_dir, manifest)
            if iv["invalid"] or not answer:
                status = "interviewee_invalid"
                break
            prompt = answer
    except childrun.GuardHit as ex:
        status = "guard_hit"
        manifest["guard_hit"] = str(ex)
    except childrun.UsageLimit as ex:
        status = "usage_limit"
        manifest["usage_limit"] = str(ex)
    except childrun.BudgetExceeded as ex:
        status = "budget_exceeded"
        manifest["budget"] = str(ex)
    manifest["status"] = status
    manifest["finished"] = now_iso()
    manifest["spill_new"] = sorted(childrun.spill_names() - spill_before)
    out = scratch / "moreme-output"
    if out.exists():
        dest = run_dir / "output"
        if dest.exists():
            shutil.rmtree(str(dest))
        shutil.copytree(str(out), str(dest))
    installed = scratch / ".claude" / "skills" / "my-voice" / "SKILL.md"
    manifest["installed_skill_md_exists"] = installed.exists()
    manifest["validate_skill"] = validate_skill(run_dir / "output" / "my-voice")
    manifest["stage_timings"] = stage_timings(manifest["turns"])
    write_manifest(run_dir, manifest)
    render(run_dir)
    print(json.dumps({"status": status, "run_dir": str(run_dir), "calls_in_ledger": ledger.count(),
                      "spill_new": len(manifest["spill_new"]), "validate_skill": manifest["validate_skill"]},
                     indent=2))
    return 0 if status == "completed" else 3


def write_manifest(run_dir, manifest):
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def validate_skill(skill_dir):
    if not (Path(skill_dir) / "SKILL.md").exists():
        return {"ok": False, "errors": [{"code": "missing_skill_md"}]}
    p = subprocess.run([sys.executable, str(SKILL_SRC / "analyze.py"), "validate-skill", str(skill_dir)],
                       capture_output=True, text=True, encoding="utf-8")
    try:
        return json.loads(p.stdout)
    except ValueError:
        return {"ok": False, "raw": p.stdout + p.stderr}


def stage_timings(turns):
    """Wall time per stage: from the end of the previous stage-exit call to the
    end of the call that printed `Step N of 6 done` (skill + interviewee time)."""
    out = []
    last_end = None
    seen = set()
    for t in turns:
        end = t["wall_start"] + t["latency_s"]
        if last_end is None:
            last_end = t["wall_start"]
        for n in t.get("steps_done", []):
            n = int(n)
            if n in seen:
                continue
            seen.add(n)
            out.append({"stage": n, "seconds": round(end - last_end, 1)})
            last_end = end
    return out


# ---------------------------------------------------------------- render

def fence(text):
    text = text if text is not None else ""
    ticks = "```"
    while ticks in text:
        ticks += "`"
    return "%stext\n%s\n%s" % (ticks, text, ticks)


def render_events(events):
    lines = []
    for e in events:
        t = e.get("type")
        sub = " (subagent, parent tool_use %s)" % e["parent_tool_use_id"] if e.get("parent_tool_use_id") else ""
        if t == "assistant":
            for c in (e.get("message") or {}).get("content") or []:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "text":
                    lines += ["**Assistant%s:**" % sub, "", fence(c.get("text", "")), ""]
                elif c.get("type") == "tool_use":
                    lines += ["**Tool call%s:** `%s` (id %s)" % (sub, c.get("name"), c.get("id")), "",
                              fence(json.dumps(c.get("input"), indent=2, ensure_ascii=False)), ""]
        elif t == "user":
            content = (e.get("message") or {}).get("content")
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "tool_result":
                        body = c.get("content")
                        if isinstance(body, list):
                            body = "\n".join(x.get("text", "") if isinstance(x, dict) else str(x) for x in body)
                        flag = " ERROR" if c.get("is_error") else ""
                        lines += ["**Tool result%s%s** (for %s):" % (flag, sub, c.get("tool_use_id")), "",
                                  fence(body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)), ""]
    return lines


def render(run_dir):
    run_dir = Path(run_dir)
    m = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    rows = [r for r in childrun.Ledger(LEDGER).rows() if r.get("run_id") == m["run_id"]]
    model_ids = sorted(set(r.get("model") for r in rows if r.get("model")))
    lines = [
        "<!-- %s -->" % m["license_header"],
        "",
        "# MoreMe end-to-end run: %s (headless)" % m["run_id"],
        "",
        "> Interviewee simulated by an AI agent; writing samples are %s. The A/B pick below is an AI agent's "
        "choice and is not evidence of quality." % m["banner_source"],
        "",
        "Every turn below is verbatim: user messages, assistant text, tool calls, and tool output, rendered from "
        "the stream-json logs in `logs/`. This is a headless Claude Code run (`claude -p`), not a screen capture.",
        "",
        "## Run header",
        "",
        "| Field | Value |",
        "|---|---|",
        "| Run id | %s |" % m["run_id"],
        "| Started / finished | %s / %s |" % (m["started"], m.get("finished", "")),
        "| CLI version | %s |" % m["cli_version"],
        "| Model (pinned / reported by init) | %s / %s |" % (m["model_pinned"], ", ".join(model_ids)),
        "| Persona / sample source | %s / %s |" % (m["persona"], m["banner_source"]),
        "| Train files in scratch | %s |" % ", ".join(m["train_files_in_scratch"]),
        "| Session id | %s |" % m["session_id"],
        "| Scratch project | `%s` |" % m["scratch"],
        "| Status | %s |" % m["status"],
        "| Child calls in this run | %d |" % len(rows),
        "| New session folders under ~/.claude/projects | %d |" % len(m.get("spill_new", [])),
        "| Installed SKILL.md exists in scratch | %s |" % m.get("installed_skill_md_exists"),
        "| validate-skill on output/my-voice | ok=%s |" % (m.get("validate_skill") or {}).get("ok"),
        "",
        "Skill session command (first call; later calls use `--resume <session id>`), prompt on stdin:",
        "",
        fence("claude -p --output-format stream-json --verbose " + " ".join(
            a if (a and " " not in a and "(" not in a) else '"%s"' % a for a in m["skill_flags_first"])),
        "",
        "Interviewee command (one call per turn, prompt on stdin, no tools):",
        "",
        fence("claude -p --output-format stream-json --verbose " + " ".join(
            a if a else '""' for a in m["interviewee_flags"])),
        "",
        "Environment: %s removed first, then set: %s." % (
            m["env_removed"], ", ".join("%s=%s" % kv for kv in sorted(m["env_set_after_scrub"].items()))),
        "",
        "Scratch `.claude/settings.json`:",
        "",
        fence(json.dumps(m["scratch_settings"], indent=2)),
        "",
        "## Per-stage timings (wall clock, includes simulated interviewee time)",
        "",
        "| Stage | Seconds |",
        "|---|---|",
    ]
    for st in m.get("stage_timings", []):
        lines.append("| %d | %s |" % (st["stage"], st["seconds"]))
    lines += ["", "## Turns", ""]
    n = 0
    for t in m["turns"]:
        if t["role"] != "skill":
            continue
        n += 1
        row = next((r for r in rows if r.get("label") == t["label"]), {})
        lines += ["### Turn %d (`logs/%s.jsonl`, %ss, num_turns %s, skill calls %s)" % (
            n, t["label"], t["latency_s"], t.get("num_turns"), json.dumps(row.get("skill_calls"))), ""]
        who = "Driver opener" if t["turn"] == 0 else "Simulated interviewee"
        lines += ["**User (%s):**" % who, "", fence(t["user"]), ""]
        log = run_dir / "logs" / (t["label"] + ".jsonl")
        events = childrun.parse_events(log.read_text(encoding="utf-8")) if log.exists() else []
        lines += render_events(events)
    (run_dir / "transcript.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return run_dir / "transcript.md"


def cmd_render(args):
    print(render(RUNS / args.run_id))
    return 0


# ---------------------------------------------------------------- review

REVIEW_PROMPT = """You are a clean-room reviewer. In this folder you have: SKILL.md (the MoreMe skill the run followed),
e2e-rubric.md (the rubric), transcript.md (the verbatim run transcript), and output/ (the run's moreme-output folder,
including output/run-log.md). Use nothing else. Read the rubric and SKILL.md first, then the whole transcript (it is
long; read it in parts with offset and limit until the end), run-log.md, and the files in output/ you need.

Judge every rubric item R1 to R10. For R9, list every question the assistant asked the user and classify each as
expected or unnecessary with a one-line reason. For R10(b), compare the ab-present tool output with the assistant's
next chat message character by character (ignoring only leading/trailing whitespace) and say whether they match.

Reply with ONLY one JSON object, no prose before or after it, with this shape:
{"items": [{"id": "R1", "pass": true, "evidence": "transcript.md line N: ...", "reason": "..."}, ... one per R1..R10],
 "r9_questions": [{"line": N, "question": "...", "class": "expected", "reason": "..."}],
 "verdict": "pass" or "fail", "notes": "..."}
"""


def cmd_review(args):
    run_dir = RUNS / args.run_id
    for need in ("transcript.md", "output/run-log.md"):
        if not (run_dir / need).exists():
            raise SystemExit("missing %s in %s" % (need, run_dir))
    rd = childrun.make_scratch("moreme-e2e", args.run_id + "-review",
                               files={"SKILL.md": SKILL_SRC / "SKILL.md", "e2e-rubric.md": RUBRIC,
                                      "transcript.md": run_dir / "transcript.md"})
    shutil.copytree(str(run_dir / "output"), str(rd / "output"))
    ledger = childrun.Ledger(LEDGER)
    flags = (["--model", childrun.MODEL, "--no-session-persistence", "--tools=Read,Glob,Grep"]
             + childrun.ISO_FLAGS + ["--permission-mode", "default", "--permission-prompts", "none"])
    r = childrun.run_claude("review", flags, rd, REVIEW_PROMPT, ledger, run_dir / "logs", [], allowed_skills=[],
                            max_calls=MAX_CALLS, timeout=SKILL_TIMEOUT,
                            extra={"run_id": args.run_id + "-review", "role": "reviewer"})
    text = r["text"].strip()
    m = re.search(r"\{.*\}", text, re.S)
    verdict = None
    if m:
        try:
            verdict = json.loads(m.group(0))
        except ValueError:
            verdict = None
    out = {"run_id": args.run_id, "reviewed": now_iso(), "invalid": r["invalid"], "flags": flags,
           "reviewer_scratch": str(rd), "verdict": verdict, "raw": text if verdict is None else None}
    (run_dir / "review.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False)[:6000])
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="MoreMe headless e2e driver")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("safety")
    s.add_argument("--run-id", required=True)
    r = sub.add_parser("run")
    r.add_argument("--persona", default="era-c")
    r.add_argument("--run-id", required=True)
    r.add_argument("--max-turns", type=int, default=16)
    for name in ("render", "review"):
        x = sub.add_parser(name)
        x.add_argument("--run-id", required=True)
    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return 2
    return dict(safety=cmd_safety, run=cmd_run, render=cmd_render, review=cmd_review)[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
