"""Pre-registration hash gate (AD-006 Pre-registration).

eval/PREREGISTRATION.md holds a machine-readable block:

    <!-- prereg-hashes:start -->
    status: draft            (or: frozen)
    <sha256>  <repo-relative path>
    ...
    <!-- prereg-hashes:end -->

Held-out scoring and held-out drafting call require_frozen(), which raises
PreregError unless the status is frozen and every listed file still hashes to
the recorded value (line endings normalized to LF). Nothing in this module
freezes the file on its own: `freeze` is a separate, explicit command for the
pre-registration ticket.

    cd eval && python -m harness.prereg hashes         print current hashes
    cd eval && python -m harness.prereg write-hashes   refresh the block (status kept)
    cd eval && python -m harness.prereg check          exit 0 only if frozen and matching
    cd eval && python -m harness.prereg freeze         set status frozen and write hashes
"""
import re
import sys
from pathlib import Path

from harness import common

START = "<!-- prereg-hashes:start -->"
END = "<!-- prereg-hashes:end -->"


class PreregError(RuntimeError):
    """The pre-registration is not frozen or a hashed file changed."""


def hashed_files(repo=common.REPO):
    repo = Path(repo)
    fixed = ["moreme/SKILL.md", "moreme/templates/my-voice/SKILL.md.tmpl", "moreme/analyze.py",
             "eval/reference_stats.json", "eval/split.json", "eval/tasks/tasks.json", "eval/lib/childrun.py"]
    harness = sorted(p.relative_to(repo).as_posix() for p in (repo / "eval" / "harness").glob("*.py"))
    return fixed + harness


def current_hashes(repo=common.REPO):
    repo = Path(repo)
    out = []
    for r in hashed_files(repo):
        p = repo / r
        out.append((r, common.sha256_text_file(p) if p.exists() else "missing"))
    return out


def parse_block(text):
    if START not in text or END not in text:
        raise PreregError("no hash block in PREREGISTRATION.md")
    body = text.split(START, 1)[1].split(END, 1)[0]
    status = None
    hashes = {}
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("```"):
            continue
        m = re.match(r"^status:\s*(\w+)$", line)
        if m:
            status = m.group(1)
            continue
        m = re.match(r"^([0-9a-f]{64}|missing)\s+(\S+)$", line)
        if m:
            hashes[m.group(2)] = m.group(1)
    return status, hashes


def render_block(status, hashes):
    lines = [START, "```", "status: %s" % status]
    lines += ["%s  %s" % (h, r) for r, h in hashes]
    lines += ["```", END]
    return "\n".join(lines)


def mismatches(recorded, repo=common.REPO):
    now = dict(current_hashes(repo))
    bad = []
    for r, h in sorted(now.items()):
        if recorded.get(r) != h:
            bad.append("%s: recorded %s, now %s" % (r, recorded.get(r, "absent"), h))
    for r in sorted(set(recorded) - set(now)):
        bad.append("%s: recorded but no longer hashed" % r)
    return bad


def require_frozen(path=None, repo=common.REPO):
    path = Path(path or common.PREREG)
    if not path.exists():
        raise PreregError("PREREGISTRATION.md not found; held-out scoring refused")
    status, recorded = parse_block(path.read_text(encoding="utf-8"))
    if status != "frozen":
        raise PreregError("pre-registration status is %r, not frozen; held-out scoring refused" % status)
    bad = mismatches(recorded, repo)
    if bad:
        raise PreregError("hash mismatch; held-out scoring refused: " + "; ".join(bad))
    return True


def write_hashes(path=None, status=None, repo=common.REPO):
    path = Path(path or common.PREREG)
    text = path.read_text(encoding="utf-8")
    old_status, _ = parse_block(text)
    block = render_block(status or old_status or "draft", current_hashes(repo))
    pre = text.split(START, 1)[0]
    post = text.split(END, 1)[1]
    common.write_text(path, pre + block + post)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "check"
    if cmd == "hashes":
        for r, h in current_hashes():
            print("%s  %s" % (h, r))
        return 0
    if cmd == "write-hashes":
        write_hashes()
        print("hash block refreshed")
        return 0
    if cmd == "freeze":
        write_hashes(status="frozen")
        print("frozen")
        return 0
    try:
        require_frozen()
    except PreregError as ex:
        print(str(ex), file=sys.stderr)
        return 1
    print("ok: frozen and every hash matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
