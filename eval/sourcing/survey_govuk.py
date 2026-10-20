"""Survey one GOV.UK blog author: list posts, check byline and OGL footer, count words.

Usage: python survey_govuk.py AUTHOR_URL --cache DIR --out candidates.json
"""
import argparse
import html as htmlmod
import json
import re
import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
from fetchlib import count_words, extract_paragraphs, fetch  # noqa: E402

OGL_RE = re.compile(
    r"All content is available under the <a[^>]*href=\"https://www\.nationalarchives\.gov\.uk/doc/"
    r"open-government-licence/version/3/\"[^>]*>Open Government Licence v3\.0</a>, except where otherwise stated")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("author_url")
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-pages", type=int, default=20)
    a = ap.parse_args()
    base = a.author_url.rstrip("/") + "/"
    host = re.match(r"https://[^/]+/", base).group(0)
    post_re = re.compile(r'href="(%s20\d\d/\d\d/\d\d/[a-z0-9-]+/)"' % re.escape(host))
    urls = []
    for n in range(1, a.max_pages + 1):
        page = base if n == 1 else "%spage/%d/" % (base, n)
        html, st = fetch(page, a.cache)
        if st != 200:
            break
        # only links inside <article> blocks on the listing (skip sidebar "recent posts")
        for art in re.findall(r"<article.*?</article>", html, re.S):
            for u in post_re.findall(art):
                if u not in urls:
                    urls.append(u)
    rows = []
    for u in urls:
        html, st = fetch(u, a.cache)
        art = re.search(r"<article.*?</article>", html, re.S)
        art = art.group(0) if art else ""
        authors = sorted(set(re.findall(r'href="(%sauthor/[^"]+)"[^>]*rel="author"' % re.escape(host), art)))
        title = re.search(r'<h1[^>]*>(.*?)</h1>', art, re.S)
        date = re.search(r'<time[^>]*datetime="([^"]+)"', art)
        paras = extract_paragraphs(html, "div", "entry-content")
        text = "\n\n".join(paras)
        rows.append({
            "url": u,
            "title": htmlmod.unescape(re.sub(r"<[^>]+>", "", title.group(1)).strip()) if title else "",
            "date": date.group(1) if date else "",
            "authors": authors,
            "ogl_footer": bool(OGL_RE.search(html)),
            "blockquotes": art.count("<blockquote"),
            "words": count_words(text),
        })
    json.dump(rows, open(a.out, "w", encoding="utf-8"), indent=1)
    for r in rows:
        print(r["date"][:10], r["words"], len(r["authors"]), r["ogl_footer"], r["blockquotes"], r["title"][:70])
    print("total posts", len(rows), "words", sum(r["words"] for r in rows))


if __name__ == "__main__":
    main()
