"""Child `claude -p` runs under the adopted AD-006 isolation profile (SUB-004).

Used by the e2e driver (eval/e2e/run_moreme.py) and the eval harness. Standard
library only.

What this module guarantees for every child call made through `run_claude`:

- The scratch project lives under %LOCALAPPDATA%\\Temp\\moreme-eval or
  ...\\moreme-e2e, is created by Python, and is outside any git repo.
- Flags `--setting-sources project --strict-mcp-config`, a pinned model, and
  the scratch `.claude/settings.json` from `scratch_settings()`.
- The environment has the parent session's CLAUDE* and AI_AGENT variables
  removed FIRST, and only then DISABLE_AUTOUPDATER=1,
  CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 and MOREME_TEST_GUARD=1 are set.
- Variadic flags are passed as --flag=value and the prompt goes on stdin.
- The init event is checked: exact target skill set, no plugins, no MCP
  servers, CLI version 2.1.303, auto-memory not written. A failed check marks
  the unit invalid.
- A names-only snapshot (os.scandir, no file is opened) of ~/.claude/skills
  and ~/.claude/commands is taken before and after. A new entry named
  my-voice*, voice-* or moreme* raises GuardHit and halts the run.
- A names-only count of new session folders under ~/.claude/projects.
- One ledger row per call in an append-only JSONL file with torn-tail healing.

Never reads file contents under ~/.claude, never touches credential files.
"""
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

# Expected Claude Code version. MOREME_CLI_VERSION overrides it for a run when the
# installed CLI has been updated (recorded per call; see PREREGISTRATION.md).
CLI_VERSION = os.environ.get("MOREME_CLI_VERSION", "2.1.303")
MODEL = "claude-sonnet-5-5"
SCRATCH_KINDS = ("moreme-eval", "moreme-e2e")

ISO_FLAGS = ["--setting-sources", "project", "--strict-mcp-config"]
PERMISSION_FLAGS = ["--permission-mode", "acceptEdits", "--permission-prompts", "none"]

# FROZEN 4 narrow allow list for MoreMe child runs. Never Bash(python:*).
MOREME_ALLOWED_TOOLS = [
    "Skill(moreme)",
    "Bash(python --version)",
    "Bash(py -3 --version)",
    "Bash(python3 --version)",
    "Bash(python .claude/skills/moreme/analyze.py:*)",
    "Bash(py -3 .claude/skills/moreme/analyze.py:*)",
    # Claude Code 2.1.306 on Windows may run commands through its PowerShell tool.
    "PowerShell(python --version)",
    "PowerShell(py -3 --version)",
    "PowerShell(python3 --version)",
    "PowerShell(python .claude/skills/moreme/analyze.py:*)",
    "PowerShell(py -3 .claude/skills/moreme/analyze.py:*)",
]

BUILTIN_PLUGINS = [
    "cc-plugin-agents-md@builtin",
    "cc-plugin-telemetry@builtin",
    "cc-plugin-plugin-authoring@builtin",
]
SKILL_OVERRIDES = {"design": "off", "doctor": "off"}

GUARD_PATTERNS = ["my-voice*", "voice-*", "moreme*"]
SPILL_MARKERS = ("moreme-eval", "moreme-e2e")

ENV_SET_AFTER_SCRUB = {
    "DISABLE_AUTOUPDATER": "1",
    "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
    "MOREME_TEST_GUARD": "1",
}


class UsageLimit(RuntimeError):
    """The subscription reported a usage or rate limit. Stop cleanly."""


class BudgetExceeded(RuntimeError):
    """The ledger already holds the maximum number of calls."""


class GuardHit(RuntimeError):
    """A guarded name appeared in ~/.claude/skills or ~/.claude/commands."""


class VersionChanged(RuntimeError):
    """The installed Claude Code version differs from the expected one. Halt the
    batch: a retry cannot fix it, so retrying would only spend calls."""


class ScratchError(RuntimeError):
    """The scratch project is in the wrong place or holds forbidden files."""


# ---------------------------------------------------------------- paths

def home():
    return Path(os.path.expanduser("~"))


def temp_base():
    """The machine temp folder that holds scratch projects."""
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "Temp"
    import tempfile
    return Path(tempfile.gettempdir())


def scratch_root(kind, base=None):
    if kind not in SCRATCH_KINDS:
        raise ValueError("unknown scratch kind: %r" % (kind,))
    return Path(base or temp_base()) / kind


