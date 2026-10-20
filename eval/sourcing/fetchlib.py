"""Fetch and HTML-extraction helpers used to build eval/corpus/.

Build-time only. Nothing in moreme/ imports this, and the shipped skill makes
no network calls. Raw downloads go to a cache folder outside the repo (the
--cache argument of each build script); only cleaned text is committed.
"""
import hashlib
import os
import re
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser

UA = "Mozilla/5.0 (MoreMe eval corpus build)"


def fetch(url, cache_dir, tries=6):
    """Return (text, status). Cached by URL hash; retries connection resets."""
    os.makedirs(cache_dir, exist_ok=True)
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    path = os.path.join(cache_dir, key + ".raw")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read().decode("utf-8", "replace"), 200
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                data = r.read()
            with open(path, "wb") as f:
                f.write(data)
            time.sleep(0.7)
            return data.decode("utf-8", "replace"), 200
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "", 404
            last = e
        except Exception as e:  # connection resets happen on GOV.UK blogs
            last = e
        time.sleep(1.5 * (i + 1))
    raise RuntimeError("fetch failed %s: %s" % (url, last))


BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "div", "tr", "dd", "dt", "section"}
VOID = {"br", "img", "hr", "input", "meta", "link", "source", "wbr", "col", "area", "embed"}
# Dropped with everything inside them: quoted third-party text, media, code, tables.
SKIP = {"script", "style", "blockquote", "figure", "figcaption", "iframe", "noscript",
        "svg", "pre", "code", "table", "form", "button", "aside", "q", "video", "audio"}
# Elements dropped by class: image captions and credits, sidebar resource lists.
SKIP_CLASSES = {"caption", "wp-caption", "wp-caption-text", "field--name-field-caption",
                "embedded-resource-list", "embedded-callout-menu", "callout-float-right", "media", "visually-hidden", "govuk-visually-hidden"}


class Extract(HTMLParser):
    """Collect paragraph text inside the first element <tag class~=cls>."""

    def __init__(self, tag, cls):
        super().__init__(convert_charrefs=True)
        self.tt, self.tc = tag, cls
        self.stack = []  # tags open inside the target
        self.inside = False
        self.done = False
        self.skip = 0
        self.buf = []

    def handle_starttag(self, tag, attrs):
        if self.done:
            return
        if not self.inside:
            classes = (dict(attrs).get("class") or "").split()
            if tag == self.tt and self.tc in classes:
                self.inside = True
            return
        if tag in VOID:
            if tag == "br":
                self.buf.append("\n\n")
            return
        self.stack.append(tag)
        classes = set((dict(attrs).get("class") or "").split())
        if tag in SKIP or classes & SKIP_CLASSES:
            self.stack[-1] = tag + "#skip"
            self.skip += 1
        if tag in BLOCK:
            self.buf.append("\n\n")

    def handle_endtag(self, tag):
        if self.done or not self.inside or tag in VOID:
            return
        if not self.stack:
            self.done = True
            return
        # pop to the matching tag (tolerate sloppy HTML)
        if tag in self.stack or tag + "#skip" in self.stack:
            while self.stack:
                t = self.stack.pop()
                if t.endswith("#skip"):
                    self.skip = max(0, self.skip - 1)
                    t = t[:-5]
                if t in BLOCK:
                    self.buf.append("\n\n")
                if t == tag:
                    break

    def handle_data(self, data):
        if self.inside and not self.done and not self.skip:
            self.buf.append(data)

    def paragraphs(self):
        t = "".join(self.buf).replace("\xa0", " ")
        out = []
        for p in re.split(r"\n\s*\n", t):
            p = re.sub(r"\s+", " ", p).strip()
            if p:
                out.append(p)
        return out


def extract_paragraphs(html, tag, cls):
    e = Extract(tag, cls)
    e.feed(html)
    return e.paragraphs()


WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*")


def count_words(text):
    """FROZEN 1 word rule (letters with internal apostrophes)."""
    return len(WORD.findall(text.replace("’", "'").replace("‘", "'")))
