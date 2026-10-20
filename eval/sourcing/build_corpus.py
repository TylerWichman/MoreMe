"""Build eval/corpus/<persona-id>/*.txt from the sources in sources.json.

Usage:
    python eval/sourcing/build_corpus.py --cache DIR [--out eval/corpus] [--report report.json]

DIR holds raw downloads (kept outside the repo). Every page is checked for its
license at fetch time; a page that fails the check is skipped and reported.
Output files are plain UTF-8 (no BOM, LF line endings), one paragraph per
block, no titles, datelines, salutations, signatures, footnotes, images,
block quotes, verse, or bracketed editorial insertions.

The report (JSON) lists, per document: persona, file, source URL, title, date,
word count, and the license evidence that was matched. PROVENANCE.md is
written from it by make_provenance.py.
"""
import argparse
import datetime
import html as htmlmod
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetchlib import count_words, extract_paragraphs, fetch  # noqa: E402

OGL_RE = re.compile(
    r"All content is available under the <a[^>]*href=\"https://www\.nationalarchives\.gov\.uk/doc/"
    r"open-government-licence/version/3/\"[^>]*>Open Government Licence v3\.0</a>, except where otherwise stated")
CC_RE = re.compile(
    r'field--name-field-default-license[^>]*><a rel="license" href="https://creativecommons\.org/licenses/by-sa/4\.0/">'
    r'.*?This work is licensed under a Creative Commons Attribution-Share Alike 4\.0 International License\.', re.S)
PG_RIGHTS_RE = re.compile(r'<td property="dcterms:rights">Public domain in the USA\.</td>')

# Paragraphs on GOV.UK posts that are site furniture or contact lines, not the post.
GOV_DROP = re.compile(r"^(Follow \w+ on Twitter|You can follow|Sign up for|Subscribe to|Find out more|"
                      r"Follow GDS on Twitter|Keep in touch)", re.I)


QUOTE_RE = re.compile(r'[“"]([^”"]+)[”"]')


def drop_quoted(paras, min_words=6):
    """Remove each sentence that contains a quotation of min_words or more words.

    Quotations that long are usually someone else's words (third-party material),
    which the OGL excludes and which would not be the persona's own style.
    """
    out = []
    for p in paras:
        while True:
            m = next((m for m in QUOTE_RE.finditer(p) if len(m.group(1).split()) >= min_words), None)
            if not m:
                break
            a = max(p.rfind(". ", 0, m.start()), p.rfind("? ", 0, m.start()), p.rfind("! ", 0, m.start()))
            a = 0 if a < 0 else a + 2
            after = p[m.end():]
            ends_here = re.match(r"[.!?,;:]*(?=\s+[A-Z“\"]|\s*$)", after)
            if ends_here and (ends_here.end() or m.group(1).rstrip()[-1:] in ".!?"):
                b = m.end() + ends_here.end()
            else:
                tail = re.search(r"[.!?][”\"’']*(\s|$)", after)
                b = len(p) if not tail else m.end() + tail.end()
            p = (p[:a] + p[b:]).strip()
            p = re.sub(r"\s+", " ", p)
        if count_words(p) > 0:
            out.append(p)
    return out


def web_clean(paras, author_name=None):
    """Drop video transcripts (other speakers), image credits, and headings or list
    fragments (under 10 words with no closing punctuation). Paragraphs naming the
    author in the third person (standfirsts, bios, sign-offs) are editorial furniture."""
    out = []
    for p in paras:
        if author_name and author_name in p:
            continue
        if re.match(r"^Transcript:?\s*$", p):
            break
        if re.match(r"^(Image by|\((Taken from|Image|Source|Credit))", p):
            continue
        if count_words(p) < 10 and not re.search(r"[.!?:;\"”’)\]]$", p):
            continue
        out.append(p)
    return out


def today():
    return datetime.datetime.now().strftime("%Y-%m-%d")


def strip_title(t):
    return htmlmod.unescape(re.sub(r"<[^>]+>", "", t)).strip()


# ---------------------------------------------------------------- web sources