def project_folder_name(path):
    """Name Claude Code gives a cwd under ~/.claude/projects: every character
    that is not an ASCII letter or digit becomes '-'."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def to_slash_abs(path):
    """C:\\Users\\x\\.claude -> //c/Users/x/.claude (the second deny-rule form, WIN-010)."""
    p = str(path).replace("\\", "/")
    m = re.match(r"^([A-Za-z]):/(.*)$", p)
    if m:
        return "//%s/%s" % (m.group(1).lower(), m.group(2))
    return p


# ------------------------------------------------------- scratch project

def scratch_settings(home_dir=None):
    """Scratch .claude/settings.json (SUB-004 plus autoMemoryEnabled false)."""
    claude_dir = to_slash_abs(Path(home_dir or home()) / ".claude")
    return {
        "enabledPlugins": dict((p, False) for p in BUILTIN_PLUGINS),
        "disableBundledSkills": True,
        "skillOverrides": dict(SKILL_OVERRIDES),
        "autoMemoryEnabled": False,
        "permissions": {
            "deny": [
                "Edit(~/.claude/**)",
                "Write(~/.claude/**)",
                "Edit(%s/**)" % claude_dir,
                "Write(%s/**)" % claude_dir,
            ]
        },
    }


def _inside_git_repo(path):
    for parent in [path] + list(path.parents):
        if (parent / ".git").exists():
            return parent
    return None


def make_scratch(kind, run_id, skills=None, files=None, texts=None, settings=None, base=None):
    """Create a fresh scratch project and return its path.

    skills:   {name: source_dir}  copied to .claude/skills/<name>/ (no __pycache__)
    files:    {relpath: source_file} copied byte for byte
    texts:    {relpath: text} written as UTF-8
    settings: dict for .claude/settings.json (default scratch_settings())
    """
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$", run_id):
        raise ScratchError("run id must be a short plain name: %r" % (run_id,))
    root = scratch_root(kind, base)
    d = root / run_id
    if d.exists():
        shutil.rmtree(str(d))
    d.mkdir(parents=True)
    repo = _inside_git_repo(d)
    if repo is not None:
        raise ScratchError("scratch dir is inside a git repo: %s" % repo)
    sp = d / ".claude" / "settings.json"
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(settings if settings is not None else scratch_settings(), indent=2),
                  encoding="utf-8")
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    for name, src in (skills or {}).items():
        shutil.copytree(str(src), str(d / ".claude" / "skills" / name), ignore=ignore)
    for rel, src in (files or {}).items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(src), str(p))
    for rel, text in (texts or {}).items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return d


