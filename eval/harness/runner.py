"""3-arm draft runner (AD-006 Arms) on eval/lib/childrun.py.

Arms: without (task prompt only), with (same prompt, the persona's my-voice
skill in the scratch project's .claude/skills/), samples-pasted (same prompt
plus 3 fixed train excerpts). Reps: 2 with, 2 without, 1 samples-pasted.
Same pinned --model for every arm. The 5 units of a task run in an order
shuffled by random.Random("<ARM_ORDER_SEED>:<persona>:<task id>"), recorded in
the manifest. Draft units are single-shot with --no-session-persistence.

Where things go (AMEND-002):
- evidence_dir (outside the repo): the call ledger and raw stream-json logs.
- results_dir (in the repo): one path-free draft record per unit and a
  manifest. Every draft record carries its persona's license header.

Exit codes of run_batch: 0 done, 3 usage limit (resume later from the ledger),
4 call budget reached, 5 guard hit (halted), 6 seven-day window too full.
"""
import random
import re
import shutil
import time
from pathlib import Path

from harness import common, evidence, extraction, leakage, prereg, tasks
from harness.ledger import MAX_ATTEMPTS, UnitLedger, unit_key

cr = common.childrun

SEVEN_DAY_MAX = 0.90
EXIT_OK, EXIT_LIMIT, EXIT_BUDGET, EXIT_GUARD, EXIT_WINDOW = 0, 3, 4, 5, 6


def unit_plan(persona, task_id, seed=common.ARM_ORDER_SEED):
    """The 5 (arm, rep) units of one task in their recorded random order."""
    units = [(arm, rep) for arm in common.ARMS for rep in range(1, common.REPS[arm] + 1)]
    rng = random.Random("%s:%s:%s" % (seed, persona, task_id))
    rng.shuffle(units)
    return units


def draft_args(arm, model=cr.MODEL):
    args = ["--model", model, "--no-session-persistence"] + cr.ISO_FLAGS + cr.PERMISSION_FLAGS
    if arm == "with":
        args.append("--allowedTools=Skill(%s)" % evidence.TARGET_SKILL)
    return args


def last_rate_limit(rows):
    for r in reversed(rows):
        info = r.get("rate_limit_info") or []
        if info:
            return info[-1]
    return None


def window_ok(rows, seven_day_max=SEVEN_DAY_MAX):
    """(ok, note) from the newest rate_limit_event seen in the ledger."""
    info = last_rate_limit(rows)
    if not info:
        return True, "no rate_limit_event seen yet"
    if info.get("status") == "rejected":
        return False, "last rate_limit_event was rejected"
    seven = ((info.get("unifiedWindows") or {}).get("seven_day") or {}).get("utilization")
    if seven is not None and seven >= seven_day_max:
        return False, "seven-day utilization %.2f >= %.2f" % (seven, seven_day_max)
    return True, "seven-day utilization %s" % seven


def _safe(s):
    return re.sub(r"[^A-Za-z0-9._-]", "-", s)


def draft_record_path(results_dir, persona, task_id, arm, rep):
    return Path(results_dir) / "drafts" / ("%s-%s-r%d.json" % (task_id, arm, rep))


def run_unit(ctx, persona, task, arm, rep, position, interrupted):
    key = unit_key(persona, task["id"], arm, rep)
    excerpts = ctx["excerpts"].get(persona) if arm == "samples-pasted" else None
    prompt = tasks.arm_prompt(task["prompt"], arm, ctx["mode"], excerpts)
    history = []
    out = None
    record = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        run_id = _safe("d-%s-%s-r%d-a%d-%s" % (task["id"], arm, rep, attempt, ctx["stamp"]))
        skills = {"my-voice": ctx["skill_dirs"][persona]} if arm == "with" else None
        scratch = cr.make_scratch("moreme-eval", run_id, skills=skills, base=ctx.get("scratch_base"))
        try:
            leakage.assert_draft_scratch(scratch, ctx["split"], arm)
            out = cr.run_claude(
                run_id, draft_args(arm, ctx["model"]), scratch, prompt, ctx["ledger"].ledger, ctx["log_dir"],
                evidence.expected_skills(arm), allowed_skills=evidence.allowed_skills(arm),
                max_calls=ctx["max_calls"], claude=ctx.get("claude"), home_dir=ctx.get("home_dir"),
                extra={"unit": key, "attempt": attempt})
        finally:
            if not ctx.get("keep_scratch"):
                shutil.rmtree(str(scratch), ignore_errors=True)
        final = out["text"]
        draft = extraction.extract_draft(final)
        ev = evidence.unit_evidence(out["events"], arm)
        reasons = list(out["invalid"]) + ev["problems"] + extraction.invalid_reasons(final, draft)
        reasons = sorted(set(reasons))
        record = {
            "license_header": ctx["headers"][persona],
            "persona": persona, "task_id": task["id"], "split": task["split"], "arm": arm, "rep": rep,
            "mode": ctx["mode"], "model_requested": ctx["model"], "position_in_task": position,
            "attempt": attempt, "prompt": prompt, "final_message": final, "draft": draft,
            "draft_words": len(common.words(draft)), "target_words": task["target_words"],
            "valid": not reasons, "invalid_reasons": reasons, "invalid_history": list(history),
            "evidence": ev, "log_label": run_id,
            "created": time.strftime("%Y-%m-%dT%H:%M"),
        }
        if not reasons:
            break
        history.append({"attempt": attempt, "reasons": reasons})
    path = draft_record_path(ctx["results_dir"], persona, task["id"], arm, rep)
    common.write_json(path, record)
    ctx["ledger"].mark_done(key, record["valid"], record["attempt"], common.rel(path),
                            reasons=history, interrupted_rerun=interrupted)
    return record


