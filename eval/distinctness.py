"""Persona distinctness check (assumption A-004), using analyze.py only.

    python eval/distinctness.py [--out eval/distinctness.json]

For each persona, its train split and its dev split are each profiled in view
`all` with `analyze.py profile`. Then `analyze.py compare --reference-stats
eval/reference_stats.json` gives delta_fw for every (train of P, dev of Q) pair.

within(P)   = delta_fw(train P, dev P)
cross(P, Q) = delta_fw(train P, dev Q), Q != P

The check passes when, for every pair P != Q, within(P) < cross(P, Q) and
within(Q) < cross(Q, P): each persona's dev text is closer to its own train text
than any other persona's dev text is. Heldout text is never read.
Exit 0 on pass, 1 on fail. The pass/fail verdict is this train-vs-dev check only.

Supplementary (descriptive, does not change the verdict): with --chunks, the
train text of each persona is cut into consecutive 1,000-word chunks (the same
unit reference-stats uses) and delta_fw is computed for every pair of chunks.
It reports the mean within-persona and cross-persona chunk distance.
"""
import argparse
import json
import os
import subprocess
import sys
import re
import tempfile
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ANALYZE = os.path.join(REPO, "moreme", "analyze.py")
SPLIT_PY = os.path.join(HERE, "split.py")
REF = os.path.join(HERE, "reference_stats.json")


def run(args):
    p = subprocess.run([sys.executable, ANALYZE] + args, capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise SystemExit("analyze.py %s failed (%d): %s" % (args[0], p.returncode, p.stderr.strip()))
    return p.stdout


WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*")


def chunks(text, n=1000):
    """Consecutive n-word chunks, raw text from first word start to last word end; remainder dropped."""
    text = unicodedata.normalize("NFC", text)
    mapped = text.replace("’", "'").replace("‘", "'")
    spans = [m.span() for m in WORD.finditer(mapped)]
    return [text[spans[i][0]:spans[i + n - 1][1]] for i in range(0, len(spans) - n + 1, n)]


def chunk_analysis(tmp, personas, ref):
    paths = []
    for pid in personas:
        d = os.path.join(tmp, "train", pid)
        joined = "\n\n".join(open(os.path.join(d, f), encoding="utf-8").read().strip("\n")
                             for f in sorted(os.listdir(d)))
        for k, c in enumerate(chunks(joined)):
            src = os.path.join(tmp, "chunk-%s-%02d.txt" % (pid, k))
            with open(src, "w", encoding="utf-8", newline="\n") as f:
                f.write(c)
            out = src[:-4] + ".json"
            run(["profile", "--view", "all", "--out", out, src])
            paths.append((pid, out))
    sums, counts = dict(), dict()
    res = os.path.join(tmp, "cmpc.json")
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            (p, a), (q, b) = paths[i], paths[j]
            run(["compare", a, b, "--reference-stats", ref, "--out", res])
            with open(res, encoding="utf-8") as f:
                d = json.load(f)["delta_fw"]
            for key in set([(p, q), (q, p)]):
                sums[key] = sums.get(key, 0.0) + d
                counts[key] = counts.get(key, 0) + 1
    mean = dict((p, dict((q, round(sums[(p, q)] / counts[(p, q)], 4)) for q in personas)) for p in personas)
    ok = dict((p, all(mean[p][p] < mean[p][q] for q in personas if q != p)) for p in personas)
    return dict(unit="1000-word train chunks, all pairs", mean_delta_fw=mean,
                within_below_every_cross=ok, all_personas=all(ok.values()))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "distinctness.json"))
    ap.add_argument("--reference-stats", default=REF)
    ap.add_argument("--chunks", action="store_true", help="add the supplementary chunk-level table")
    a = ap.parse_args(argv)
    chunk_result = None
    with tempfile.TemporaryDirectory(prefix="moreme-distinct-") as tmp:
        for split in ("train", "dev"):
            subprocess.run([sys.executable, SPLIT_PY, "materialize", "--split", split,
                            "--out", os.path.join(tmp, split)], check=True, capture_output=True)
        personas = sorted(os.listdir(os.path.join(tmp, "train")))
        prof = {}
        for split in ("train", "dev"):
            for pid in personas:
                d = os.path.join(tmp, split, pid)
                files = sorted(os.path.join(d, f) for f in os.listdir(d))
                out = os.path.join(tmp, "%s-%s.json" % (split, pid))
                run(["profile", "--view", "all", "--out", out] + files)
                prof[(split, pid)] = out
        matrix = {}
        for p in personas:
            matrix[p] = {}
            for q in personas:
                res = os.path.join(tmp, "cmp.json")
                run(["compare", prof[("train", p)], prof[("dev", q)], "--reference-stats", a.reference_stats,
                     "--out", res])
                with open(res, encoding="utf-8") as f:
                    matrix[p][q] = json.load(f)["delta_fw"]
        if a.chunks:
            chunk_result = chunk_analysis(tmp, personas, a.reference_stats)
    failures = []
    for p in personas:
        for q in personas:
            if p != q and not matrix[p][p] < matrix[p][q]:
                failures.append("within(%s)=%.4f is not below cross(%s, %s)=%.4f" % (p, matrix[p][p], p, q, matrix[p][q]))
    margin = {p: round(min(matrix[p][q] for q in personas if q != p) - matrix[p][p], 4) for p in personas}
    with open(a.reference_stats, encoding="utf-8") as f:
        ref_meta = json.load(f)
    result = {
        "schema_version": "1",
        "metric": "delta_fw",
        "rows": "train split of persona P",
        "columns": "dev split of persona Q",
        "reference_stats_created": ref_meta.get("created"),
        "personas": personas,
        "matrix": matrix,
        "within": {p: matrix[p][p] for p in personas},
        "nearest_other": {p: min((matrix[p][q], q) for q in personas if q != p)[1] for p in personas},
        "margin": margin,
        "passed": not failures,
        "failures": failures,
        "supplementary_chunks": chunk_result,
    }
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, indent=1)
        f.write("\n")
    for p in personas:
        print("%-9s within %.4f  nearest other %.4f (%s)  margin %.4f" % (
            p, matrix[p][p], matrix[p][result["nearest_other"][p]], result["nearest_other"][p], margin[p]))
    if chunk_result:
        for p in personas:
            others = [(chunk_result["mean_delta_fw"][p][q], q) for q in personas if q != p]
            print("chunks %-9s within %.4f  nearest other %.4f (%s)" % (
                p, chunk_result["mean_delta_fw"][p][p], min(others)[0], min(others)[1]))
    print("PASS" if not failures else "FAIL")
    for f in failures:
        print(f, file=sys.stderr)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