def build_govuk(p, cache):
    docs, skipped = [], []
    host = "https://gds.blog.gov.uk/"
    for url in p["urls"]:
        html, st = fetch(url, cache)
        art = re.search(r"<article.*?</article>", html, re.S)
        art = art.group(0) if art else ""
        authors = sorted(set(re.findall(r'href="(%sauthor/[^"]+)"[^>]*rel="author"' % re.escape(host), art)))
        ok_lic = bool(OGL_RE.search(html))
        if st != 200 or authors != [p["byline"]] or not ok_lic:
            skipped.append({"url": url, "reason": "status %s, authors %s, ogl %s" % (st, authors, ok_lic)})
            continue
        name = re.search(r'rel="author">([^<]+?)(?: - [^<]*)?</a>', art)
        name = name.group(1).strip() if name else None
        paras = web_clean(drop_quoted(
            [x for x in extract_paragraphs(html, "div", "entry-content") if not GOV_DROP.match(x)]), name)
        title = re.search(r"<h1[^>]*>(.*?)</h1>", art, re.S)
        date = re.search(r'<time[^>]*datetime="([^"]+)"', art)
        docs.append({
            "url": url, "title": strip_title(title.group(1)) if title else "",
            "date": date.group(1)[:10] if date else "", "paras": paras,
            "license": "OGL-3.0",
            "evidence": "Page footer: 'All content is available under the Open Government Licence v3.0, "
                        "except where otherwise stated' (link to nationalarchives.gov.uk/doc/open-government-licence/version/3/); "
                        "single byline link %s" % p["byline"],
            "changes": "Text of the post body only. Removed title, images, captions, embedded media, block quotes "
                       "(quoted third-party material), tables, links (anchor text kept), sharing and comment sections, "
                       "and site navigation. Removed every sentence containing a quotation of six or more words (quoted "
                       "third-party material), video transcripts, image credits, paragraphs naming the author in the third "
                       "person (standfirst, bio, sign-off), and headings or list "
                       "fragments under ten words with no closing punctuation. Formatting stripped; one paragraph per block.",
        })
    return docs, skipped


def build_osc(p, cache):
    docs, skipped = [], []
    for url in p["urls"]:
        html, st = fetch(url, cache)
        alist = re.search(r'class="author__list">(.*?)</div>', html, re.S)
        authors = re.findall(r'href="/users/([^"]+)"', alist.group(1)) if alist else []
        ok_lic = bool(CC_RE.search(html))
        if st != 200 or authors != [p["byline"]] or not ok_lic:
            skipped.append({"url": url, "reason": "status %s, authors %s, cc %s" % (st, authors, ok_lic)})
            continue
        name = re.search(r'href="/users/[^"]+"[^>]*>([^<]+)</a>', alist.group(1))
        name = name.group(1).strip() if name else None
        title = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        date = re.search(r'class="author__meta-date">([^<]+)<', html)
        d = date.group(1).strip() if date else ""
        try:
            d = datetime.datetime.strptime(d, "%B %d, %Y").strftime("%Y-%m-%d")
        except ValueError:
            pass
        docs.append({
            "url": url, "title": strip_title(title.group(1)) if title else "", "date": d,
            "paras": web_clean(drop_quoted(extract_paragraphs(html, "div", "field--name-body")), name),
            "license": "CC-BY-SA-4.0",
            "evidence": "Article license field: 'This work is licensed under a Creative Commons Attribution-Share "
                        "Alike 4.0 International License.' (rel=license link to creativecommons.org/licenses/by-sa/4.0/); "
                        "single byline /users/%s" % p["byline"],
            "changes": "Text of the article body only. Removed title, byline, images, captions, block quotes, code "
                       "blocks, tables, links (anchor text kept), author bio, and comments. Removed every sentence containing "
                       "a quotation of six or more words (quoted third-party material), image credits, paragraphs naming "
                       "the author in the third person, and headings or "
                       "list fragments under ten words with no closing punctuation. Formatting stripped; "
                       "one paragraph per block.",
        })
    return docs, skipped


# ---------------------------------------------------------------- Project Gutenberg

def pg_body(raw):
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    a = re.search(r"^\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG EBOOK.*$", raw, re.M)
    b = re.search(r"^\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG EBOOK.*$", raw, re.M)
    return raw[a.end():b.start()].split("\n")


