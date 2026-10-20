"""Physical leakage control (AD-006).

Before every skill-generation or drafting run: assert that no dev or held-out
corpus file (by name or by content hash) is in the scratch project, through
eval/lib/childrun.assert_train_only. Draft scratch projects must also hold
nothing but .claude/settings.json and, in the `with` arm, the my-voice skill.

After a run: no 12-word shingle of any held-out (or dev) document may appear in
transcripts, generated skills, or drafts' prompts. Shingles are compared as
sha1 digests of lowercased FROZEN 1 words, so reports never print corpus text.
"""
import hashlib
from pathlib import Path

from harness import common

cr = common.childrun


def assert_draft_scratch(scratch, split, arm):
    """Raise ScratchError on dev/held-out text or any unexpected file."""
    cr.assert_train_only(scratch, common.CORPUS, split)
    scratch = Path(scratch)
    for f in scratch.rglob("*"):
        if not f.is_file():
            continue
        r = f.relative_to(scratch).as_posix()
        if r == ".claude/settings.json":
            continue
        if arm == "with" and r.startswith(".claude/skills/my-voice/"):
            continue
        raise cr.ScratchError("unexpected file in draft scratch project: %s" % r)


def shingles(text, n=common.SHINGLE_WORDS):
    w = [x.lower() for x in common.words(text)]
    out = set()
    for i in range(len(w) - n + 1):
        out.add(hashlib.sha1(" ".join(w[i:i + n]).encode("utf-8")).hexdigest())
    return out


def corpus_shingles(split, which=("heldout",)):
    """{relative doc path: shingle set} for the named splits. This is the only
    harness function that opens held-out text, and it keeps digests only."""
    out = {}
    for meta in split["personas"].values():
        for d in meta["documents"]:
            if d["split"] in which:
                out[d["file"]] = shingles(common.read_corpus_text(split, d["file"], allow=which))
    return out


def scan_files(paths, doc_shingles):
    """[(file, doc, shared shingle count)] for every overlap found."""
    hits = []
    for p in paths:
        try:
            text = Path(p).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        s = shingles(text)
        if not s:
            continue
        for doc, ds in doc_shingles.items():
            k = len(s & ds)
            if k:
                hits.append((common.rel(p), doc, k))
    return hits


def scan_texts(named_texts, doc_shingles):
    hits = []
    for name, text in named_texts:
        s = shingles(text)
        for doc, ds in doc_shingles.items():
            k = len(s & ds)
            if k:
                hits.append((name, doc, k))
    return hits


def leakage_targets(repo=common.REPO):
    """Files the shingle test covers: generated persona skills, e2e transcripts
    and logs, harness draft records (they hold each unit's prompt)."""
    repo = Path(repo)
    globs = ["eval/skills/**/*", "eval/e2e/runs/**/*", "eval/results/**/*", "docs/example-run/**/*",
             "docs/transcript*.md", "docs/transcripts/**/*"]
    seen = set()
    for g in globs:
        for f in repo.glob(g):
            if f.is_file() and f.suffix.lower() in (".md", ".txt", ".json", ".jsonl") and f not in seen:
                seen.add(f)
                yield f
