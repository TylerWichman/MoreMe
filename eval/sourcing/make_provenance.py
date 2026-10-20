"""Fill the per-document tables in eval/corpus/PROVENANCE.md from build_report.json.

Usage: python eval/sourcing/make_provenance.py [--report eval/sourcing/build_report.json]

Each persona section in PROVENANCE.md holds an "Attribution template:" line and a
pair of markers. Everything between the markers is replaced with one table row per
document. The template's {title}, {date}, {url} fields are filled per document.
"""
import argparse
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PROV = os.path.join(HERE, "..", "corpus", "PROVENANCE.md")
LICENSE_NAMES = {"OGL-3.0": "OGL v3.0", "CC-BY-SA-4.0": "CC BY-SA 4.0", "US-PD": "Public domain (USA)"}


def cell(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=os.path.join(HERE, "build_report.json"))
    a = ap.parse_args()
    report = json.load(open(a.report, encoding="utf-8"))
    text = open(PROV, encoding="utf-8").read()
    for p in report["personas"]:
        pid = p["id"]
        sec = text[text.index("## %s\n" % pid):]
        tmpl = re.search(r"^- Attribution template: `(.+)`$", sec, re.M).group(1)
        rows = ["| File | Source URL | Title or section | Date | License | Words | Attribution text |",
                "|---|---|---|---|---|---|---|"]
        for d in p["docs"]:
            date = d["date"] or "see section"
            attrib = tmpl.format(title=d["title"], date=d["date"], url=d["url"])
            rows.append("| `%s` | %s | %s | %s | %s | %d | %s |" % (
                d["file"], d["url"], cell(d["title"]), date, LICENSE_NAMES[d["license"]], d["words"], cell(attrib)))
        rows.append("")
        rows.append("%d documents, %d words. License evidence matched on every page: %s" % (
            len(p["docs"]), p["words"], cell(p["docs"][0]["evidence"])))
        block = "<!-- docs:%s:start -->\n%s\n<!-- docs:%s:end -->" % (pid, "\n".join(rows), pid)
        text = re.sub(r"<!-- docs:%s:start -->.*?<!-- docs:%s:end -->" % (re.escape(pid), re.escape(pid)),
                      lambda m: block, text, flags=re.S)
    with open(PROV, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("updated", os.path.normpath(PROV))


if __name__ == "__main__":
    main()
