"""Survey one opensource.com author: list articles, check sole byline and CC BY-SA field.

Usage: python survey_osc.py USER_SLUG --cache DIR --out candidates.json
"""
import argparse
import html as htmlmod
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from fetchlib import count_words, extract_paragraphs, fetch  # noqa: E402

CC_RE = re.compile(
    r'field--name-field-default-license[^>]*><a rel="license" href="https://creativecommons\.org/licenses/by-sa/4\.0/">'
    r'.*?This work is licensed under a Creative Commons Attribution-Share Alike 4\.0 International License\.', re.S)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-pages", type=int, default=15)
    ap.add_argument("--extra", nargs="*", default=[], help="extra /article/ paths found elsewhere")
    a = ap.parse_args()
    urls = []
    for n in range(a.max_pages):
        html, st = fetch("https://opensource.com/users/%s?page=%d" % (a.slug, n), a.cache)
        new = [u for u in dict.fromkeys(re.findall(r'href="(/article/[^"#?]+)"', html)) if u not in urls]
        if st != 200 or not new:
            break
        urls.extend(new)
    urls.extend(u for u in a.extra if u not in urls)
    rows = []
    for path in urls:
        u = "https://opensource.com" + path
        html, st = fetch(u, a.cache)
        if st != 200:
            continue
        alist = re.search(r'class="author__list">(.*?)</div>', html, re.S)
        authors = re.findall(r'href="/users/([^"]+)"', alist.group(1)) if alist else []
        title = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        date = re.search(r'class="author__meta-date">([^<]+)<', html)
        body = re.search(r'field--name-body.*?(?=<div class="views-element-container author-block)', html, re.S)
        btxt = body.group(0) if body else ""
        paras = extract_paragraphs(html, "div", "field--name-body")
        rows.append({
            "url": u,
            "title": htmlmod.unescape(re.sub(r"<[^>]+>", "", title.group(1)).strip()) if title else "",
            "date": date.group(1).strip() if date else "",
            "authors": authors,
            "cc_by_sa_field": bool(CC_RE.search(html)),
            "code_blocks": btxt.count("<pre"),
            "blockquotes": btxt.count("<blockquote"),
            "words": count_words("\n\n".join(paras)),
        })
    json.dump(rows, open(a.out, "w", encoding="utf-8"), indent=1)
    for r in rows:
        print(r["date"], r["words"], ",".join(r["authors"]), r["cc_by_sa_field"], "pre=%d" % r["code_blocks"],
              "bq=%d" % r["blockquotes"], r["title"][:60])
    print("total", len(rows), "words", sum(r["words"] for r in rows))


if __name__ == "__main__":
    main()
