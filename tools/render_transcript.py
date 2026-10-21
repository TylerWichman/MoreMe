"""Render key moments of an e2e transcript.md as small HTML pages for README screenshots.

Build-time only (stdlib). Each scene is one HTML file sized for a screenshot. Long
user answers are shortened and marked as shortened; nothing else is changed.

    python tools/render_transcript.py eval/e2e/runs/<run>/transcript.md OUT_DIR
"""
import html
import json
import re
import sys
from pathlib import Path

HEADER = re.compile(r"^\*\*(User \(([^)]*)\)|Assistant|Tool call|Tool result)[:*]")
FENCE = "```"
CAPTION = ("Rendered from the transcript of a headless Claude Code run with a simulated interviewee. "
           "Not a screen capture of the Claude Code interface.")


def parse(md):
    """Return a list of (kind, label, text) blocks in transcript order."""
    lines = md.splitlines()
    blocks, i = [], 0
    while i < len(lines):
        m = HEADER.match(lines[i])
        if not m:
            i += 1
            continue
        kind = m.group(1)
        label = ""
        if kind.startswith("User"):
            kind, label = "user", m.group(2)
        elif kind == "Assistant":
            kind = "assistant"
        elif kind == "Tool call":
            t = re.search(r"`([^`]+)`", lines[i])
            kind, label = "tool", t.group(1) if t else "tool"
        else:
            kind = "result"
        # body = first fenced block after the header
        j = i + 1
        while j < len(lines) and not lines[j].startswith(FENCE):
            if HEADER.match(lines[j]):
                break
            j += 1
        body = []
        if j < len(lines) and lines[j].startswith(FENCE):
            j += 1
            while j < len(lines) and not lines[j].startswith(FENCE):
                body.append(lines[j])
                j += 1
        blocks.append((kind, label, "\n".join(body)))
        i = j + 1
    return blocks


def tool_chip(label, text):
    detail = ""
    try:
        args = json.loads(text)
        path = args.get("file_path") or ""
        detail = path or args.get("command") or args.get("skill") or ""
    except (ValueError, AttributeError):
        path = ""
    detail = detail.replace("\\\\", "/").replace("\\", "/")
    if path:  # show file paths from the project folder; leave commands as written
        detail = re.sub(r"^.*?(moreme-output/|\.claude/)", r"\1", detail)
    return label + ("(" + detail + ")" if detail else "")


def shorten(text, max_words=45):
    words = text.split()
    if len(words) <= max_words:
        return text, False
    return " ".join(words[:max_words]) + " ...", True


def find(blocks, kind, needle, start=0):
    for k in range(start, len(blocks)):
        if blocks[k][0] == kind and needle in blocks[k][2]:
            return k
    raise LookupError(needle)


def scenes(blocks):
    """Pick five key moments by text markers. Returns [(name, title, [block indexes])]."""
    out = []
    first_a = find(blocks, "assistant", "Question 1")
    out.append(("1-start", "Start: what MoreMe does, and question 1", list(range(0, first_a + 1))))
    prompt = find(blocks, "assistant", "of 300 words so far")
    out.append(("2-writing", "Writing prompts adapt to the last answer", [prompt, prompt + 1]))
    report = find(blocks, "assistant", "Does this sound like you")
    out.append(("3-report", "Your style report and a check-in", [report, report + 1]))
    ab = find(blocks, "assistant", "Type A or B", report)
    out.append(("4-blind-ab", "Blind A/B: two drafts, you pick", [ab, ab + 1]))
    last = max(k for k, b in enumerate(blocks) if b[0] == "assistant")
    tools_before = [k for k in range(ab + 2, last) if blocks[k][0] == "tool"][-3:]
    out.append(("5-install", "Install and finish", tools_before + [last]))
    return out


CSS = """
:root { --bg:#1e1e1e; --fg:#e6e6e6; --muted:#9a9a9a; --user:#2b3a4a; --chip:#3a3a3a; --accent:#d97757; }
body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.5 Consolas, 'Cascadia Mono', Menlo, monospace; }
main { width:860px; padding:20px 24px 16px; }
h1 { font-size:14px; color:var(--accent); margin:0 0 14px; font-weight:600; }
.msg { margin:0 0 12px; white-space:pre-wrap; }
.user { background:var(--user); padding:8px 12px; border-radius:6px; }
.user::before { content:'> '; color:var(--muted); }
.assistant::before { content:'* '; color:var(--accent); }
.tool { color:var(--muted); font-size:13px; margin:0 0 6px; }
.tool span { background:var(--chip); padding:1px 6px; border-radius:4px; }
.note { color:var(--muted); font-size:12px; }
footer { color:var(--muted); font-size:11px; margin-top:12px; border-top:1px solid #333; padding-top:8px; }
"""


def render_scene(title, blocks, idxs):
    parts = ["<!doctype html><html><head><meta charset='utf-8'><style>", CSS, "</style></head><body><main>",
             "<h1>MoreMe in Claude Code: " + html.escape(title) + "</h1>"]
    for k in idxs:
        kind, label, text = blocks[k]
        if kind == "user":
            t, cut = shorten(text)
            parts.append("<div class='msg user'>" + html.escape(t) + "</div>")
            if cut:
                parts.append("<div class='note'>(answer shortened for the screenshot)</div>")
        elif kind == "assistant":
            parts.append("<div class='msg assistant'>" + html.escape(text) + "</div>")
        elif kind == "tool":
            parts.append("<div class='tool'><span>" + html.escape(tool_chip(label, text)) + "</span></div>")
    parts.append("<footer>" + html.escape(CAPTION) + "</footer></main></body></html>")
    return "".join(parts)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    src, out = Path(argv[0]), Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    blocks = parse(src.read_text(encoding="utf-8"))
    for name, title, idxs in scenes(blocks):
        (out / (name + ".html")).write_text(render_scene(title, blocks, idxs), encoding="utf-8")
        print(name, idxs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
