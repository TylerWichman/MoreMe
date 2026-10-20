"""Stream-json invocation evidence and the per-call skill invariant (AD-006).

A draft unit's evidence comes from its stream-json events:

- init: skills, plugins, mcp_servers, claude_code_version, model
- skill_calls: every Skill tool_use (main thread and subagents), in order
- invoked: the target skill was called by a Skill tool_use on the main thread
  and its tool_result was not an error
- tools_used: every tool name used; draft units allow only Skill
- invariant_violations: Skill calls other than the arm's allowed set
"""
from harness import common

cr = common.childrun

DRAFT_ALLOWED_TOOLS = frozenset(["Skill"])
TARGET_SKILL = "my-voice"


def expected_skills(arm):
    return [TARGET_SKILL] if arm == "with" else []


def allowed_skills(arm):
    return set(expected_skills(arm))


def invocation(events, target=TARGET_SKILL):
    """(invoked, detail) for the target skill on the main thread."""
    uses = [t for t in cr.tool_uses(events)
            if t["name"] == "Skill" and (t["input"] or {}).get("skill") == target and not t["parent"]]
    if not uses:
        return False, "no_skill_tool_use"
    results = dict((r["tool_use_id"], r) for r in cr.tool_results(events))
    for u in uses:
        r = results.get(u["id"])
        if r is not None and not r["is_error"]:
            return True, "skill_tool_use_ok"
    return False, "skill_tool_use_error_or_no_result"


def unit_evidence(events, arm):
    """Compact, path-free evidence record for one draft unit."""
    init = cr.init_event(events) or {}
    tools = [t["name"] for t in cr.tool_uses(events)]
    invoked, detail = invocation(events)
    problems = ["init:" + p for p in cr.check_init(init or None, expected_skills(arm))]
    extra_tools = sorted(set(tools) - DRAFT_ALLOWED_TOOLS)
    if extra_tools:
        problems.append("tools_not_subset_of_skill:%s" % ",".join(extra_tools))
    violations = cr.skill_invariant(events, allowed_skills(arm))
    if violations:
        problems.append("skill_invariant:%s" % ",".join(str(v) for v in violations))
    return {
        "init_skills": init.get("skills"),
        "init_plugins": init.get("plugins"),
        "init_mcp_servers": init.get("mcp_servers"),
        "claude_code_version": init.get("claude_code_version"),
        "model": init.get("model"),
        "skill_calls": cr.skill_calls(events),
        "tools_used": tools,
        "invoked": invoked if arm == "with" else False,
        "invocation_detail": detail if arm == "with" else "not_applicable",
        "invariant_violations": violations,
        "problems": problems,
    }


def invariant_over_log(events, allowed):
    """Skill calls outside `allowed` in one saved stream-json log."""
    return cr.skill_invariant(events, set(allowed))


def invocation_rate(records):
    """Share of valid `with` units whose target skill was invoked."""
    w = [r for r in records if r["arm"] == "with" and r.get("valid")]
    if not w:
        return None, 0, 0
    k = sum(1 for r in w if r["evidence"]["invoked"])
    return k / float(len(w)), k, len(w)