def clean_block(lines):
    """Drop indented lines (verse, notes, datelines, signatures) and unwrap a paragraph."""
    keep = [ln for ln in lines if not re.match(r"^\s{2,}\S", ln)]
    t = " ".join(ln.strip() for ln in keep).strip()
    t = re.sub(r"\[[^\]]*\]", "", t)          # bracketed editorial insertions and footnote markers
    t = t.replace("_", "")                     # PG italics markers
    t = re.sub(r"\s+", " ", t).strip()
    return t


def blocks_of(lines):
    out, cur = [], []
    for ln in lines:
        if ln.strip() == "":
            if cur:
                out.append(cur)
                cur = []
        else:
            cur.append(ln)
    if cur:
        out.append(cur)
    return out


def is_heading(block):
    t = " ".join(x.strip() for x in block)
    letters = [c for c in t if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters) and len(t) < 90


def paras_from(lines):
    paras, in_footnote = [], False
    for blk in blocks_of(lines):
        first = blk[0].strip()
        if first.startswith("FOOTNOTE") or re.match(r"^\[(\d+|Footnote)", first):
            in_footnote = True
            continue
        if in_footnote and re.match(r"^\s*\[", blk[0]):
            continue
        in_footnote = False
        if is_heading(blk) or re.match(r"^\s*\*(\s+\*)+\s*$", blk[0]):
            continue
        t = clean_block(blk)
        if t and count_words(t) > 0:
            paras.append(t)
    return paras


def split_letters(lines):
    """Letters of a homesteader: one document per letter; letter XXI (by the writer's child) excluded."""
    docs, cur, num = [], None, None
    start = next(i for i, ln in enumerate(lines) if ln.strip() == "LETTERS OF A WOMAN HOMESTEADER" and i > 120)
    for ln in lines[start + 1:]:
        s = ln.strip()
        if re.fullmatch(r"[IVXL]+", s):
            if cur is not None:
                docs.append((num, cur))
            cur, num = [], s
            continue
        if s == "THE END":
            break
        if cur is not None:
            if re.fullmatch(r"[A-Z ,.']*DEAR[A-Z ,.']*,--", s):
                continue  # salutation
            cur.append(ln)
    if cur is not None:
        docs.append((num, cur))
    return [(n, paras_from(c)) for n, c in docs if n != "XXI"]


def split_diary(lines):
    """Diary: one document per dated entry (an indented dateline naming a month starts a new entry)."""
    months = "January|February|March|April|May|June|July|August|September|October|November|December"
    start = next(i for i, ln in enumerate(lines) if ln.strip() == "BOOK I")
    docs, cur, label = [], None, None
    for ln in lines[start + 1:]:
        s = ln.strip()
        if s == "THE END":
            break
        if re.match(r"^\s{20,}\S", ln) and re.search(months, s):
            if cur:
                docs.append((label, cur))
            cur, label = [], "Entry headed " + s.rstrip(".,")
            continue
        if cur is not None:
            cur.append(ln)
    if cur:
        docs.append((label, cur))
    return [(lab, paras_from(c)) for lab, c in docs]


def split_weeks(lines):
    """Garden essays: dedication, preliminary, and one document per week. Introductory letter by another writer excluded."""
    heads = ["BY WAY OF DEDICATION", "PRELIMINARY"]
    idx = [i for i, ln in enumerate(lines) if ln.strip() in heads or re.fullmatch(r"[A-Z]+ WEEK", ln.strip())]
    idx = [i for i in idx if i > 130]
    end = next(i for i, ln in enumerate(lines) if ln.strip() == "CALVIN" and i > idx[-1])
    out = []
    for k, i in enumerate(idx):
        j = idx[k + 1] if k + 1 < len(idx) else end
        body = [ln for ln in lines[i + 1:j] if not re.fullmatch(r"\s*C\. D\. W\.\s*", ln)]
        out.append((lines[i].strip(), paras_from(body)))
    return out


