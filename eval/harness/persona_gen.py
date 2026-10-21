"""Persona skill generation (AD-006 "Skill generation per persona").

Each persona's my-voice skill is produced by the shipped moreme/SKILL.md, driven
by the e2e driver (eval/e2e/run_moreme.py, unchanged) with a simulated
interviewee whose samples are that persona's train split only. The driver ships
a brief for era-c only; this module adds briefs for the other personas to the
driver's PERSONAS table at run time and then calls the driver's own `run`
command, so the flow, isolation profile, guards, and outputs are the driver's.

    cd eval && python -m harness gen-skill --persona modern-a --run-id gen-modern-a-r1

After a completed run, the generated my-voice/SKILL.md is exported with the
driver's export_example (license header after the frontmatter, sanitized) to
eval/skills/<persona>/my-voice/SKILL.md, and eval/skills/<persona>/source.json
records which run produced it.

Briefs use persona IDs and invented first names only (eval/lib/personas.py);
writer names appear only in the banner_source line, which the driver prints in
the transcript banner for attribution, as it does for era-c.
"""
import argparse
import json
import sys
from pathlib import Path

from harness import common

sys.path.insert(0, str(common.EVAL / "e2e"))
import run_moreme  # noqa: E402

BRIEFS = {
    "modern-a": {
        "banner_source": ("posts by Mike Bracken on the GDS blog (UK Government Digital Service, 2011 to 2015), "
                          "Open Government Licence v3.0"),
        "who": ("You lead a large digital team inside a national government. You write blog posts for your "
                "colleagues and the public about plans, progress, and why services should be built around the "
                "people who use them. You are direct, upbeat, and plain-spoken, and you like short punchy "
                "sentences and lists of what comes next. You never use emoji. Today you use AI to help you write "
                "team updates, emails to colleagues, and blog posts."),
        "give_files": ["my-writing/modern-a-04.txt", "my-writing/modern-a-05.txt", "my-writing/modern-a-15.txt"],
        "task": ("A short post for our team blog saying the new online booking service is live and thanking "
                 "everyone who tested it."),
    },
    "modern-b": {
        "banner_source": ("articles by Ron McFarland on Opensource.com (2019 to 2023), CC BY-SA 4.0"),
        "who": ("You are a management consultant who writes essays about how organizations work, often "
                "explaining an idea from a business book and applying it to teams. You are patient, curious, and "
                "methodical, and you like to define terms and walk through examples. You never use emoji. Today "
                "you use AI to help you write articles, emails to clients, and short posts."),
        "give_files": ["my-writing/modern-b-01.txt", "my-writing/modern-b-03.txt", "my-writing/modern-b-06.txt"],
        "task": "A short email to a client explaining why their team should hold a monthly open planning meeting.",
    },
    "era-d": {
        "banner_source": ("a public-domain wartime diary from Louisiana, 1862 (Project Gutenberg)"),
        "who": ("You are a young woman who keeps a private diary during a war. You write lively, introspective "
                "entries about family, friends, rumors, books, and your own moods, and you digress freely. You "
                "never use emoji. Today you use AI to help you write notes and letters to friends and family."),
        "give_files": ["my-writing/era-d-02.txt", "my-writing/era-d-05.txt", "my-writing/era-d-07.txt"],
        "task": "A short note to my cousin telling her about the visitors we had yesterday.",
    },
    "era-e": {
        "banner_source": ("public-domain humorous essays on keeping a vegetable garden, 1870 (Project Gutenberg)"),
        "who": ("You are a man who writes humorous essays about your vegetable garden: weeds, neighbors, pests, "
                "and your own small vanities. You are dry, wry, and fond of mock-solemn asides. You never use "
                "emoji. Today you use AI to help you write notes, letters, and short posts."),
        "give_files": ["my-writing/era-e-01.txt", "my-writing/era-e-07.txt", "my-writing/era-e-08.txt"],
        "task": "A short note to my neighbor thanking him for the seeds and warning him about the beetles.",
    },
    "era-f": {
        "banner_source": ("public-domain Sunday evening talks to students, 1902 (Project Gutenberg)"),
        "who": ("You are the head of a school who gives short, plain talks to students about character, work, "
                "and daily habits. You speak directly, use simple examples from ordinary life, and end with a "
                "clear lesson. You never use emoji. Today you use AI to help you write talks, letters, and short "
                "notes to students and teachers."),
        "give_files": ["my-writing/era-f-02.txt", "my-writing/era-f-04.txt", "my-writing/era-f-05.txt"],
        "task": "A short note to the students about keeping their rooms clean and orderly.",
    },
}