def _sha(path):
    h = hashlib.sha256()
    with open(str(path), "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_train_only(scratch, corpus_dir, split, persona=None):
    """Raise ScratchError if any dev or held-out corpus document (by file name or
    by content hash) is present anywhere in the scratch project.

    split: parsed eval/split.json. persona: limit to one persona, or None for all.
    Returns the list of train documents found (relative corpus paths)."""
    scratch = Path(scratch)
    forbidden_names = {}
    forbidden_hashes = {}
    train_hashes = {}
    for pid, meta in split["personas"].items():
        if persona is not None and pid != persona:
            continue
        for doc in meta["documents"]:
            src = Path(corpus_dir) / doc["file"]
            if doc["split"] == "train":
                train_hashes[_sha(src)] = doc["file"]
            else:
                forbidden_names[Path(doc["file"]).name] = doc["file"]
                forbidden_hashes[_sha(src)] = doc["file"]
    hits = []
    found_train = []
    for f in scratch.rglob("*"):
        if not f.is_file():
            continue
        if f.name in forbidden_names:
            hits.append("%s (name of %s)" % (f, forbidden_names[f.name]))
            continue
        h = _sha(f)
        if h in forbidden_hashes:
            hits.append("%s (content of %s)" % (f, forbidden_hashes[h]))
        elif h in train_hashes:
            found_train.append(train_hashes[h])
    if hits:
        raise ScratchError("dev or held-out text in scratch dir: %s" % "; ".join(hits))
    return sorted(set(found_train))


# ------------------------------------------------------------ environment

def child_env(base=None):
    """Scrub parent CLAUDE*/AI_AGENT vars, THEN set the guard variables.
    (Setting CLAUDE_CODE_DISABLE_AUTO_MEMORY before the scrub would delete it.)"""
    src = os.environ if base is None else base
    env = {}
    for k, v in src.items():
        ku = k.upper()
        if ku.startswith("CLAUDE") or ku == "AI_AGENT":
            continue
        env[k] = v
    env.update(ENV_SET_AFTER_SCRUB)
    return env


# ---------------------------------------------------- names-only guards

def guard_dirs(home_dir=None):
    h = Path(home_dir or home())
    return [h / ".claude" / "skills", h / ".claude" / "commands"]


def names_snapshot(dirs=None, max_depth=3):
    """Directory-entry paths only (os.scandir). Never opens a file and never
    follows a link."""
    names = set()
    for root in dirs if dirs is not None else guard_dirs():
        root = Path(root)
        if not root.exists():
            names.add(str(root) + "  <absent>")
            continue
        stack = [(root, 0)]
        while stack:
            d, depth = stack.pop()
            try:
                with os.scandir(str(d)) as it:
                    for entry in it:
                        names.add(str(Path(entry.path)))
                        if entry.is_dir(follow_symlinks=False) and depth + 1 < max_depth:
                            stack.append((Path(entry.path), depth + 1))
            except OSError:
                pass
    return names


def guarded_names(new_entries):
    out = []
    for n in new_entries:
        base = Path(n.split("  <")[0]).name.lower()
        if any(fnmatch.fnmatch(base, pat) for pat in GUARD_PATTERNS):
            out.append(n)
    return out


def check_snapshot(before, after):
    """Return the new entries; raise GuardHit if any is a guarded name."""
    new = sorted(set(after) - set(before))
    hits = guarded_names(new)
    if hits:
        raise GuardHit("guarded names appeared: %s" % hits)
    return new


def spill_names(home_dir=None):
    """Direct children of ~/.claude/projects whose name holds moreme-eval or
    moreme-e2e (names only)."""
    p = Path(home_dir or home()) / ".claude" / "projects"
    if not p.exists():
        return set()
    with os.scandir(str(p)) as it:
        return set(e.name for e in it if any(m in e.name for m in SPILL_MARKERS))


# ---------------------------------------------------- stream-json parsing

def parse_events(text):
    events = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except ValueError:
            events.append({"type": "_unparsed", "raw": line[:500]})
    return events


def init_event(events):
    for e in events:
        if e.get("type") == "system" and e.get("subtype") == "init":
            return e
    return None


def result_event(events):
    for e in reversed(events):
        if e.get("type") == "result":
            return e
    return None


def tool_uses(events):
    """Every tool_use block, main thread and subagents, in order."""
    out = []
    for e in events:
        if e.get("type") == "assistant":
            for c in (e.get("message") or {}).get("content") or []:
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    out.append({"id": c.get("id"), "name": c.get("name"), "input": c.get("input"),
                                "parent": e.get("parent_tool_use_id")})
    return out


def tool_results(events):
    out = []
    for e in events:
        if e.get("type") == "user":
            content = (e.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for c in content:
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    body = c.get("content")
                    if isinstance(body, list):
                        body = "\n".join(x.get("text", "") for x in body if isinstance(x, dict))
                    out.append({"tool_use_id": c.get("tool_use_id"), "is_error": bool(c.get("is_error")),
                                "content": body if isinstance(body, str) else json.dumps(body),
                                "parent": e.get("parent_tool_use_id")})
    return out


def assistant_texts(events, main_only=True):
    texts = []
    for e in events:
        if e.get("type") != "assistant":
            continue
        if main_only and e.get("parent_tool_use_id"):
            continue
        for c in (e.get("message") or {}).get("content") or []:
            if isinstance(c, dict) and c.get("type") == "text":
                texts.append(c.get("text", ""))
    return texts


def final_text(events):
    texts = assistant_texts(events)
    return texts[-1] if texts else ""


def skill_calls(events):
    return [(t["input"] or {}).get("skill") for t in tool_uses(events) if t["name"] == "Skill"]


# ------------------------------------------------------- init assertion

def check_init(init, expect_skills, version=CLI_VERSION):
    """Problems with the init event (empty list = pass)."""
    if not init:
        return ["no_init_event"]
    problems = []
    skills = init.get("skills")
    if skills is None or sorted(skills) != sorted(expect_skills):
        problems.append("skills=%s expected=%s" % (json.dumps(skills), json.dumps(sorted(expect_skills))))
    if init.get("plugins"):
        problems.append("plugins=%s" % json.dumps(init.get("plugins")))
    if init.get("mcp_servers"):
        problems.append("mcp_servers=%s" % json.dumps(init.get("mcp_servers")))
    if init.get("claude_code_version") != version:
        problems.append("claude_code_version=%s expected=%s" % (init.get("claude_code_version"), version))
    return problems


def memory_problems(init):
    """Auto-memory must be off: no reported path, or the reported folder is
    absent or empty after the run (names only)."""
    paths = (init or {}).get("memory_paths") or {}
    out = []
    for key, p in paths.items():
        if not p:
            continue
        d = Path(p)
        if d.is_dir():
            with os.scandir(str(d)) as it:
                if any(True for _ in it):
                    out.append("auto_memory_written:%s" % key)
    return out


def skill_invariant(events, allowed):
    """Skill invocations outside `allowed` (main thread and subagents)."""
    return [s for s in skill_calls(events) if s not in allowed]


# --------------------------------------------------- invalid-unit detector

INVALID_PATTERNS = [
    ("refusal", re.compile(r"\bI (?:can(?:'|\u2019)?t|cannot|won(?:'|\u2019)?t|will not) (?:help|assist|write|do) (?:with )?(?:that|this)\b", re.I)),
    ("refusal", re.compile(r"\bI(?:'|\u2019)?m (?:not able|unable) to (?:help|assist|write) (?:with )?(?:that|this)\b", re.I)),
    ("missing_skill", re.compile(r"\b(?:couldn(?:'|\u2019)?t|could not|can(?:'|\u2019)?t|cannot|unable to|did not|didn(?:'|\u2019)?t) (?:find|locate|load|access|see)\b[^.\n]{0,60}\bskill", re.I)),
    ("missing_skill", re.compile(r"\bskill\b[^.\n]{0,60}\b(?:is not|isn(?:'|\u2019)?t|was not|wasn(?:'|\u2019)?t) (?:installed|available|found|loaded)\b", re.I)),
    ("missing_skill", re.compile(r"\bskill\b[^.\n]{0,60}\b(?:unavailable|doesn(?:'|\u2019)?t exist|does not exist|not found)\b", re.I)),
    ("missing_skill", re.compile(r"\bno (?:such )?skill (?:named|called)\b", re.I)),
]


def invalid_reason(text):
    """Return 'empty', 'refusal', 'missing_skill', or None for a draft."""
    if text is None or not text.strip():
        return "empty"
    for reason, rx in INVALID_PATTERNS:
        if rx.search(text):
            return reason
    return None


# ----------------------------------------------------------------- ledger

class Ledger(object):
    """Append-only JSONL. Before each append, a partial last line (no trailing
    newline) is moved to <name>.quarantine.jsonl and never merged."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.quarantine = self.path.with_name(self.path.stem + ".quarantine.jsonl")

    def heal(self):
        if not self.path.exists():
            return None
        data = self.path.read_bytes()
        if not data or data.endswith(b"\n"):
            return None
        cut = data.rfind(b"\n") + 1
        torn = data[cut:]
        with open(str(self.quarantine), "ab") as q:
            q.write(torn + b"\n")
        with open(str(self.path), "r+b") as f:
            f.truncate(cut)
        return torn.decode("utf-8", "replace")

    def rows(self):
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
        return out

    def append(self, row):
        self.heal()
        line = json.dumps(row, ensure_ascii=False) + "\n"
        with open(str(self.path), "a", encoding="utf-8", newline="\n") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    def count(self, key="call"):
        return sum(1 for r in self.rows() if r.get("kind") == key)


# ------------------------------------------------------------------ runner

def _usage_limited(res, err, events):
    blob = (str((res or {}).get("result", "")) + " " + (err or "")).lower()
    if (res or {}).get("is_error") and any(s in blob for s in ("usage limit", "rate limit", "limit reached")):
        return True
    for e in events:
        if e.get("type") == "rate_limit_event":
            info = e.get("rate_limit_info") or {}
            if info.get("status") == "rejected":
                return True
    return False


def run_claude(label, args, cwd, prompt, ledger, log_dir, expect_skills, allowed_skills=None,
               max_calls=60, timeout=1200, claude=None, home_dir=None, extra=None):
    """Run one child `claude -p` call with the prompt on stdin.

    Returns a dict: row (ledger row), events, init, result, text, stderr,
    invalid (list of reasons; empty = valid unit). Raises GuardHit after
    logging if a guarded name appears, UsageLimit on a limit error, and
    BudgetExceeded before the call if the ledger is full."""
    used = ledger.count()
    if used >= max_calls:
        raise BudgetExceeded("call budget reached: %d" % used)
    claude = claude or shutil.which("claude")
    if not claude:
        raise RuntimeError("claude CLI not found on PATH")
    prefix = list(claude) if isinstance(claude, (list, tuple)) else [claude]
    for a in args:
        # Variadic flags swallow a following prompt; require --flag=value.
        # (--tools "" is fine because the prompt goes on stdin.)
        if a in ("--allowedTools", "--allowed-tools", "--disallowedTools", "--disallowed-tools"):
            raise ValueError("pass %s as --flag=value" % a)
    cmd = prefix + ["-p", "--output-format", "stream-json", "--verbose"] + list(args)
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    gdirs = guard_dirs(home_dir)
    before = names_snapshot(gdirs)
    spill_before = spill_names(home_dir)
    t0 = time.time()
    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        p = subprocess.run(cmd, cwd=str(cwd), env=child_env(), input=prompt, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
        out, err, code = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as ex:
        out = ex.stdout or ""
        err = ex.stderr or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
        err += "\n[TIMEOUT]"
        code = -999
    latency = round(time.time() - t0, 2)
    after = names_snapshot(gdirs)
    spill_after = spill_names(home_dir)
    (log_dir / (label + ".jsonl")).write_text(out, encoding="utf-8")
    if err.strip():
        (log_dir / (label + ".stderr.txt")).write_text(err, encoding="utf-8")
    events = parse_events(out)
    init = init_event(events)
    res = result_event(events) or {}
    tus = tool_uses(events)
    trs = tool_results(events)
    invalid = []
    invalid += ["init:" + x for x in check_init(init, expect_skills)]
    invalid += ["memory:" + x for x in memory_problems(init)]
    bad_skills = skill_invariant(events, set(allowed_skills if allowed_skills is not None else expect_skills))
    if bad_skills:
        invalid.append("skill_invariant:%s" % json.dumps(bad_skills))
    if code != 0:
        invalid.append("exit=%s" % code)
    new_guard = sorted(set(after) - set(before))
    guard_hits = guarded_names(new_guard)
    row = {
        "kind": "call",
        "n": used + 1,
        "label": label,
        "started": started,
        "args": list(args),
        "cwd": str(cwd),
        "exit": code,
        "latency_s": latency,
        "model": (init or {}).get("model"),
        "claude_code_version": (init or {}).get("claude_code_version"),
        "apiKeySource": (init or {}).get("apiKeySource"),
        "init_skills": (init or {}).get("skills"),
        "init_plugins": (init or {}).get("plugins"),
        "init_mcp_servers": (init or {}).get("mcp_servers"),
        "permissionMode": (init or {}).get("permissionMode"),
        "session_id": res.get("session_id") or (init or {}).get("session_id"),
        "num_turns": res.get("num_turns"),
        "duration_ms": res.get("duration_ms"),
        "api_equivalent_cost_usd": res.get("total_cost_usd"),
        "usage": res.get("usage"),
        "is_error": res.get("is_error"),
        "result_subtype": res.get("subtype"),
        "skill_calls": skill_calls(events),
        "tools_used": [t["name"] for t in tus],
        "tool_errors": sum(1 for r in trs if r["is_error"]),
        "permission_denials": res.get("permission_denials"),
        "guard_new_entries": len(new_guard),
        "guard_hits": guard_hits,
        "spill_new": sorted(spill_after - spill_before),
        "invalid": invalid,
        "rate_limit_info": [e.get("rate_limit_info") for e in events if e.get("type") == "rate_limit_event"][-1:],
    }
    if extra:
        row.update(extra)
    ledger.append(row)
    out_dict = {"row": row, "events": events, "init": init, "result": res, "text": final_text(events),
                "stderr": err, "invalid": invalid, "tool_uses": tus, "tool_results": trs}
    if guard_hits:
        raise GuardHit("guarded names appeared: %s" % guard_hits)
    if _usage_limited(res, err, events):
        raise UsageLimit(str(res.get("result", ""))[:300] or err[:300])
    return out_dict


def claude_version(claude=None):
    claude = claude or shutil.which("claude")
    p = subprocess.run([claude, "--version"], capture_output=True, text=True, env=child_env(), timeout=60)
    return p.stdout.strip()