def split_talks(lines):
    """Sunday evening talks: one document per talk; publishers' note, preface, and contents excluded."""
    ci = next(i for i, ln in enumerate(lines) if ln.strip() == "CONTENTS")
    titles = []
    for ln in lines[ci + 1:]:
        m = re.match(r"^\s*([A-Z][A-Z .,;:!?'\-\"]+?)\s{2,}\d+\s*$", ln)
        if m:
            titles.append(m.group(1).strip())
        elif titles and ln.strip() == "":
            continue
        elif titles and not m and ln.strip():
            break
    body_start = next(i for i, ln in enumerate(lines) if i > ci and ln.strip() == "CHARACTER BUILDING")
    pos = []
    for t in titles:
        for i in range(pos[-1][0] + 1 if pos else body_start, len(lines)):
            if lines[i].strip().rstrip(".") == t.rstrip("."):
                pos.append((i, t))
                break
    out = []
    for k, (i, t) in enumerate(pos):
        j = pos[k + 1][0] if k + 1 < len(pos) else len(lines)
        out.append((t, paras_from(lines[i + 1:j])))
    return out


PARSERS = {"letters": split_letters, "diary": split_diary, "weeks": split_weeks, "talks": split_talks}


def build_pg(p, cache, cap):
    n = p["pg_id"]
    page_url = "https://www.gutenberg.org/ebooks/%d" % n
    txt_url = "https://www.gutenberg.org/cache/epub/%d/pg%d.txt" % (n, n)
    page, _ = fetch(page_url, cache)
    if not PG_RIGHTS_RE.search(page):
        return [], [{"url": page_url, "reason": "catalog page does not say 'Public domain in the USA.'"}]
    raw, _ = fetch(txt_url, cache)
    parts = PARSERS[p["parser"]](pg_body(raw))
    docs, total = [], 0
    for label, paras in parts:
        if total >= cap:
            break
        w = count_words("\n\n".join(paras))
        if w == 0:
            continue
        total += w
        docs.append({
            "url": txt_url, "catalog": page_url, "title": label, "date": p.get("published", ""), "paras": paras,
            "license": "US-PD",
            "evidence": "Project Gutenberg catalog page %s: 'Copyright Status: Public domain in the USA.'" % page_url,
            "changes": "Removed the Project Gutenberg header, footer, and license, all Project Gutenberg references, "
                       "front matter, publisher's or editor's introductions, contents, illustrations, chapter titles, "
                       "datelines, salutations, signatures, indented verse and notes, footnotes and footnote markers, "
                       "bracketed editorial insertions, and underscore italics marks. Line wraps joined into paragraphs.",
            "section": label,
        })
    return docs, []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", default=os.path.join(HERE, "..", "corpus"))
    ap.add_argument("--report", required=True)
    a = ap.parse_args()
    cfg = json.load(open(os.path.join(HERE, "sources.json"), encoding="utf-8"))
    report = {"checked": today(), "personas": [], "skipped": []}
    for p in cfg["personas"]:
        if p["kind"] == "govuk":
            docs, sk = build_govuk(p, a.cache)
        elif p["kind"] == "osc":
            docs, sk = build_osc(p, a.cache)
        else:
            docs, sk = build_pg(p, a.cache, p.get("word_cap", cfg["pg_word_cap"]))
        report["skipped"].extend(dict(s, persona=p["id"]) for s in sk)
        pdir = os.path.join(a.out, p["id"])
        os.makedirs(pdir, exist_ok=True)
        for f in os.listdir(pdir):
            if f.endswith(".txt"):
                os.remove(os.path.join(pdir, f))
        rows = []
        for k, d in enumerate(docs, 1):
            fname = "%s-%02d.txt" % (p["id"], k)
            text = "\n\n".join(d["paras"]) + "\n"
            with open(os.path.join(pdir, fname), "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            row = {k2: v for k2, v in d.items() if k2 != "paras"}
            row.update(file="corpus/%s/%s" % (p["id"], fname), words=count_words(text))
            rows.append(row)
        report["personas"].append({"id": p["id"], "kind": p["kind"], "demo_candidate": bool(p.get("demo_candidate")),
                                   "docs": rows, "words": sum(r["words"] for r in rows)})
        print(p["id"], len(rows), "docs", sum(r["words"] for r in rows), "words", "skipped", len(sk))
    json.dump(report, open(a.report, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
