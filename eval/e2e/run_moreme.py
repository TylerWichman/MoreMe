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
    python eval/e2e/run_moreme.py export-example --run-id ID
        copy the run's my-voice/SKILL.md to docs/example-run/ with the license
        header (no calls)

Outputs. Committed, sanitized by tools/sanitize_artifacts.py:
eval/e2e/runs/<run-id>/ (manifest.json, transcript.md, interviewee-brief.txt,
review.json, rubric-record.md). Raw evidence, never committed:
<evidence>/e2e/runs/<run-id>/ (logs/, output/ = the run's moreme-output folder)
and the ledger of every child call <evidence>/e2e/calls.jsonl, where <evidence>
is eval/lib/artifacts.evidence_root() (MOREME_EVIDENCE_DIR, else the OneShot
project evidence folder, else <repo>/.evidence).
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
from lib import artifacts, childrun, personas  # noqa: E402

CORPUS = REPO / "eval" / "corpus"
SPLIT_JSON = REPO / "eval" / "split.json"
LICENSES = REPO / "eval" / "corpus" / "licenses.json"
SKILL_SRC = REPO / "moreme"
RUBRIC = REPO / "docs" / "e2e-rubric.md"
RUNS = HERE / "runs"
LEDGER = artifacts.evidence_root() / "e2e" / "calls.jsonl"
MAX_CALLS = 45  # per driver command (one run, one review), counted from the ledger at start
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
        "first_name": personas.persona_first_name("era-c"),
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
    """Scratch project with only .claude/settings.json and .claude/skills/moreme.
    Since AMEND-003 MoreMe never reads the user's files, so no writing files are
    copied in; the interviewee gets its passages from the train split directly.
    Returns (scratch, train files found in it), the second always empty."""
    d = childrun.make_scratch("moreme-e2e", run_id, skills={"moreme": SKILL_SRC})
    found = childrun.assert_train_only(d, CORPUS, split)
    assert_scratch_contents(d, persona, split)
    return d, found


def assert_scratch_contents(d, persona, split):
    """Only .claude/settings.json and .claude/skills/moreme/**."""
    for f in Path(d).rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(d).as_posix()
        if rel == ".claude/settings.json" or rel.startswith(".claude/skills/moreme/"):
            continue
        raise childrun.ScratchError("unexpected file in scratch project: %s" % rel)


# ------------------------------------------------- verbatim passages (AMEND-003)

PASSAGE_MAX_WORDS = 80
SENTENCE_END = re.compile(r"(?<=[.!?])[\"')\]]*\s+")
USE_RE = re.compile(r"^\s*USE:\s*(.+?)\s*$", re.M)


def passage_spans(text, max_words=PASSAGE_MAX_WORDS):
    """(start, end) character spans of passages: whole paragraphs, or runs of
    whole sentences when a paragraph is longer than max_words. Spans never
    cut inside a sentence."""
    spans = []
    for m in re.finditer(r"[^\n]+(?:\n(?!\s*\n)[^\n]+)*", text):
        p_start, para = m.start(), m.group(0)
        if not para.strip():
            continue
        if len(para.split()) <= max_words:
            spans.append((p_start, m.end()))
            continue
        sents = []
        pos = 0
        for s in SENTENCE_END.finditer(para):
            sents.append((pos, s.start() + len(s.group(0).rstrip())))
            pos = s.end()
        if pos < len(para):
            sents.append((pos, len(para)))
        cur_start = None
        cur_words = 0
        for a, b in sents:
            w = len(para[a:b].split())
            if cur_start is not None and cur_words + w > max_words:
                spans.append((p_start + cur_start, p_start + prev_end))
                cur_start, cur_words = None, 0
            if cur_start is None:
                cur_start = a
            cur_words += w
            prev_end = b
        if cur_start is not None:
            spans.append((p_start + cur_start, p_start + prev_end))
    return [(a, b) for a, b in spans if text[a:b].strip()]


def author_words(persona):
    """Words of the real writer's name, from the persona's PROVENANCE author line."""
    text = (CORPUS / "PROVENANCE.md").read_text(encoding="utf-8")
    sec = text.split("## " + persona + "\n", 1)
    if len(sec) < 2:
        return []
    m = re.search(r"^- Author:\s*([^,\n]+)", sec[1], re.M)
    return [w for w in re.findall(r"[A-Za-z]{3,}", m.group(1))] if m else []


def names_author(text, words):
    """True if a passage names the real writer. 'Mr. <surname>' (another
    person, such as a husband) does not count."""
    for w in words:
        for m in re.finditer(r"\b%s\b" % re.escape(w), text):
            if not text[max(0, m.start() - 4):m.start()].endswith("Mr. "):
                return True
    return False


def passage_catalog(persona, split=None):
    """Numbered verbatim passages from the persona's give_files, which must be
    train-split documents, leaving out any passage that names the real writer.
    Each item: id, file (corpus path), start, end, words, text."""
    split = split or load_split()
    avoid = author_words(persona)
    train = dict((Path(f).name, f) for f in train_docs(split, persona))
    out = []
    for rel in PERSONAS[persona]["give_files"]:
        name = Path(rel).name
        if name not in train:
            raise childrun.ScratchError("passage source is not a train document: %s" % rel)
        text = (CORPUS / train[name]).read_text(encoding="utf-8")
        for a, b in passage_spans(text):
            if names_author(text[a:b], avoid):
                continue
            out.append({"id": "p%d" % (len(out) + 1), "file": train[name], "start": a, "end": b,
                        "words": len(text[a:b].split()), "text": text[a:b]})
    return out


def resolve_answer(reply, catalog, used=()):
    """Turn an interviewee reply into the text sent to MoreMe.

    A reply with a line `USE: p3, p7` becomes those passages, verbatim, joined
    by a blank line; returns (text, [provenance], None). A reply without a USE
    line is an in-role answer; returns (reply, None, None). Unknown or reused
    ids return (None, None, error)."""
    m = USE_RE.search(reply or "")
    if not m:
        return (reply or "").strip(), None, None
    ids = re.findall(r"p\d+", m.group(1))
    by_id = dict((c["id"], c) for c in catalog)
    if not ids:
        return None, None, "USE line names no passage id"
    bad = [i for i in ids if i not in by_id]
    if bad:
        return None, None, "unknown passage ids: %s" % ", ".join(bad)
    again = [i for i in ids if i in set(used)]
    if again:
        return None, None, "passages already used: %s" % ", ".join(again)
    chosen = [by_id[i] for i in ids]
    prov = [dict((k, c[k]) for k in ("id", "file", "start", "end", "words")) for c in chosen]
    return "\n\n".join(c["text"].strip() for c in chosen), prov, None


SAMPLE_METHOD = ("Answers to MoreMe's writing prompts are verbatim passages from those texts, picked by the "
                 "simulated interviewee to fit each prompt (whole paragraphs or whole sentences, never reworded); "
                 "answers to interview questions and other replies were written in role by the agent.")


def interviewee_brief(persona, scratch=None, catalog=None):
    p = PERSONAS[persona]
    catalog = catalog if catalog is not None else passage_catalog(persona)
    listing = "\n\n".join("[%s] (%d words)\n%s" % (c["id"], c["words"], c["text"].strip()) for c in catalog)
    return (
        "You are role-playing a person who is trying a tool called MoreMe inside Claude Code. MoreMe will "
        "interview you, ask you to write a few short things, and build a writing-voice skill from your writing. "
        "Stay in character the whole time.\n\n"
        "Who you are:\n" + p["who"] + "\n\n"
        "Your own writing, as numbered passages. These are the only things you ever write for MoreMe:\n\n"
        + listing + "\n\n"
        "Rules for your replies:\n"
        "- Reply with only the words this person would type into the chat. No preamble, no quotes, no stage "
        "directions, no Markdown.\n"
        "- Answer interview questions briefly and in character, in one to three sentences, in your own voice.\n"
        + personas.name_rule(persona) + "\n"
        "- When MoreMe asks you to write something (a story, a reply, an explanation, an opinion, a few lines "
        "about anything), do not write it yourself. Reply with exactly one line: USE: followed by the ids of "
        "the one or two passages that fit the request best, for example USE: p4, p9. Pick passages you have not "
        "used yet. Prefer one passage; add a second only if the first is short.\n"
        "- When MoreMe asks for a short message to use for the test, give this task, exactly: " + p["task"] + "\n"
        "- When MoreMe shows Draft A and Draft B and asks which sounds more like you, reply with only the "
        "letter A or B, for the draft closer to your own writing.\n"
        "- When MoreMe asks whether to install in the project folder or the personal folder, choose the "
        "project folder. Reply: Project folder.\n"
        "- When MoreMe shows the measurements of your writing and asks whether they sound like you, answer in "
        "your own voice, in one or two sentences: usually that it sounds like you, or one small correction "
        "(for example that you are chattier in letters than the numbers suggest).\n"
        "- If MoreMe asks whether to replace an existing my-voice skill, reply: Yes.\n"
        "- If MoreMe asks whether you want to stop early or keep writing, keep writing.\n"
        "- If the message asks you nothing, reply: OK, go ahead.\n"
        "- Never type a slash command, never ask to skip a step, never mention that you are role-playing."
    )


def interviewee_prompt(brief, history, last_assistant, used=(), correction=None):
    convo = []
    for who, text in history:
        convo.append("%s: %s" % ("You" if who == "user" else "MoreMe (Claude)", text))
    extra = ""
    if used:
        extra += "\n\nPassages you already used: %s." % ", ".join(used)
    if correction:
        extra += "\n\nYour last reply could not be used (%s). Reply again following the rules." % correction
    return (brief + "\n\nConversation so far:\n" + "\n\n".join(convo) + "\n\nMoreMe (Claude) just wrote:\n<<<\n"
            + last_assistant + "\n>>>" + extra + "\n\nWrite your reply now.")


def evidence_run_dir(run_id):
    """Raw evidence folder for one run (logs/, output/), outside the repo."""
    return artifacts.evidence_root() / "e2e" / "runs" / run_id


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
    logs = evidence_run_dir(args.run_id) / "logs"
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
    cap = ledger.count() + MAX_CALLS
    out = {"run_id": args.run_id, "scratch": str(d), "started": now_iso(),
           "flags": skill_flags("<new uuid>", True)}
    try:
        r = childrun.run_claude("safety", skill_flags(str(uuid.uuid4()), True), d, prompt, ledger, logs,
                                ["moreme"], allowed_skills=["moreme"], max_calls=cap,
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
    artifacts.write_committed_json(run_dir / "safety-result.json", out)
    print(artifacts.sanitize_text(json.dumps(out, indent=2, ensure_ascii=False)))
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
    ev = evidence_run_dir(args.run_id)
    if ev.exists() and any(ev.iterdir()):
        raise SystemExit("evidence folder exists, pick a new run id: %s" % artifacts.sanitize_text(str(ev)))
    logs = ev / "logs"
    logs.mkdir(parents=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    scratch, found_train = build_scratch(args.run_id, persona, split)
    iv_dir = childrun.make_scratch("moreme-e2e", args.run_id + "-iv")
    ledger = childrun.Ledger(LEDGER)
    cap = ledger.count() + MAX_CALLS
    sid = str(uuid.uuid4())
    catalog = passage_catalog(persona, split)
    brief = interviewee_brief(persona, scratch, catalog)
    used_ids = []
    prov_path = ev / "provenance.jsonl"
    artifacts.write_committed(run_dir / "interviewee-brief.txt", license_header(persona) + "\n\n" + brief)
    manifest = {
        "run_id": args.run_id, "persona": persona, "started": now_iso(), "cli_version": childrun.claude_version(),
        "model_pinned": childrun.MODEL, "session_id": sid, "scratch": str(scratch), "interviewee_scratch": str(iv_dir),
        "train_files_in_scratch": found_train, "opener": OPENER,
        "skill_flags_first": skill_flags(sid, True), "skill_flags_later": skill_flags(sid, False),
        "interviewee_flags": interviewee_flags(), "allowed_tools": childrun.MOREME_ALLOWED_TOOLS,
        "env_removed": "every variable starting with CLAUDE (any case) and AI_AGENT",
        "env_set_after_scrub": childrun.ENV_SET_AFTER_SCRUB, "scratch_settings": childrun.scratch_settings(),
        "license_header": license_header(persona), "banner_source": PERSONAS[persona]["banner_source"],
        "persona_first_name": PERSONAS[persona]["first_name"], "evidence_dir": str(ev),
        "sample_method": SAMPLE_METHOD, "passage_catalog_size": len(catalog),
        "passage_sources": sorted(set(c["file"] for c in catalog)),
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
                                    exp, allowed_skills=["moreme", "my-voice"], max_calls=cap,
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
            correction = None
            answer = prov = None
            for attempt in (0, 1):
                label = "interviewee-t%02d" % (i + 1) + ("" if attempt == 0 else "-retry")
                iv = childrun.run_claude(label, interviewee_flags(), iv_dir,
                                         interviewee_prompt(brief, history[:-1], text, used_ids, correction),
                                         ledger, logs, [], allowed_skills=[], max_calls=cap, timeout=IV_TIMEOUT,
                                         extra={"run_id": args.run_id, "turn": i + 1, "role": "interviewee"})
                answer, prov, correction = resolve_answer(iv["text"], catalog, used_ids)
                if correction is None or iv["invalid"]:
                    break
            if prov:
                used_ids += [x["id"] for x in prov]
                with open(str(prov_path), "a", encoding="utf-8", newline="\n") as f:
                    f.write(json.dumps({"turn": i + 1, "passages": prov}) + "\n")
            manifest["turns"].append({"turn": i + 1, "role": "interviewee", "label": label,
                                      "answer": answer, "answer_kind": "passages" if prov else "in_role",
                                      "passage_ids": [x["id"] for x in prov] if prov else [],
                                      "latency_s": iv["row"]["latency_s"], "wall_start": t1,
                                      "invalid": iv["invalid"] + (["unusable:" + correction] if correction else [])})
            write_manifest(run_dir, manifest)
            if iv["invalid"] or correction or not answer:
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
        dest = ev / "output"
        if dest.exists():
            shutil.rmtree(str(dest))
        shutil.copytree(str(out), str(dest))
    installed = scratch / ".claude" / "skills" / "my-voice" / "SKILL.md"
    manifest["installed_skill_md_exists"] = installed.exists()
    manifest["validate_skill"] = validate_skill(ev / "output" / "my-voice")
    manifest["stage_timings"] = stage_timings(manifest["turns"])
    manifest["chat_visibility"] = chat_visibility(load_turn_events(manifest, logs), ev / "output" / "report.txt")
    write_manifest(run_dir, manifest)
    render(run_dir, logs)
    print(json.dumps({"status": status, "run_dir": artifacts.sanitize_text(str(run_dir)),
                      "calls_in_ledger": ledger.count(), "chat_visibility_ok": manifest["chat_visibility"]["ok"],
                      "spill_new": len(manifest["spill_new"]), "validate_skill": manifest["validate_skill"]},
                     indent=2))
    return 0 if status == "completed" else 3


def write_manifest(run_dir, manifest):
    """The committed manifest is sanitized (home path, user name, emails)."""
    artifacts.write_committed_json(Path(run_dir) / "manifest.json", manifest)


def load_turn_events(manifest, logs_dir):
    """[(user_text, events)] for the skill turns, in order."""
    out = []
    for t in manifest["turns"]:
        if t["role"] != "skill":
            continue
        log = Path(logs_dir) / (t["label"] + ".jsonl")
        events = childrun.parse_events(log.read_text(encoding="utf-8")) if log.exists() else []
        out.append((t["user"], events))
    return out


STAGE_NAMES = ["Interview", "Sample", "Analysis", "Generate", "Blind A/B", "Install"]
# The Skill call that loads MoreMe comes before SKILL.md can act, so it is exempt;
# every other tool call counts.
OPENING_EXEMPT_TOOLS = ("Skill",)


def chat_items(turn_events):
    """Linear chat-level sequence: ("user", text), ("text", text) for main-thread
    assistant text (what the user sees), ("tool", name) for main-thread tool calls."""
    items = []
    for user, events in turn_events:
        items.append(("user", user))
        for e in events:
            if e.get("type") != "assistant" or e.get("parent_tool_use_id"):
                continue
            for c in (e.get("message") or {}).get("content") or []:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "text" and c.get("text", "").strip():
                    items.append(("text", c["text"]))
                elif c.get("type") == "tool_use":
                    items.append(("tool", c.get("name")))
    return items


WORDS_RE = re.compile(r"\b\d[\d,]*\s+words\b", re.I)
MINUTE_RE = re.compile(r"\bminutes?\b", re.I)


def ask_indices(items):
    """Indices of the messages that ask the user to act: the last chat text
    before each user message (and before the end), i.e. the text that ends a turn."""
    out = []
    last_text = None
    for idx, (kind, _v) in enumerate(items):
        if kind == "user":
            if last_text is not None:
                out.append(last_text)
            last_text = None
        elif kind == "text":
            last_text = idx
    if last_text is not None:
        out.append(last_text)
    return out


def chat_visibility(turn_events, report_path=None):
    """Mechanical cross-check of the rubric's chat-visibility rule (decision
    2026-10-20 turn boundaries; the clean-room reviewer is authoritative).

    A stage's lines count when the user sees them no later than the next
    message that asks the user to act (the text that ends a turn):
      opening    chat text (not just the previous done line) between the stage's
                 start and the first turn-ending message at or after it; for
                 stage 1 that text must give the time ("minutes");
      done       the exact done line in chat text, in order, with no user turn
                 between the stage's last tool call and the done line;
      word_count (stage 2) a "N words" count in chat within the stage;
      report     (stage 3) at least 60% of report.txt's non-empty lines in chat
                 text before the first tool call after the Step 3 done line.
    """
    items = chat_items(turn_events)
    asks = ask_indices(items)
    done_at = {}
    for idx, (kind, val) in enumerate(items):
        if kind != "text":
            continue
        for n, name in enumerate(STAGE_NAMES, 1):
            if n not in done_at and ("Step %d of 6 done: %s." % (n, name)) in val:
                done_at[n] = idx
    report_lines = []
    if report_path and Path(report_path).exists():
        report_lines = [x.strip() for x in Path(report_path).read_text(encoding="utf-8", errors="replace").splitlines()
                        if x.strip()]

    def next_ask(i):
        return next((a for a in asks if a >= i), len(items) - 1)

    def text_after_done(idx, n):
        line = "Step %d of 6 done: %s." % (n, STAGE_NAMES[n - 1])
        return items[idx][1].split(line, 1)[-1]

    stages = []
    prev = None
    in_order = True
    for n, name in enumerate(STAGE_NAMES, 1):
        st = {"stage": n, "done": n in done_at}
        end = done_at.get(n)
        if end is not None and prev is not None and end < prev:
            in_order = False
        start = 0 if prev is None else prev
        # The text after the previous done line (same message) counts, and so
        # does chat text up to the next message that asks the user to act.
        deadline = next_ask(start if prev is None else start + 1)
        window = []
        if prev is not None:
            window.append(text_after_done(prev, n - 1))
            window += [v for k, v in items[prev + 1:deadline + 1] if k == "text"]
        else:
            window += [v for k, v in items[:deadline + 1] if k == "text"]
        st["opening"] = any(w.strip() for w in window)
        if n == 1:
            # Step 1's opening is the introduction with the time it takes; a bare
            # interview question does not count.
            st["opening"] = bool(MINUTE_RE.search("\n".join(window)))
        stop = end if end is not None else deadline
        tools = [i for i in range(start, stop) if items[i][0] == "tool" and items[i][1] not in OPENING_EXEMPT_TOOLS]
        if end is not None:
            last_tool = tools[-1] if tools else start
            st["done_timely"] = not any(items[i][0] == "user" for i in range(last_tool, end))
        else:
            st["done_timely"] = False
        texts = []
        if prev is not None:
            texts.append(text_after_done(prev, n - 1))
        texts += [v for k, v in items[start + (1 if prev is not None else 0):stop] if k == "text"]
        if end is not None:
            texts.append(items[end][1].split("Step %d of 6 done: %s." % (n, name), 1)[0])
        if n == 2:
            st["word_count"] = bool(WORDS_RE.search("\n".join(texts)))
        if n == 3:
            if report_lines:
                lo = done_at.get(2, 0)
                if end is not None:
                    hi = next((i for i in range(end + 1, len(items)) if items[i][0] == "tool"), len(items))
                else:
                    hi = done_at.get(4, len(items))
                shown_text = "\n".join(v for k, v in items[lo:hi] if k == "text")
                shown = sum(1 for x in report_lines if x in shown_text)
                st["report_lines_shown"] = "%d/%d" % (shown, len(report_lines))
                st["report_shown"] = shown >= 0.6 * len(report_lines)
            else:
                st["report_shown"] = None
        stages.append(st)
        if end is not None:
            prev = end
    ok = in_order and all(s["done"] and s["done_timely"] and s["opening"] for s in stages)
    ok = ok and stages[1].get("word_count", False) and stages[2].get("report_shown") is not False
    return {"ok": bool(ok), "done_lines_in_order": in_order, "stages": stages,
            "rule": "lines visible no later than the next message that asks the user to act",
            "note": "Mechanical cross-check only; the clean-room reviewer decides R1-R6."}


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


def logs_for(run_dir):
    """A run's raw logs: <run_dir>/logs if present (older layout), else the evidence folder."""
    local = Path(run_dir) / "logs"
    return local if local.is_dir() else evidence_run_dir(Path(run_dir).name) / "logs"


def output_for(run_dir):
    """A run's moreme-output copy: <run_dir>/output if present, else the evidence folder."""
    local = Path(run_dir) / "output"
    return local if local.is_dir() else evidence_run_dir(Path(run_dir).name) / "output"


def render(run_dir, logs_dir=None):
    """Rebuild transcript.md from the raw logs. The written file is sanitized
    and carries the sanitizer disclosure under its title."""
    run_dir = Path(run_dir)
    logs_dir = Path(logs_dir) if logs_dir is not None else logs_for(run_dir)
    m = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    rows = [r for r in childrun.Ledger(LEDGER).rows() if r.get("run_id") == m["run_id"]]
    model_ids = sorted(set(r.get("model") for r in rows if r.get("model")))
    lines = [
        "<!-- %s -->" % m["license_header"],
        "",
        "# MoreMe end-to-end run: %s (headless)" % m["run_id"],
        "",
        "> Interviewee simulated by an AI agent; writing samples are %s. The A/B pick below is an AI agent's "
        "choice and is not evidence of quality." % m["banner_source"]
        + ((" " + m["sample_method"]) if m.get("sample_method") else ""),
        "",
        "Every turn below is verbatim: user messages, assistant text, tool calls, and tool output, rendered from "
        "the stream-json logs (kept outside the repo). This is a headless Claude Code run (`claude -p`), not a "
        "screen capture. Only the sanitizer substitutions named above were made.",
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
        "| Persona first name (invented) | %s |" % m.get("persona_first_name", "(none)"),
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
    cv = m.get("chat_visibility")
    if cv:
        lines += ["", "## Chat-visible stage lines (mechanical cross-check; the reviewer decides)", "",
                  "| Stage | Opening line | Done line | Extra |", "|---|---|---|---|"]
        for st in cv["stages"]:
            extra = ""
            if "word_count" in st:
                extra = "word count shown: %s" % st["word_count"]
            if "report_shown" in st:
                extra = "report shown: %s (%s lines)" % (st["report_shown"], st.get("report_lines_shown", "n/a"))
            lines.append("| %d | %s | %s | %s |" % (st["stage"], st["opening"], st["done"], extra))
        lines += ["", "Done lines in order: %s. Overall: %s." % (cv["done_lines_in_order"], cv["ok"])]
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
        log = logs_dir / (t["label"] + ".jsonl")
        events = childrun.parse_events(log.read_text(encoding="utf-8")) if log.exists() else []
        lines += render_events(events)
    return artifacts.write_committed(run_dir / "transcript.md", "\n".join(lines) + "\n", disclose=True)


def cmd_render(args):
    """Rebuild transcript.md; also refresh the manifest's chat_visibility
    cross-check when the raw logs are available."""
    run_dir = RUNS / args.run_id
    logs = logs_for(run_dir)
    m = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    if logs.is_dir() and m.get("turns"):
        m["chat_visibility"] = chat_visibility(load_turn_events(m, logs), output_for(run_dir) / "report.txt")
        write_manifest(run_dir, m)
    print(artifacts.sanitize_text(str(render(run_dir, logs))))
    return 0


# ---------------------------------------------------------------- review

REVIEW_PROMPT = """You are a clean-room reviewer. In this folder you have: SKILL.md (the MoreMe skill the run followed),
e2e-rubric.md (the rubric), transcript.md (the verbatim run transcript), and output/ (the run's moreme-output folder,
including output/run-log.md). Use nothing else. Read the rubric and SKILL.md first, then the whole transcript (it is
long; read it in parts with offset and limit until the end), run-log.md, and the files in output/ you need.

Chat visibility (part of R1-R6, see "Chat-visible stage lines" in the rubric): the user sees only main-thread
assistant text, which the transcript shows as blocks headed exactly "**Assistant:**". Text that appears only in
run-log.md, in a tool call's input (for example a Write of run-log.md), in a tool result, or in a subagent block does
NOT count as shown. The test is what the user has seen by the time they are asked to act: tool calls may run before
these lines inside a turn, but each line must appear no later than the next assistant message that asks the user to do
something (the message that ends the assistant's turn). For each stage 1 to 6 find, in "**Assistant:**" blocks only:
(1) the opening line (what happens next and about how long it takes; for Step 1, the introduction, in the first message
the user sees); (2) the exact done line "Step N of 6 done: <Name>." after the stage's work, not first appearing after
the user replied to a later message. Also find the Step 2 word count shown in chat, and the Step 3 report shown in chat
(the report.txt content, not only a Read of it) before any Step 4 tool call. A stage whose opening line, done line, or
required result is missing or late fails its R item even if run-log.md says passed. Under R9, the Step 3 check-in
("Does this sound like you? ...") and the resume question after the first answer (only when run-log.md already
existed) are expected questions. Step 2 is a guided writing conversation (see "Guided writing sample" in the rubric):
each writing prompt that follows from the previous answer, until the user's words reach about 300, is an expected
question; a request to paste or point to files is unnecessary. The simulated user's writing answers are verbatim
passages of real text; do not judge how well they fit the prompt.

Judge every rubric item R1 to R10. For R9, list every question the assistant asked the user and classify each as
expected or unnecessary with a one-line reason. For R10(b), compare the ab-present tool output with the assistant's
next chat message character by character (ignoring only leading/trailing whitespace) and say whether they match.

Reply with ONLY one JSON object, no prose before or after it, with this shape:
{"items": [{"id": "R1", "pass": true, "evidence": "transcript.md line N: ...", "reason": "..."}, ... one per R1..R10],
 "chat_visibility": [{"stage": 1, "opening": {"shown": true, "line": N}, "done": {"shown": true, "line": N},
   "result": {"what": "word count or report or none", "shown": true, "line": N}}, ... one per stage 1..6],
 "r9_questions": [{"line": N, "question": "...", "class": "expected", "reason": "..."}],
 "verdict": "pass" or "fail", "notes": "..."}
"""


def cmd_review(args):
    run_dir = RUNS / args.run_id
    out_dir = output_for(run_dir)
    if not (run_dir / "transcript.md").exists() or not (out_dir / "run-log.md").exists():
        raise SystemExit("missing transcript.md or output/run-log.md for %s" % args.run_id)
    rd = childrun.make_scratch("moreme-e2e", args.run_id + "-review",
                               files={"SKILL.md": SKILL_SRC / "SKILL.md", "e2e-rubric.md": RUBRIC,
                                      "transcript.md": run_dir / "transcript.md"})
    shutil.copytree(str(out_dir), str(rd / "output"))
    ledger = childrun.Ledger(LEDGER)
    cap = ledger.count() + MAX_CALLS
    flags = (["--model", childrun.MODEL, "--no-session-persistence", "--tools=Read,Glob,Grep"]
             + childrun.ISO_FLAGS + ["--permission-mode", "default", "--permission-prompts", "none"])
    r = childrun.run_claude("review", flags, rd, REVIEW_PROMPT, ledger, logs_for(run_dir), [], allowed_skills=[],
                            max_calls=cap, timeout=SKILL_TIMEOUT,
                            extra={"run_id": args.run_id + "-review", "role": "reviewer"})
    text = r["text"].strip()
    m = re.search(r"\{.*\}", text, re.S)
    verdict = None
    if m:
        try:
            verdict = json.loads(m.group(0))
        except ValueError:
            verdict = None
    persona = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8")).get("persona")
    out = {"license_header": license_header(persona) if persona else None,
           "run_id": args.run_id, "reviewed": now_iso(), "invalid": r["invalid"], "flags": flags,
           "reviewer_scratch": str(rd), "verdict": verdict, "raw": text if verdict is None else None}
    artifacts.write_committed_json(run_dir / "review.json", out)
    print(artifacts.sanitize_text(json.dumps(out, indent=2, ensure_ascii=False))[:6000])
    return 0


def export_example(run_id, dest):
    """Copy a run's generated my-voice/SKILL.md to dest/my-voice/ with the
    persona's license header after the frontmatter, sanitized. Returns the path."""
    run_dir = RUNS / run_id
    persona = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))["persona"]
    src = output_for(run_dir) / "my-voice" / "SKILL.md"
    text = artifacts.add_license_header(src.read_text(encoding="utf-8"), license_header(persona))
    return artifacts.write_committed(Path(dest) / "my-voice" / "SKILL.md", text)


def cmd_export(args):
    p = export_example(args.run_id, args.dest)
    print(json.dumps(validate_skill(p.parent)))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="MoreMe headless e2e driver")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("safety")
    s.add_argument("--run-id", required=True)
    r = sub.add_parser("run")
    r.add_argument("--persona", default="era-c")
    r.add_argument("--run-id", required=True)
    r.add_argument("--max-turns", type=int, default=26)
    for name in ("render", "review"):
        x = sub.add_parser(name)
        x.add_argument("--run-id", required=True)
    x = sub.add_parser("export-example")
    x.add_argument("--run-id", required=True)
    x.add_argument("--dest", default=str(REPO / "docs" / "example-run"))
    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return 2
    return dict(safety=cmd_safety, run=cmd_run, render=cmd_render, review=cmd_review,
                **{"export-example": cmd_export})[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