def register_briefs():
    """Add briefs the driver does not ship, never replacing one it does."""
    split = common.load_split()
    for pid, b in BRIEFS.items():
        if pid in run_moreme.PERSONAS:
            continue
        train = set("my-writing/" + Path(f).name for f in common.split_files(split, pid, "train"))
        missing = [f for f in b["give_files"] if f not in train]
        if missing:
            raise ValueError("brief for %s names non-train files: %s" % (pid, missing))
        entry = dict(b)
        entry["excerpt_words"] = 350
        entry["first_name"] = common.personas.persona_first_name(pid)
        run_moreme.PERSONAS[pid] = entry


def skill_dir(persona):
    return common.SKILLS / persona / "my-voice"


def export(persona, run_id, attempts=None):
    dest = common.SKILLS / persona
    p = run_moreme.export_example(run_id, dest)
    check = run_moreme.validate_skill(p.parent)
    m = run_manifest(run_id)
    common.write_json(dest / "source.json", {
        "license_header": common.license_headers()[persona],
        "persona": persona, "run_id": run_id, "generated_by": "moreme/SKILL.md via eval/e2e/run_moreme.py run",
        "sample_method": m.get("sample_method"), "sample_composition": m.get("sample_composition"),
        "generation_attempts": attempts or [], "committed_run_dir": "eval/e2e/runs/%s/" % run_id,
        "validate_skill": check,
    })
    return p, check


MAX_GENERATION_ATTEMPTS = 2


def run_manifest(run_id):
    return common.read_json(run_moreme.RUNS / run_id / "manifest.json")


def generation_verdict(manifest):
    """(usable, reason). A generation counts only when the run completed and its
    sample meets the corpus-share rule (>= 75% verbatim corpus words before the
    Step 2 done line, eval/e2e/run_moreme.sample_composition)."""
    if manifest.get("status") != "completed":
        return False, "status:%s" % manifest.get("status")
    comp = manifest.get("sample_composition") or {}
    if not comp.get("meets_rule"):
        return False, "corpus_share:%s" % comp.get("corpus_share")
    return True, "ok"


def generate(persona, run_id, max_turns=16, attempts=MAX_GENERATION_ATTEMPTS, run=None):
    """Run generation until one run is usable; every failed run is kept and
    counted. A usage limit or guard hit stops at once. Returns (run_id or None, log)."""
    run = run or (lambda rid: run_moreme.cmd_run(argparse.Namespace(persona=persona, run_id=rid,
                                                                    max_turns=max_turns)))
    log = []
    for k in range(1, attempts + 1):
        rid = run_id if k == 1 else "%s-a%d" % (run_id, k)
        run(rid)
        m = run_manifest(rid)
        ok, reason = generation_verdict(m)
        log.append({"run_id": rid, "usable": ok, "reason": reason,
                    "sample_composition": m.get("sample_composition")})
        if ok:
            return rid, log
        if m.get("status") in ("usage_limit", "guard_hit", "budget_exceeded"):
            break
    return None, log


def main(argv=None):
    ap = argparse.ArgumentParser(prog="harness gen-skill")
    ap.add_argument("--persona", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--max-turns", type=int, default=16)
    ap.add_argument("--attempts", type=int, default=MAX_GENERATION_ATTEMPTS)
    ap.add_argument("--export-only", action="store_true", help="export a finished run's skill, no calls")
    a = ap.parse_args(argv)
    register_briefs()
    attempts = []
    rid = a.run_id
    if not a.export_only:
        rid, attempts = generate(a.persona, a.run_id, a.max_turns, a.attempts)
        print(json.dumps({"generation_attempts": attempts}))
        if rid is None:
            print("no usable generation run; nothing exported", file=sys.stderr)
            return 3
    else:
        ok, reason = generation_verdict(run_manifest(rid))
        if not ok:
            print("run %s is not usable (%s); nothing exported" % (rid, reason), file=sys.stderr)
            return 3
    p, check = export(a.persona, rid, attempts)
    print(json.dumps({"skill": common.rel(p), "validate_skill": check}))
    return 0 if check.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
