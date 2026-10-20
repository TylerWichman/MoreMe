"""Pre-registered draft extraction and invalid-unit detection (AD-006).

Identical for every arm:

1. Take the final assistant text message of the main thread (stream-json).
2. Drop every code-fence line (a line whose first non-space characters are
   three backticks or three tildes). The text between fences is kept.
3. If the first non-empty line matches PREAMBLE_RE (a single-line lead-in such
   as "Here's the email:"), drop it, and drop one directly following line that
   is only a Markdown rule (---, ***, ___).
4. Strip leading and trailing blank space.

A unit is invalid when the extracted draft is empty, or the final message
matches the fixed refusal or missing-skill regex list in
eval/lib/childrun.py (INVALID_PATTERNS, consumed here unchanged).
Both regexes are copied verbatim into eval/PREREGISTRATION.md.
"""
import re

from harness import common

FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
RULE_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
PREAMBLE_RE = re.compile(
    r"^\s*(?:(?:sure|okay|ok|certainly|absolutely|of course)[,!.]?\s+)?"
    r"(?:here(?:'s|’s| is| are)\b|below is\b|i(?:'ve|’ve| have) (?:written|drafted)\b)"
    r"[^\n]{0,120}[:.]\s*$",
    re.IGNORECASE,
)
PREAMBLE_PATTERN = PREAMBLE_RE.pattern
FENCE_PATTERN = FENCE_RE.pattern


def extract_draft(final_message):
    """Apply the pre-registered rule to the final assistant message."""
    if not final_message:
        return ""
    lines = [ln for ln in final_message.replace("\r\n", "\n").replace("\r", "\n").split("\n")
             if not FENCE_RE.match(ln)]
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and PREAMBLE_RE.match(lines[i]):
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i < len(lines) and RULE_RE.match(lines[i]):
            i += 1
    return "\n".join(lines[i:]).strip()


def invalid_reasons(final_message, draft):
    """List of reasons (empty = valid). Fixed detector, same for every arm."""
    reasons = []
    if draft is None or not draft.strip():
        reasons.append("empty")
        return reasons
    r = common.childrun.invalid_reason(final_message)
    if r:
        reasons.append(r)
    return reasons


def check_extracted(draft):
    """Post-conditions every committed draft must meet (used by tests)."""
    problems = []
    if not draft.strip():
        problems.append("empty")
    for ln in draft.split("\n"):
        if FENCE_RE.match(ln):
            problems.append("code_fence_left")
            break
    first = next((ln for ln in draft.split("\n") if ln.strip()), "")
    if first and PREAMBLE_RE.match(first):
        problems.append("preamble_left")
    return problems
