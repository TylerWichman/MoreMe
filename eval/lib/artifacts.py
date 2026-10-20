"""Where run artifacts go, and the privacy hook for committed ones.

Standard library only. Two kinds of output:

- Committed artifacts (transcripts, manifests, rubric records, generated
  skills) stay in the repo. Write them with `write_committed()`, which runs
  tools/sanitize_artifacts.py on the text first.
- Raw evidence (stream-json logs, call ledgers, console dumps, stderr) is
  bulky and full of machine paths. It goes to `evidence_root()`, outside the
  repo's tracked tree:
    1. $MOREME_EVIDENCE_DIR when set;
    2. else, when the repo sits inside a OneShot workspace, its project
       evidence folder (vault/clients/operator/snapshots/moreme-public-release/evidence);
    3. else <repo>/.evidence/ (git-ignored).
"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
_TOOLS = REPO / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))
import sanitize_artifacts  # noqa: E402

DISCLOSURE = sanitize_artifacts.DISCLOSURE
VAULT_EVIDENCE = Path("vault") / "clients" / "operator" / "snapshots" / "moreme-public-release" / "evidence"
LOCAL_EVIDENCE = ".evidence"


def evidence_root(repo=None, env=None):
    env = os.environ if env is None else env
    repo = Path(repo or REPO).resolve()
    if env.get("MOREME_EVIDENCE_DIR"):
        return Path(env["MOREME_EVIDENCE_DIR"])
    for parent in repo.parents:
        if (parent / "vault" / "clients").is_dir():
            return parent / VAULT_EVIDENCE
    return repo / LOCAL_EVIDENCE


def evidence_dir(*parts, **kw):
    """evidence_root()/<parts...>, created. Example: evidence_dir("e2e", run_id)."""
    d = evidence_root(repo=kw.get("repo"), env=kw.get("env")).joinpath(*parts)
    d.mkdir(parents=True, exist_ok=True)
    return d


def sanitize_text(text):
    return sanitize_artifacts.sanitize_text(text)


def sanitize_obj(obj):
    """Sanitize every string (keys and values) inside a JSON-like object."""
    if isinstance(obj, str):
        return sanitize_text(obj)
    if isinstance(obj, list):
        return [sanitize_obj(x) for x in obj]
    if isinstance(obj, tuple):
        return [sanitize_obj(x) for x in obj]
    if isinstance(obj, dict):
        return dict((sanitize_obj(k), sanitize_obj(v)) for k, v in obj.items())
    return obj


def write_committed(path, text, disclose=False):
    """Write a committed text artifact after sanitizing it. With disclose=True
    the DISCLOSURE line is added after the first heading (Markdown)."""
    text = sanitize_text(text)
    if disclose:
        text = sanitize_artifacts.disclose_markdown(text)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(str(p), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return p


def write_committed_json(path, obj):
    import json
    return write_committed(path, json.dumps(sanitize_obj(obj), indent=2, ensure_ascii=False) + "\n")