def run_batch(personas, which, evidence_dir, results_dir, mode="auto", model=cr.MODEL, task_ids=None,
              max_calls=120, claude=None, home_dir=None, scratch_base=None, skill_dirs=None,
              split=None, tasks_doc=None, keep_scratch=False, prereg_path=None, log=print):
    """Run every unit of the given personas' tasks that is not done yet."""
    if which == "heldout":
        prereg.require_frozen(prereg_path)  # raises on any hash mismatch
    split = split or common.load_split()
    tasks_doc = tasks_doc or tasks.load()
    evidence_dir = Path(evidence_dir)
    results_dir = Path(results_dir)
    ledger = UnitLedger(evidence_dir / "ledger.jsonl")
    torn = ledger.heal()
    if torn is not None:
        log("torn tail quarantined (%d bytes); its unit will be re-run" % len(torn.encode("utf-8")))
    ok, note = window_ok(ledger.rows())
    if not ok:
        log("not starting: " + note)
        return EXIT_WINDOW
    skill_dirs = skill_dirs or dict((p, common.SKILLS / p / "my-voice") for p in personas)
    ctx = {
        "split": split, "mode": mode, "model": model, "ledger": ledger, "log_dir": evidence_dir / "logs",
        "results_dir": results_dir, "max_calls": max_calls, "claude": claude, "home_dir": home_dir,
        "scratch_base": scratch_base, "skill_dirs": skill_dirs, "keep_scratch": keep_scratch,
        "headers": common.license_headers(), "stamp": time.strftime("%m%d%H%M"),
        "excerpts": dict((p, tasks.train_excerpts(split, p)) for p in personas),
    }
    done = ledger.done_units()
    interrupted = set(ledger.interrupted_units())
    spill_before = cr.spill_names(home_dir)
    plan = []
    for persona in personas:
        for task in tasks.select(tasks_doc, persona, which):
            if task_ids and task["id"] not in task_ids:
                continue
            plan.append((persona, task, unit_plan(persona, task["id"])))
    code = EXIT_OK
    stopped = None
    try:
        for persona, task, units in plan:
            for pos, (arm, rep) in enumerate(units, 1):
                key = unit_key(persona, task["id"], arm, rep)
                if key in done:
                    continue
                rec = run_unit(ctx, persona, task, arm, rep, pos, key in interrupted)
                log("%s valid=%s invoked=%s" % (key, rec["valid"], rec["evidence"]["invoked"]))
    except cr.UsageLimit as ex:
        code, stopped = EXIT_LIMIT, "usage limit: %s" % str(ex)[:200]
    except cr.BudgetExceeded as ex:
        code, stopped = EXIT_BUDGET, str(ex)
    except cr.GuardHit as ex:
        code, stopped = EXIT_GUARD, "guard hit (halted): %s" % common.scrub_paths(str(ex))
    spill_after = cr.spill_names(home_dir)
    write_manifest(results_dir, ledger, plan, mode, model, which, stopped,
                   sorted(spill_after - spill_before), spill_before, spill_after)
    if stopped:
        log("stopped: " + stopped)
    return code


def load_records(results_dir):
    out = []
    for f in sorted((Path(results_dir) / "drafts").glob("*.json")):
        out.append(common.read_json(f))
    return out


def write_manifest(results_dir, ledger, plan, mode, model, which, stopped, spill_new, spill_before, spill_after):
    records = load_records(results_dir)
    rate, k, n = evidence.invocation_rate(records)
    models = sorted(set(str(r["evidence"].get("model")) for r in records))
    versions = sorted(set(str(r["evidence"].get("claude_code_version")) for r in records))
    previous = {}
    mpath = Path(results_dir) / "manifest.json"
    if mpath.exists():
        previous = common.read_json(mpath)
    spill_total = previous.get("session_spill", {}).get("new_folders_total", 0) + len(spill_new)
    manifest = {
        "schema_version": "1",
        "split": which,
        "mode": mode,
        "model_requested": model,
        "models_observed": models,
        "claude_code_versions": versions,
        "arm_order_seed": common.ARM_ORDER_SEED,
        "samples_seed": common.SAMPLES_SEED,
        "reps": common.REPS,
        "unit_order": dict((t["id"], ["%s-r%d" % u for u in units]) for _p, t, units in plan),
        "ledger": ledger.summary(),
        "invocation": {"rate": rate, "invoked": k, "valid_with_units": n,
                       "threshold": common.INVOCATION_THRESHOLD,
                       "below_threshold": (rate is not None and rate < common.INVOCATION_THRESHOLD)},
        "invalid_units": sum(1 for r in records if not r["valid"]),
        "units_with_reruns": sum(1 for r in records if r["invalid_history"]),
        "skill_invariant_failures": sum(1 for r in records for h in r["invalid_history"]
                                        if any(x.startswith("skill_invariant") for x in h["reasons"])),
        "init_assertion_failures": sum(1 for r in records for h in r["invalid_history"]
                                       if any(x.startswith("init:") for x in h["reasons"])),
        "session_spill": {"new_folders_this_batch": len(spill_new), "new_folders_total": spill_total,
                          "matching_folders_before": len(spill_before), "matching_folders_after": len(spill_after),
                          "method": "names-only listing of ~/.claude/projects entries containing moreme-eval or moreme-e2e"},
        "stopped": stopped,
        "updated": time.strftime("%Y-%m-%dT%H:%M"),
    }
    common.write_json(mpath, manifest)
    return manifest
