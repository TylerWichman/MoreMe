#!/usr/bin/env python3
"""MoreMe analyze.py: measure writing style with the Python standard library only.

This script reads text files you wrote and counts simple, checkable habits:
sentence length, punctuation, contractions, pronouns, and similar. It opens no
network connections and writes only where you tell it to.

Run "python analyze.py --help" for the list of commands.

Requires Python 3.8 or newer. No packages to install.
"""

import argparse
import codecs
import collections
import datetime
import decimal
import io
import json
import math
import os
import re
import secrets
import shutil
import statistics
import sys
import tempfile
import traceback
import unicodedata
import zipfile
from pathlib import Path

ANALYZE_VERSION = "1.0.0"
SCHEMA_VERSION = "1"
MOREME_VERSION = "v1.0.0"

# Files larger than this are read line by line instead of all at once.
STREAM_THRESHOLD = 5 * 1024 * 1024
BINARY_SNIFF_BYTES = 8192
# A paragraph buffer this large is split at sentence ends early to bound memory.
PARTIAL_PARAGRAPH_CHARS = 65536
LOW_WORDS = 1000
VERY_LOW_WORDS = 300
FEW_SENTENCES = 5
SKILL_BODY_MAX_CHARS = 20000
DESCRIPTION_MAX_CHARS = 1024

# ---------------------------------------------------------------------------
# Feature keys (FROZEN 1, schema_version "1")
# ---------------------------------------------------------------------------

EXPOSED_KEYS = (
    "sentence_length_mean",
    "sentence_length_sd",
    "sentence_length_p10",
    "sentence_length_p50",
    "sentence_length_p90",
    "word_length_mean",
    "paragraph_length_mean",
    "comma_per_1k",
    "semicolon_per_1k",
    "colon_per_1k",
    "exclamation_per_1k",
    "question_per_1k",
    "ellipsis_per_1k",
    "parenthesis_per_1k",
    "em_dash_per_1k",
    "en_dash_per_1k",
    "spaced_hyphen_per_1k",
    "contraction_per_1k",
    "first_person_singular_per_1k",
    "first_person_plural_per_1k",
    "second_person_per_1k",
    "question_sentence_share",
    "exclamation_sentence_share",
    "type_token_ratio_mattr100",
    "all_caps_word_per_1k",
    "lowercase_sentence_start_share",
    "emoji_per_1k",
    "sentence_opener_variety",
)

# The 13 keys the my-voice template may show (FROZEN 3, Measured profile).
DISPLAY_KEYS = (
    "sentence_length_p50",
    "sentence_length_p10",
    "sentence_length_p90",
    "paragraph_length_mean",
    "comma_per_1k",
    "exclamation_per_1k",
    "question_sentence_share",
    "contraction_per_1k",
    "first_person_singular_per_1k",
    "second_person_per_1k",
    "em_dash_per_1k",
    "emoji_per_1k",
    "lowercase_sentence_start_share",
)

WHOLE_NUMBER_KEYS = frozenset(
    ["sentence_length_p10", "sentence_length_p50", "sentence_length_p90", "paragraph_length_mean"]
)
PERCENT_KEYS = frozenset(
    [
        "question_sentence_share",
        "exclamation_sentence_share",
        "lowercase_sentence_start_share",
        "type_token_ratio_mattr100",
        "sentence_opener_variety",
    ]
)
NOT_MEASURED = "not measured (too little text)"

FIRST_PERSON_SINGULAR = frozenset(["i", "me", "my", "mine", "myself"])
FIRST_PERSON_PLURAL = frozenset(["we", "us", "our", "ours", "ourselves"])
SECOND_PERSON = frozenset(["you", "your", "yours", "yourself", "yourselves"])
CONTRACTION_ENDINGS = ("n't", "'re", "'ve", "'ll", "'d", "'m", "'s")
ABBREVIATIONS = frozenset(
    ["mr", "mrs", "ms", "dr", "st", "jr", "sr", "prof", "vs", "etc", "e.g", "i.e"]
)

# Scoring-only function-word list: 150 common English function words
# (articles, determiners, prepositions, conjunctions, auxiliaries, third-person
# and relative pronouns, common adverbs). It leaves out every pronoun counted
# by an exposed feature (I, me, my, mine, myself, we, us, our, ours, ourselves,
# you, your, yours, yourself, yourselves) and all contracted forms.
FUNCTION_WORDS = (
    # articles and determiners (28)
    "the", "a", "an", "this", "that", "these", "those", "some", "any", "each",
    "every", "no", "all", "both", "either", "neither", "such", "another", "other", "much",
    "many", "more", "most", "few", "less", "several", "own", "same",
    # prepositions (42)
    "of", "in", "to", "for", "with", "on", "at", "by", "from", "about",
    "as", "into", "like", "through", "after", "over", "between", "out", "against", "during",
    "without", "before", "under", "around", "among", "upon", "within", "along", "across", "behind",
    "beyond", "toward", "towards", "above", "below", "until", "since", "off", "up", "down",
    "near", "onto",
    # conjunctions (18)
    "and", "but", "or", "nor", "so", "yet", "if", "because", "although", "though",
    "while", "whether", "unless", "than", "when", "where", "whereas", "once",
    # auxiliaries and modals (25)
    "be", "is", "am", "are", "was", "were", "been", "being", "have", "has",
    "had", "having", "do", "does", "did", "will", "would", "shall", "should", "can",
    "could", "may", "might", "must", "ought",
    # third-person and relative pronouns (21)
    "he", "him", "his", "she", "her", "hers", "it", "its", "they", "them",
    "their", "theirs", "himself", "herself", "itself", "themselves", "who", "whom", "whose", "which",
    "what",
    # common adverbs (16)
    "not", "only", "also", "very", "just", "then", "there", "here", "now", "even",
    "still", "too", "again", "ever", "never", "always",
)
FUNCTION_WORD_SET = frozenset(FUNCTION_WORDS)
CHAR3_TOP = 300

# Words and phrases that sound like generated marketing copy (TC-001). The
# my-voice "Words I avoid" list starts from this list. tools/check_prose.py
# should use the same list.
BANNED_PHRASES = (
    "seamless", "seamlessly", "leverage", "leveraging", "unlock", "empower",
    "game-changer", "game changer", "delve", "robust", "elevate", "revolutionize",
    "revolutionary", "cutting-edge", "supercharge", "effortless", "effortlessly",
    "unleash", "transformative", "next-level", "world-class", "best-in-class",
    "magic", "magical", "in today's", "it's worth noting", "dive into", "deep dive",
    "say goodbye to", "whether you're", "look no further",
    "take your writing to the next level",
)

FORBIDDEN_TOKENS = (
    "scoring_only", "function_word_freq", "char3_freq", "delta_fw", "char3_cosine",
    "reference_stats",
)

VERBATIM_START = "<!-- verbatim-samples:start -->"
VERBATIM_END = "<!-- verbatim-samples:end -->"
AVOID_START = "<!-- avoid-words:start -->"
AVOID_END = "<!-- avoid-words:end -->"

# ---------------------------------------------------------------------------
# Regular expressions
# ---------------------------------------------------------------------------

WORD_RE = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*")
TERM_RE = re.compile("[.!?…]+[\"'”’)\\]]*")
TERM_CLOSERS = "\"'”’)]"
TOKEN_OPENERS = "\"'(“‘["
ELLIPSIS_RE = re.compile(r"\.{2,}")
SPACED_HYPHEN_RE = re.compile(r"(?<=[ \t])-(?=[ \t])")
DOUBLE_HYPHEN_RE = re.compile(r"(?<!-)--(?!-)")
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF"
    "\U0001F900-\U0001F9FF\U0001FA70-\U0001FAFF☀-⛿✀-➿]"
)
SKIN_TONE_RE = re.compile("[\U0001F3FB-\U0001F3FF]")
REGIONAL_RE = re.compile("[\U0001F1E6-\U0001F1FF]")
WHITESPACE_RE = re.compile(r"\s+")
CONTROL_BYTES = frozenset(list(range(1, 9)) + [0x0B] + list(range(0x0E, 0x20)) + [0x7F])
SKILL_NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")
PLACEHOLDER_RE = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")


class InputError(Exception):
    """Bad input from the user. Printed as one line, exit code 2."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def r4(value):
    if value is None:
        return None
    value = float(value)
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, 4)


def warning(code, message):
    return {"code": code, "message": message}


def now_iso():
    return datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()


def map_apostrophes(text):
    return text.replace("’", "'").replace("‘", "'")


def find_words(text):
    return WORD_RE.findall(map_apostrophes(text))


def plural(n, one, many):
    return one if n == 1 else many


def atomic_write_bytes(path, data):
    path = Path(path)
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name + ".tmp-", dir=str(parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_write_text(path, text):
    atomic_write_bytes(path, text.encode("utf-8"))


def json_text(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def emit_json(obj):
    sys.stdout.write(json_text(obj))
    sys.stdout.flush()


def write_json_file(path, obj):
    atomic_write_text(path, json_text(obj))


# ---------------------------------------------------------------------------
# Reading files (FROZEN 1 decoding order)
# ---------------------------------------------------------------------------


class Source(object):
    """One decoded input file. Small files are held in memory; large ones are streamed."""

    def __init__(self, path):
        self.path = Path(path)
        self.name = self.path.name
        self.encoding = None
        self.errors = "strict"
        self.skip = 0
        self.streamed = False
        self.text = None
        self._open()

    def _open(self):
        if not self.path.exists():
            raise InputError("File not found: " + self.name)
        if not self.path.is_file():
            raise InputError("Not a file: " + self.name)
        try:
            size = self.path.stat().st_size
            with open(str(self.path), "rb") as handle:
                head = handle.read(BINARY_SNIFF_BYTES)
        except OSError:
            raise InputError("Cannot read file: " + self.name)
        self.streamed = size > STREAM_THRESHOLD
        data = None
        if not self.streamed:
            with open(str(self.path), "rb") as handle:
                data = handle.read()

        if head[:4] in (b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff"):
            raise InputError("UTF-32 text is not supported. Save it as UTF-8: " + self.name)
        bom = None
        if head[:3] == codecs.BOM_UTF8:
            bom = ("utf-8-sig", 0)
        elif head[:2] == codecs.BOM_UTF16_LE:
            bom = ("utf-16-le", 2)
        elif head[:2] == codecs.BOM_UTF16_BE:
            bom = ("utf-16-be", 2)

        if bom is not None:
            self.encoding, self.skip = bom
            if not self._try(data, "strict"):
                self.errors = "replace"
                self._try(data, "replace")
            return

        if b"\x00" in head or (
            head and sum(1 for b in bytearray(head) if b in CONTROL_BYTES) > 0.3 * len(head)
        ):
            raise InputError("This looks like a binary file, not text: " + self.name)

        for encoding in ("utf-8", "cp1252", "latin-1"):
            self.encoding = encoding
            if self._try(data, "strict"):
                return
        raise InputError("Cannot decode file: " + self.name)  # latin-1 never fails

    def _try(self, data, errors):
        """Decode fully (small files) or check the whole stream (large files)."""
        try:
            if data is not None:
                self.text = data[self.skip:].decode(self.encoding, errors)
            else:
                decoder = codecs.getincrementaldecoder(self.encoding)(errors)
                with open(str(self.path), "rb") as handle:
                    handle.seek(self.skip)
                    while True:
                        chunk = handle.read(1 << 20)
                        if not chunk:
                            break
                        decoder.decode(chunk)
                decoder.decode(b"", True)
            return True
        except UnicodeDecodeError:
            self.text = None
            return False

    @property
    def fallback(self):
        return self.encoding not in ("utf-8", "utf-8-sig")

    @property
    def replaced(self):
        return self.errors == "replace"

    def lines(self):
        """Yield normalized lines (NFC, no line-ending characters, no U+FEFF)."""
        if self.text is not None:
            text = self.text.replace("\r\n", "\n").replace("\r", "\n")
            text = unicodedata.normalize("NFC", text).replace("﻿", "")
            for line in text.split("\n"):
                yield line
            return
        with open(str(self.path), "rb") as raw:
            raw.seek(self.skip)
            wrapper = io.TextIOWrapper(raw, encoding=self.encoding, errors=self.errors, newline=None)
            try:
                for line in wrapper:
                    if line.endswith("\n"):
                        line = line[:-1]
                    yield unicodedata.normalize("NFC", line).replace("﻿", "")
            finally:
                wrapper.detach()

    def full_text(self):
        return "\n".join(self.lines())


def read_text_file(path):
    """Decode a whole text file with the FROZEN 1 chain and normalize it."""
    return Source(path).full_text()


# ---------------------------------------------------------------------------
# Sentence splitting (FROZEN 1)
# ---------------------------------------------------------------------------


def split_sentences(text, final):
    """Split one paragraph's text into (segment, terminator) pairs.

    Returns (segments, remainder). With final=False, the text after the last
    sure split is returned as remainder so more text can be added to it.
    """
    segments = []
    start = 0
    length = len(text)
    for match in TERM_RE.finditer(text):
        end = match.end()
        if end == length:
            if not final:
                continue
        elif not text[end].isspace():
            continue
        run = match.group()
        core = run.rstrip(TERM_CLOSERS)
        if "?" in core or "!" in core:
            split = True
        elif "…" in core or core.count(".") >= 2:
            split = False
        else:
            j = match.start()
            while j > 0 and not text[j - 1].isspace():
                j -= 1
            token = text[j:match.start()].lstrip(TOKEN_OPENERS)
            if token.casefold() in ABBREVIATIONS:
                split = False
            elif len(token) == 1 and token.isalpha() and token.isupper() and token != "I":
                split = False
            else:
                split = True
        if split:
            segments.append((text[start:end], core))
            start = end
    if final:
        if start < length:
            segments.append((text[start:], ""))
        return segments, ""
    return segments, text[start:]


# ---------------------------------------------------------------------------
# Counting
# ---------------------------------------------------------------------------


class Accumulator(object):
    """Counts features over a stream of normalized lines."""

    def __init__(self, scoring=False):
        self.scoring = scoring
        self.word_count = 0
        self.letters = 0
        self.sentence_lengths = []
        self.paragraph_count = 0
        self.openers = collections.Counter()
        self.lowercase_starts = 0
        self.question_sentences = 0
        self.exclamation_sentences = 0
        self.punct = collections.Counter()
        self.contractions = 0
        self.fps = 0
        self.fpp = 0
        self.second = 0
        self.all_caps = 0
        self.emoji = 0
        self.regional = 0
        self.window = collections.deque()
        self.window_counts = {}
        self.mattr_sum = 0
        self.mattr_n = 0
        self.function_words = collections.Counter()
        self.char3 = collections.Counter()
        self._char3_carry = ""
        self._char3_started = False
        self._para = []
        self._para_chars = 0
        self._para_limit = PARTIAL_PARAGRAPH_CHARS
        self._para_words = 0

    # -- input --------------------------------------------------------------

    def feed_line(self, line):
        self._count_line(line)
        if self.scoring:
            self._char3_line(line)
        if not line.strip(" \t"):
            self._end_paragraph()
            return
        self._para.append(line)
        self._para_chars += len(line) + 1
        if self._para_chars > self._para_limit:
            text = "\n".join(self._para)
            segments, rest = split_sentences(text, final=False)
            for segment, term in segments:
                self._sentence(segment, term)
            self._para = [rest] if rest else []
            self._para_chars = len(rest)
            if not segments:
                self._para_limit *= 2

    def end_doc(self):
        self._end_paragraph()
        self._char3_carry = ""
        self._char3_started = False

    def feed_text(self, text):
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = unicodedata.normalize("NFC", text).replace("﻿", "")
        for line in text.split("\n"):
            self.feed_line(line)
        self.end_doc()

    # -- internals ------------------------------------------------------------

    def _count_line(self, line):
        punct = self.punct
        for ch in ",;:!?(—–":
            n = line.count(ch)
            if n:
                punct[ch] += n
        punct["ellipsis"] += len(ELLIPSIS_RE.findall(line)) + line.count("…")
        punct["spaced_hyphen"] += len(SPACED_HYPHEN_RE.findall(line)) + len(DOUBLE_HYPHEN_RE.findall(line))
        emoji = len(EMOJI_RE.findall(line))
        if emoji:
            emoji -= len(SKIN_TONE_RE.findall(line))
        self.emoji += emoji
        self.regional += len(REGIONAL_RE.findall(line))

    def _char3_line(self, line):
        chunk = WHITESPACE_RE.sub(" ", line.lower()).strip()
        if not chunk:
            return
        if self._char3_started:
            chunk = " " + chunk
        self._char3_started = True
        combined = self._char3_carry + chunk
        counter = self.char3
        for i in range(len(combined) - 2):
            counter[combined[i:i + 3]] += 1
        self._char3_carry = combined[-2:]

    def _end_paragraph(self):
        if self._para:
            text = "\n".join(self._para)
            segments, _ = split_sentences(text, final=True)
            for segment, term in segments:
                self._sentence(segment, term)
        if self._para_words:
            self.paragraph_count += 1
        self._para = []
        self._para_chars = 0
        self._para_limit = PARTIAL_PARAGRAPH_CHARS
        self._para_words = 0

    def _sentence(self, segment, term):
        words = find_words(segment)
        if not words:
            return
        self.sentence_lengths.append(len(words))
        self._para_words += len(words)
        first = words[0]
        self.openers[first.casefold()] += 1
        if first[0].islower():
            self.lowercase_starts += 1
        if "?" in term:
            self.question_sentences += 1
        if "!" in term:
            self.exclamation_sentences += 1
        for word in words:
            self._word(word)

    def _word(self, word):
        self.word_count += 1
        apostrophes = word.count("'")
        self.letters += len(word) - apostrophes
        folded = word.casefold()
        if apostrophes:
            base = folded.split("'", 1)[0]
            if folded.endswith(CONTRACTION_ENDINGS):
                self.contractions += 1
        else:
            base = folded
            if self.scoring and folded in FUNCTION_WORD_SET:
                self.function_words[folded] += 1
        if base in FIRST_PERSON_SINGULAR:
            self.fps += 1
        elif base in FIRST_PERSON_PLURAL:
            self.fpp += 1
        elif base in SECOND_PERSON:
            self.second += 1
        if len(word) - apostrophes >= 2 and word.upper() == word and word.lower() != word:
            self.all_caps += 1
        # moving-window type-token ratio, 100 words, O(n)
        window = self.window
        counts = self.window_counts
        window.append(folded)
        counts[folded] = counts.get(folded, 0) + 1
        if len(window) > 100:
            old = window.popleft()
            left = counts[old] - 1
            if left:
                counts[old] = left
            else:
                del counts[old]
        if len(window) == 100:
            self.mattr_sum += len(counts)
            self.mattr_n += 1

    # -- results --------------------------------------------------------------

    def exposed(self):
        wc = self.word_count
        lengths = self.sentence_lengths
        sc = len(lengths)
        punct = self.punct

        def per1k(count):
            return None if wc == 0 else count / wc * 1000.0

        def share(count):
            return None if sc == 0 else count / sc

        if wc >= 100:
            ttr = self.mattr_sum / (self.mattr_n * 100.0)
        elif wc > 0:
            ttr = len(self.window_counts) / float(wc)
        else:
            ttr = None
        values = {
            "sentence_length_mean": (sum(lengths) / float(sc)) if sc else None,
            "sentence_length_sd": statistics.pstdev(lengths) if sc >= 2 else None,
            "sentence_length_p10": percentile(lengths, 10),
            "sentence_length_p50": percentile(lengths, 50),
            "sentence_length_p90": percentile(lengths, 90),
            "word_length_mean": (self.letters / float(wc)) if wc else None,
            "paragraph_length_mean": (wc / float(self.paragraph_count)) if self.paragraph_count else None,
            "comma_per_1k": per1k(punct[","]),
            "semicolon_per_1k": per1k(punct[";"]),
            "colon_per_1k": per1k(punct[":"]),
            "exclamation_per_1k": per1k(punct["!"]),
            "question_per_1k": per1k(punct["?"]),
            "ellipsis_per_1k": per1k(punct["ellipsis"]),
            "parenthesis_per_1k": per1k(punct["("]),
            "em_dash_per_1k": per1k(punct["—"]),
            "en_dash_per_1k": per1k(punct["–"]),
            "spaced_hyphen_per_1k": per1k(punct["spaced_hyphen"]),
            "contraction_per_1k": per1k(self.contractions),
            "first_person_singular_per_1k": per1k(self.fps),
            "first_person_plural_per_1k": per1k(self.fpp),
            "second_person_per_1k": per1k(self.second),
            "question_sentence_share": share(self.question_sentences),
            "exclamation_sentence_share": share(self.exclamation_sentences),
            "type_token_ratio_mattr100": ttr,
            "all_caps_word_per_1k": per1k(self.all_caps),
            "lowercase_sentence_start_share": share(self.lowercase_starts),
            "emoji_per_1k": per1k(self.emoji + self.regional // 2),
            "sentence_opener_variety": (len(self.openers) / float(sc)) if sc else None,
        }
        out = {}
        for key in EXPOSED_KEYS:
            value = values[key]
            if key in WHOLE_NUMBER_KEYS and key != "paragraph_length_mean":
                out[key] = value
            else:
                out[key] = r4(value)
        return out

    def scoring_only(self):
        wc = self.word_count
        fw = {}
        for word in FUNCTION_WORDS:
            fw[word] = None if wc == 0 else r4(self.function_words[word] / wc * 1000.0)
        total = sum(self.char3.values())
        top = sorted(self.char3.items(), key=lambda item: (-item[1], item[0]))[:CHAR3_TOP]
        char3 = {}
        for gram, count in top:
            char3[gram] = r4(count / float(total))
        return {"function_word_freq": fw, "char3_freq": char3}


def percentile(sorted_or_not, p):
    n = len(sorted_or_not)
    if n == 0:
        return None
    values = sorted(sorted_or_not)
    rank = max(1, (p * n + 99) // 100)
    return int(values[rank - 1])


# ---------------------------------------------------------------------------
# profile
# ---------------------------------------------------------------------------


def build_profile(acc, docs, view, extra_warnings):
    exposed = acc.exposed()
    warnings = []
    if acc.word_count < VERY_LOW_WORDS:
        warnings.append(warning(
            "very_low_word_count",
            "Only {0:,} {1}. Numbers from fewer than 300 words are very rough.".format(
                acc.word_count, plural(acc.word_count, "word", "words")),
        ))
    elif acc.word_count < LOW_WORDS:
        warnings.append(warning(
            "low_word_count",
            "Only {0:,} words. Numbers from fewer than 1,000 words are rough.".format(acc.word_count),
        ))
    warnings.extend(extra_warnings)
    sc = len(acc.sentence_lengths)
    if sc < FEW_SENTENCES:
        warnings.append(warning(
            "few_sentences",
            "Only {0} {1} found, so sentence numbers are rough.".format(sc, plural(sc, "sentence", "sentences")),
        ))
    missing = [key for key in EXPOSED_KEYS if exposed[key] is None]
    if missing:
        warnings.append(warning(
            "value_undefined",
            "Too little text to measure: " + ", ".join(missing) + ".",
        ))
    profile = collections.OrderedDict()
    profile["schema_version"] = SCHEMA_VERSION
    profile["analyze_version"] = ANALYZE_VERSION
    profile["view"] = view
    profile["word_count"] = acc.word_count
    profile["sentence_count"] = sc
    profile["paragraph_count"] = acc.paragraph_count
    profile["doc_count"] = len(docs)
    profile["docs"] = docs
    profile["exposed"] = exposed
    if view == "all":
        profile["scoring_only"] = acc.scoring_only()
    profile["warnings"] = warnings
    return profile


def profile_files(paths, view="exposed"):
    acc = Accumulator(scoring=(view == "all"))
    docs = []
    notes = []
    sources = [Source(path) for path in paths]  # check every file before counting
    for source in sources:
        before = acc.word_count
        for line in source.lines():
            acc.feed_line(line)
        acc.end_doc()
        docs.append(collections.OrderedDict(
            [("name", source.name), ("word_count", acc.word_count - before), ("encoding_used", source.encoding)]
        ))
        if source.fallback:
            notes.append(warning(
                "encoding_fallback",
                "{0} is not UTF-8, so it was read as {1}. Check that the numbers look right.".format(
                    source.name, source.encoding),
            ))
        if source.replaced:
            notes.append(warning(
                "replacement_chars",
                "Some characters in {0} could not be read and were replaced.".format(source.name),
            ))
        if source.streamed:
            notes.append(warning(
                "large_input_streamed",
                "{0} is larger than 5 MB, so it was read in pieces.".format(source.name),
            ))
    return build_profile(acc, docs, view, notes)


def profile_text(text, view="all", name="text"):
    acc = Accumulator(scoring=(view == "all"))
    acc.feed_text(text)
    docs = [collections.OrderedDict([("name", name), ("word_count", acc.word_count), ("encoding_used", "utf-8")])]
    return build_profile(acc, docs, view, [])


def cmd_profile(args):
    profile = profile_files(args.files, args.view)
    if args.out:
        write_json_file(args.out, profile)
        emit_json({"ok": True, "out": str(args.out), "warnings": profile["warnings"]})
    else:
        emit_json(profile)
    return 0


# ---------------------------------------------------------------------------
# compare, attribute, reference-stats
# ---------------------------------------------------------------------------


def load_json_file(path, what):
    path = Path(path)
    if not path.is_file():
        raise InputError("{0} not found: {1}".format(what, path.name))
    try:
        with open(str(path), "r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        raise InputError("{0} is not valid JSON: {1}".format(what, path.name))


def load_profile(path):
    data = load_json_file(path, "Profile")
    if (
        not isinstance(data, dict)
        or data.get("schema_version") != SCHEMA_VERSION
        or not isinstance(data.get("exposed"), dict)
        or data.get("view") not in ("exposed", "all")
    ):
        raise InputError("Not a MoreMe profile (schema_version 1): " + Path(path).name)
    if data["view"] == "all" and not isinstance(data.get("scoring_only"), dict):
        raise InputError("Profile says view all but has no scoring data: " + Path(path).name)
    return data


def load_reference(path):
    data = load_json_file(path, "Reference stats file")
    if (
        not isinstance(data, dict)
        or data.get("schema_version") != SCHEMA_VERSION
        or not isinstance(data.get("function_words"), dict)
        or not isinstance(data.get("exposed"), dict)
        or not isinstance(data.get("excluded"), list)
    ):
        raise InputError("Not a MoreMe reference stats file (schema_version 1): " + Path(path).name)
    return data


def _z_diffs(keys, values_a, values_b, stats, excluded):
    """Return ({key: signed z difference or None}, [excluded keys])."""
    diffs = collections.OrderedDict()
    left_out = []
    for key in keys:
        a = values_a.get(key)
        b = values_b.get(key)
        stat = stats.get(key) or {}
        mean = stat.get("mean")
        sd = stat.get("sd")
        if key in excluded or a is None or b is None or mean is None or not sd:
            diffs[key] = None
            left_out.append(key)
            continue
        diffs[key] = (a - mean) / sd - (b - mean) / sd
    return diffs, left_out


def _mean_abs(values):
    used = [abs(v) for v in values if v is not None]
    return (sum(used) / len(used)) if used else None


def char3_distance(a, b):
    keys = set(a) | set(b)
    dot = sum((a.get(k) or 0.0) * (b.get(k) or 0.0) for k in keys)
    norm_a = math.sqrt(sum((v or 0.0) ** 2 for v in a.values()))
    norm_b = math.sqrt(sum((v or 0.0) ** 2 for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return None
    return 1.0 - dot / (norm_a * norm_b)


def delta_fw(profile_a, profile_b, ref):
    excluded = set(ref["excluded"])
    diffs, left_out = _z_diffs(
        FUNCTION_WORDS,
        profile_a["scoring_only"].get("function_word_freq") or {},
        profile_b["scoring_only"].get("function_word_freq") or {},
        ref["function_words"],
        excluded,
    )
    return _mean_abs(diffs.values()), left_out


def compare_profiles(profile_a, profile_b, ref):
    warnings = []
    left_out = []
    per_feature = collections.OrderedDict((key, None) for key in EXPOSED_KEYS)
    exposed_distance = None
    delta = None
    cosine = None
    if ref is None:
        warnings.append(warning(
            "reference_stats_missing",
            "No reference stats file given, so z-score distances were not computed.",
        ))
    else:
        diffs, out = _z_diffs(EXPOSED_KEYS, profile_a["exposed"], profile_b["exposed"], ref["exposed"],
                              set(ref["excluded"]))
        left_out.extend(out)
        for key, value in diffs.items():
            per_feature[key] = r4(value)
        exposed_distance = _mean_abs(diffs.values())
    if profile_a["view"] == "all" and profile_b["view"] == "all":
        if ref is not None:
            delta, out = delta_fw(profile_a, profile_b, ref)
            left_out.extend(out)
        cosine = char3_distance(profile_a["scoring_only"].get("char3_freq") or {},
                                profile_b["scoring_only"].get("char3_freq") or {})
        if cosine is None:
            warnings.append(warning("value_undefined", "One profile has no character data, so char3_cosine is null."))
    else:
        warnings.append(warning(
            "view_not_all",
            "Both profiles must be made with --view all for delta_fw and char3_cosine.",
        ))
    if left_out:
        warnings.append(warning(
            "feature_excluded",
            "Left out of the distance (no spread in the reference, or no value): " + ", ".join(left_out) + ".",
        ))
    result = collections.OrderedDict()
    result["schema_version"] = SCHEMA_VERSION
    result["exposed_distance"] = r4(exposed_distance)
    result["delta_fw"] = r4(delta)
    result["char3_cosine"] = r4(cosine)
    result["per_feature"] = per_feature
    result["warnings"] = warnings
    return result


def cmd_compare(args):
    a = load_profile(args.profile_a)
    b = load_profile(args.profile_b)
    ref = load_reference(args.reference_stats) if args.reference_stats else None
    result = compare_profiles(a, b, ref)
    if args.out:
        write_json_file(args.out, result)
        emit_json({"ok": True, "out": str(args.out), "warnings": result["warnings"]})
    else:
        emit_json(result)
    return 0


def cmd_attribute(args):
    draft = load_profile(args.draft_profile)
    if draft["view"] != "all":
        raise InputError("The draft profile must be made with --view all: " + Path(args.draft_profile).name)
    ref = load_reference(args.reference_stats)
    folder = Path(args.candidates)
    if not folder.is_dir():
        raise InputError("Candidates folder not found: " + folder.name)
    paths = sorted(folder.glob("*.json"), key=lambda p: p.stem)
    if len(paths) < 2:
        raise InputError("Need at least 2 candidate profiles in " + folder.name)
    deltas = collections.OrderedDict()
    left_out = set()
    for path in paths:
        candidate = load_profile(path)
        if candidate["view"] != "all":
            raise InputError("Candidate profile must be made with --view all: " + path.name)
        value, out = delta_fw(draft, candidate, ref)
        left_out.update(out)
        deltas[path.stem] = r4(value)
    scored = [(value, pid) for pid, value in deltas.items() if value is not None]
    warnings = []
    predicted = min(scored)[1] if scored else None
    if predicted is None:
        warnings.append(warning("value_undefined", "No distance could be computed, so no writer was picked."))
    if left_out:
        names = [w for w in FUNCTION_WORDS if w in left_out]
        warnings.append(warning(
            "feature_excluded",
            "Left out of the distance (no spread in the reference, or no value): " + ", ".join(names) + ".",
        ))
    k = len(paths)
    result = collections.OrderedDict()
    result["schema_version"] = SCHEMA_VERSION
    result["predicted"] = predicted
    result["k"] = k
    result["chance"] = r4(1.0 / k)
    result["deltas"] = deltas
    result["warnings"] = warnings
    if args.out:
        write_json_file(args.out, result)
        emit_json({"ok": True, "out": str(args.out), "warnings": warnings})
    else:
        emit_json(result)
    return 0


def _stat(values):
    used = [v for v in values if v is not None]
    if not used:
        return {"mean": None, "sd": None}
    mean = r4(sum(used) / float(len(used)))
    sd = r4(statistics.pstdev(used)) if len(used) >= 2 else None
    return {"mean": mean, "sd": sd}


def chunk_text(text, chunk_words):
    """Cut text into consecutive chunks of exactly chunk_words words (remainder dropped)."""
    spans = [m.span() for m in WORD_RE.finditer(map_apostrophes(text))]
    chunks = []
    for i in range(len(spans) // chunk_words):
        first = spans[i * chunk_words][0]
        last = spans[(i + 1) * chunk_words - 1][1]
        chunks.append(text[first:last])
    return chunks


def cmd_reference_stats(args):
    train = Path(args.train_dir)
    if not train.is_dir():
        raise InputError("Train folder not found: " + train.name)
    if args.chunk_words < 1:
        raise InputError("--chunk-words must be 1 or more")
    personas = sorted(p.name for p in train.iterdir() if p.is_dir() and not p.name.startswith("."))
    if len(personas) < 2:
        raise InputError("Need at least 2 persona folders in " + train.name)
    warnings = []
    chunks_per_persona = collections.OrderedDict()
    profiles = []
    for pid in personas:
        texts = []
        for path in sorted((train / pid).glob("*.txt"), key=lambda p: p.name):
            source = Source(path)
            texts.append(source.full_text())
            if source.fallback:
                warnings.append(warning(
                    "encoding_fallback",
                    "{0}/{1} is not UTF-8, so it was read as {2}.".format(pid, source.name, source.encoding),
                ))
            if source.replaced:
                warnings.append(warning(
                    "replacement_chars",
                    "Some characters in {0}/{1} could not be read and were replaced.".format(pid, source.name),
                ))
        chunks = chunk_text("\n\n".join(texts), args.chunk_words)
        if len(chunks) < 3:
            raise InputError(
                "Persona {0} has {1} chunks of {2} words; it needs at least 3.".format(
                    pid, len(chunks), args.chunk_words)
            )
        chunks_per_persona[pid] = len(chunks)
        for chunk in chunks:
            profiles.append(profile_text(chunk, view="all", name=pid))
    function_words = collections.OrderedDict()
    for word in FUNCTION_WORDS:
        function_words[word] = _stat([p["scoring_only"]["function_word_freq"][word] for p in profiles])
    exposed = collections.OrderedDict()
    for key in EXPOSED_KEYS:
        exposed[key] = _stat([p["exposed"][key] for p in profiles])
    excluded = [w for w, s in function_words.items() if not s["sd"]]
    excluded += [k for k, s in exposed.items() if not s["sd"]]
    result = collections.OrderedDict()
    result["schema_version"] = SCHEMA_VERSION
    result["analyze_version"] = ANALYZE_VERSION
    result["created"] = now_iso()
    result["source"] = collections.OrderedDict([
        ("split", "train"),
        ("chunk_words", args.chunk_words),
        ("personas", personas),
        ("chunks_per_persona", chunks_per_persona),
        ("total_chunks", len(profiles)),
    ])
    result["sd_type"] = "population"
    result["function_words"] = function_words
    result["exposed"] = exposed
    result["excluded"] = excluded
    write_json_file(args.out, result)
    emit_json({"ok": True, "out": str(args.out), "total_chunks": len(profiles), "warnings": warnings})
    return 0


# ---------------------------------------------------------------------------
# Display rules and report
# ---------------------------------------------------------------------------


def _half_up(value, places):
    quantum = decimal.Decimal(1).scaleb(-places)
    return decimal.Decimal(repr(float(value))).quantize(quantum, rounding=decimal.ROUND_HALF_UP)


def display_value(key, value):
    """Format a profile value for people (FROZEN 3 display rules)."""
    if value is None:
        return NOT_MEASURED
    if key in WHOLE_NUMBER_KEYS:
        return str(_half_up(value, 0))
    if key in PERCENT_KEYS:
        return str(_half_up(float(value) * 100.0, 0)) + "%"
    return str(_half_up(value, 1))


def _words(value):
    text = display_value("sentence_length_p50", value)
    if value is None:
        return text
    return text + (" word" if text == "1" else " words")


def _one(key, value, unit=""):
    text = display_value(key, value)
    if value is None or not unit:
        return text
    return text + unit


WARNING_TEXT = {
    "very_low_word_count": "There are fewer than 300 words, so these numbers are very rough. More samples will help.",
    "low_word_count": "There are fewer than 1,000 words, so these numbers are rough.",
    "encoding_fallback": "One or more files were not saved as UTF-8. They were read anyway; check that the numbers look right.",
    "replacement_chars": "Some characters could not be read and were replaced.",
    "few_sentences": "There are fewer than 5 sentences, so the sentence numbers are rough.",
    "value_undefined": "Some numbers could not be measured because there is too little text.",
    "large_input_streamed": "A very large file was read in pieces. The numbers are the same as reading it at once.",
}


def build_report(profile):
    e = profile["exposed"]
    wc = profile.get("word_count", 0)
    dc = profile.get("doc_count", 0)
    lines = [
        "Your writing, measured by MoreMe",
        "Based on {0:,} {1} in {2} {3}.".format(wc, plural(wc, "word", "words"), dc, plural(dc, "sample", "samples")),
        "",
        "Sentences: a typical sentence is {0}. Short ones are about {1} and long ones about {2}. "
        "The average is {3}, and length varies by about {4}.".format(
            _words(e.get("sentence_length_p50")),
            _words(e.get("sentence_length_p10")),
            _words(e.get("sentence_length_p90")),
            _one("sentence_length_mean", e.get("sentence_length_mean"), " words"),
            _one("sentence_length_sd", e.get("sentence_length_sd"), " words"),
        ),
        "Words and paragraphs: the average word is {0} long. A typical paragraph is {1}. "
        "Word variety is {2} (share of different words in each run of 100 words).".format(
            _one("word_length_mean", e.get("word_length_mean"), " letters"),
            _words(e.get("paragraph_length_mean")),
            _one("type_token_ratio_mattr100", e.get("type_token_ratio_mattr100")),
        ),
        "Punctuation per 1,000 words: commas {0}, semicolons {1}, colons {2}, exclamation marks {3}, "
        "question marks {4}, ellipses {5}, opening parentheses {6}.".format(
            *[display_value(k, e.get(k)) for k in (
                "comma_per_1k", "semicolon_per_1k", "colon_per_1k", "exclamation_per_1k",
                "question_per_1k", "ellipsis_per_1k", "parenthesis_per_1k")]
        ),
        "Dashes per 1,000 words: long dashes {0}, medium dashes {1}, spaced hyphens used as dashes {2}.".format(
            *[display_value(k, e.get(k)) for k in ("em_dash_per_1k", "en_dash_per_1k", "spaced_hyphen_per_1k")]
        ),
        "Contractions and pronouns per 1,000 words: contractions like I'm and don't {0}; "
        "I, me, my {1}; we, us, our {2}; you, your {3}.".format(
            *[display_value(k, e.get(k)) for k in (
                "contraction_per_1k", "first_person_singular_per_1k", "first_person_plural_per_1k",
                "second_person_per_1k")]
        ),
        "Kinds of sentences: questions {0}, sentences ending in an exclamation mark {1}, "
        "sentences that start lowercase {2}. Different first words: {3} of sentences.".format(
            *[display_value(k, e.get(k)) for k in (
                "question_sentence_share", "exclamation_sentence_share", "lowercase_sentence_start_share",
                "sentence_opener_variety")]
        ),
        "Capitals and emoji per 1,000 words: words in ALL CAPS {0}, emoji {1}.".format(
            display_value("all_caps_word_per_1k", e.get("all_caps_word_per_1k")),
            display_value("emoji_per_1k", e.get("emoji_per_1k")),
        ),
    ]
    seen = []
    for item in profile.get("warnings") or []:
        code = item.get("code") if isinstance(item, dict) else None
        if code in WARNING_TEXT and code not in seen:
            seen.append(code)
    lines.append("")
    if seen:
        lines.append("Notes:")
        for code in seen:
            lines.append("- " + WARNING_TEXT[code])
    else:
        lines.append("Notes: none.")
    return "\n".join(lines) + "\n"


def cmd_report(args):
    profile = load_profile(args.profile)
    text = build_report(profile)
    if args.out:
        atomic_write_text(args.out, text)
        emit_json({"ok": True, "out": str(args.out), "warnings": []})
    else:
        sys.stdout.write(text)
        sys.stdout.flush()
    return 0


# ---------------------------------------------------------------------------
# validate-skill
# ---------------------------------------------------------------------------


def error(code, message):
    return {"code": code, "message": message}


def parse_frontmatter(text):
    """Parse a small YAML subset. Returns (fields, body) or raises ValueError."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md must start with a line holding only ---")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise ValueError("The frontmatter has no closing --- line")
    fields = collections.OrderedDict()
    current = None
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_-]+)\s*:\s?(.*)$", raw)
        if match and not raw[0].isspace():
            current = match.group(1)
            value = match.group(2).strip()
            if value in (">", "|", ">-", "|-", ">+", "|+"):
                value = ""
            fields[current] = _unquote(value)
            continue
        if current is None:
            raise ValueError("Cannot read this frontmatter line: " + raw.strip()[:40])
        item = raw.strip()
        if item.startswith("- "):
            existing = fields.get(current)
            if not isinstance(existing, list):
                existing = [] if not existing else [existing]
            existing.append(_unquote(item[2:].strip()))
            fields[current] = existing
        else:
            existing = fields.get(current)
            if isinstance(existing, list):
                raise ValueError("Cannot read this frontmatter line: " + item[:40])
            fields[current] = (existing + " " + item).strip() if existing else item
    body = "\n".join(lines[end + 1:])
    return fields, body


def _unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def split_tool_list(value):
    if isinstance(value, list):
        return [v.strip() for v in value if v.strip()]
    items, depth, buf = [], 0, []
    for ch in value:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            items.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    items.append("".join(buf).strip())
    return [i for i in items if i]


def bash_pattern_ok(entry):
    match = re.match(r"^Bash\((.*)\)$", entry.strip())
    if not match:
        return False
    pattern = match.group(1).strip()
    if "*" not in pattern:
        tokens = pattern.split()
        if len(tokens) >= 2 and tokens[-1] == "--version":
            return True
    if pattern.endswith(":*"):
        pattern = pattern[:-2]
    elif pattern.endswith(" *"):
        pattern = pattern[:-2]
    if "*" in pattern:
        return False
    tokens = pattern.split()
    return len(tokens) >= 2 and re.search(r"(^|[/\\])analyze\.py$", tokens[-1]) is not None


def _blank_spans(text, start_marker, end_marker):
    """Replace marker spans with newlines so line numbers stay the same."""
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.S)
    return pattern.sub(lambda m: "\n" * m.group().count("\n"), text)


def banned_regex(phrase):
    parts = [re.escape(p) for p in phrase.split()]
    return re.compile(r"(?<![\w-])" + r"\s+".join(parts) + r"(?![\w-])", re.IGNORECASE)


BANNED_RES = [(phrase, banned_regex(phrase)) for phrase in BANNED_PHRASES]


def find_banned(text):
    """Return [(phrase, line_number)] for banned words in text."""
    mapped = map_apostrophes(text)
    hits = []
    for phrase, regex in BANNED_RES:
        match = regex.search(mapped)
        if match:
            hits.append((phrase, mapped.count("\n", 0, match.start()) + 1))
    return hits


def find_em_dashes(text):
    return [i + 1 for i, line in enumerate(text.split("\n")) if "—" in line]


NUMBER_PAIR_RE = re.compile(r"^[\s|>*-]*([A-Za-z]+)[\s|:=,*-]+(\d+(?:\.\d+)?)[\s|%]*$")


def function_word_table(text):
    run = 0
    for line in text.split("\n"):
        match = NUMBER_PAIR_RE.match(line)
        if match and match.group(1).lower() in FUNCTION_WORD_SET:
            run += 1
            if run >= 10:
                return True
        else:
            run = 0
    return False


def validate_skill_text(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    errors = []
    try:
        fields, body = parse_frontmatter(text)
    except ValueError as exc:
        errors.append(error("bad_frontmatter", str(exc) + "."))
        fields, body = None, text
    if fields is not None:
        name = fields.get("name")
        if not isinstance(name, str) or not SKILL_NAME_RE.match(name) or "claude" in name or "anthropic" in name:
            errors.append(error(
                "name_invalid",
                "The name must be 1 to 64 lowercase letters, digits, or hyphens, without the words claude or anthropic.",
            ))
        description = fields.get("description")
        if isinstance(description, list):
            description = " ".join(description)
        if not description or not str(description).strip():
            errors.append(error("description_missing", "The frontmatter needs a description."))
        elif len(description) > DESCRIPTION_MAX_CHARS:
            errors.append(error(
                "description_too_long",
                "The description has {0} characters; the limit is 1,024.".format(len(description)),
            ))
        tools = fields.get("allowed-tools")
        if tools:
            for entry in split_tool_list(tools):
                if entry == "Bash" or (entry.startswith("Bash") and not bash_pattern_ok(entry)):
                    errors.append(error(
                        "allowed_tools_too_broad",
                        "This allowed-tools entry is too broad: {0}. Use an exact --version probe or a "
                        "pattern scoped to analyze.py.".format(entry),
                    ))
    if len(body) > SKILL_BODY_MAX_CHARS:
        errors.append(error(
            "body_too_long",
            "The body has {0:,} characters; the limit is 20,000 (about 5,000 tokens).".format(len(body)),
        ))
    no_samples = _blank_spans(text, VERBATIM_START, VERBATIM_END)
    for line in find_em_dashes(no_samples):
        errors.append(error("em_dash", "Line {0} has a long dash. Use a comma, period, colon, or parentheses.".format(line)))
    no_avoid = _blank_spans(no_samples, AVOID_START, AVOID_END)
    for phrase, line in find_banned(no_avoid):
        errors.append(error("banned_word", "Line {0} uses \"{1}\". Say it in plain words instead.".format(line, phrase)))
    lowered = text.lower()
    for token in FORBIDDEN_TOKENS:
        if token in lowered:
            errors.append(error("forbidden_token", "The skill must not contain \"{0}\".".format(token)))
    if function_word_table(text):
        errors.append(error("forbidden_token", "The skill must not list common small words with numbers."))
    return errors


def validate_skill_dir(folder):
    folder = Path(folder)
    if not folder.is_dir():
        raise InputError("Skill folder not found: " + folder.name)
    skill_md = folder / "SKILL.md"
    if not skill_md.is_file():
        return [error("missing_skill_md", "There is no SKILL.md in " + folder.name + ".")]
    try:
        text = read_text_file(skill_md)
    except InputError as exc:
        return [error("bad_frontmatter", str(exc))]
    return validate_skill_text(text)


def cmd_validate_skill(args):
    errors = validate_skill_dir(args.dir)
    emit_json(collections.OrderedDict([("ok", not errors), ("errors", errors), ("warnings", [])]))
    return 0


# ---------------------------------------------------------------------------
# build-skill
# ---------------------------------------------------------------------------

NOTE_SECTIONS = (
    ("how_i_sound", "how i sound", "How I sound"),
    ("do", "do", "Do"),
    ("dont", "don't", "Don't"),
    ("avoid_words", "avoid words", "Avoid words"),
    ("examples", "examples", "Examples"),
    ("channels", "adjust by channel", "Adjust by channel"),
)
CHANNELS = (("email", "Email"), ("post", "Post"), ("cover letter", "Cover letter"))
EXCERPT_HEADER_RE = re.compile(r"^\[\s*([^\[\]]+?)\s*\]\s*$")
CHANNEL_RE = re.compile(r"^(?:[-*]\s*)?(email|post|cover letter)\s*:\s*(.*)$", re.IGNORECASE)
BULLET_RE = re.compile(r"^[-*]\s+(.*)$")


def parse_notes(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    known = dict((heading, key) for key, heading, _ in NOTE_SECTIONS)
    sections = {}
    current = None
    for line in text.split("\n"):
        match = re.match(r"^##\s+(.+?)\s*#*\s*$", line)
        if match and not line.startswith("###"):
            heading = map_apostrophes(match.group(1)).strip().casefold()
            current = known.get(heading)
            if current is not None and current in sections:
                current = None  # a repeated heading is ignored
            elif current is not None:
                sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)
    return sections


def count_sentences(text):
    segments, _ = split_sentences(" ".join(text.split()), final=True)
    return sum(1 for segment, _ in segments if find_words(segment))


def _bullets(lines):
    items = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        match = BULLET_RE.match(stripped)
        if match:
            items.append(match.group(1).strip())
        elif items:
            items[-1] = items[-1] + " " + stripped
        else:
            items.append(stripped)
    return [i for i in items if i]


def _free_text_errors(section_label, text):
    errors = []
    for phrase, _ in find_banned(text):
        errors.append(error(
            "banned_word",
            "In voice-notes.md, section {0} uses \"{1}\". Say it in plain words, or move a pet-peeve word "
            "to Avoid words.".format(section_label, phrase),
        ))
    if "—" in text:
        errors.append(error(
            "em_dash",
            "In voice-notes.md, section {0} has a long dash. Use a comma, period, colon, or parentheses.".format(
                section_label),
        ))
    return errors


def check_notes(sections, samples_dir):
    """Return (parsed notes dict, errors)."""
    errors = []
    for key, _, label in NOTE_SECTIONS:
        if key not in sections:
            errors.append(error("notes_section_missing", "voice-notes.md needs a \"## {0}\" heading.".format(label)))
    notes = {}

    def out_of_range(message):
        errors.append(error("notes_count_out_of_range", message))

    if "how_i_sound" in sections:
        text = " ".join(" ".join(sections["how_i_sound"]).split())
        n = count_sentences(text)
        if not 3 <= n <= 5:
            out_of_range("How I sound has {0} {1}; write 3 to 5.".format(n, plural(n, "sentence", "sentences")))
        errors.extend(_free_text_errors("How I sound", text))
        notes["how_i_sound"] = text

    for key, label, low, high in (("do", "Do", 5, 8), ("dont", "Don't", 3, 6)):
        if key in sections:
            items = _bullets(sections[key])
            if not low <= len(items) <= high:
                out_of_range("{0} has {1} {2}; write {3} to {4} lines starting with \"- \".".format(
                    label, len(items), plural(len(items), "line", "lines"), low, high))
            errors.extend(_free_text_errors(label, "\n".join(items)))
            notes[key] = items

    if "avoid_words" in sections:
        words = []
        for line in sections["avoid_words"]:
            item = line.strip()
            match = BULLET_RE.match(item)
            if match:
                item = match.group(1).strip()
            if item:
                words.append(item)
        if len(words) > 20:
            out_of_range("Avoid words has {0} lines; write at most 20.".format(len(words)))
        if any("—" in w for w in words):
            errors.append(error("em_dash", "In voice-notes.md, section Avoid words has a long dash."))
        notes["avoid_words"] = words

    if "examples" in sections:
        excerpts = []
        current = None
        for line in sections["examples"]:
            match = EXCERPT_HEADER_RE.match(line.strip())
            if match:
                current = [match.group(1), []]
                excerpts.append(current)
            elif current is not None:
                current[1].append(line)
        if not 3 <= len(excerpts) <= 5:
            out_of_range("Examples has {0} {1}; give 3 to 5, each under a [sample-NN.txt] line.".format(
                len(excerpts), plural(len(excerpts), "excerpt", "excerpts")))
        parsed = []
        cache = {}
        for index, (name, lines) in enumerate(excerpts, 1):
            excerpt = "\n".join(lines).strip()
            parsed.append((name, excerpt))
            n = len(find_words(excerpt))
            if not 40 <= n <= 120:
                errors.append(error(
                    "excerpt_length",
                    "Excerpt {0} (from {1}) has {2} words; use 40 to 120.".format(index, name, n),
                ))
            if "/" in name or "\\" in name or name in (".", ".."):
                errors.append(error(
                    "excerpt_not_verbatim",
                    "Excerpt {0} names \"{1}\"; use just the file name from the samples folder.".format(index, name),
                ))
                continue
            if name not in cache:
                path = Path(samples_dir) / name
                try:
                    cache[name] = read_text_file(path).strip() if path.is_file() else None
                except InputError:
                    cache[name] = None
            source = cache[name]
            if source is None:
                errors.append(error(
                    "excerpt_not_verbatim",
                    "Excerpt {0} names {1}, which is not in the samples folder.".format(index, name),
                ))
            elif unicodedata.normalize("NFC", excerpt) not in source:
                errors.append(error(
                    "excerpt_not_verbatim",
                    "Excerpt {0} is not copied exactly from {1}. Copy it again, word for word.".format(index, name),
                ))
        notes["examples"] = parsed

    if "channels" in sections:
        found = {}
        for line in sections["channels"]:
            match = CHANNEL_RE.match(line.strip())
            if match:
                found.setdefault(match.group(1).casefold(), match.group(2).strip())
        channel_lines = []
        for key, label in CHANNELS:
            if key not in found:
                out_of_range("Adjust by channel needs a line starting with \"{0}:\".".format(label))
                continue
            n = count_sentences(found[key])
            if not 1 <= n <= 3:
                out_of_range("Adjust by channel, {0}: has {1} {2}; write 1 to 3.".format(
                    label, n, plural(n, "sentence", "sentences")))
            channel_lines.append((label, found[key]))
        errors.extend(_free_text_errors("Adjust by channel", "\n".join(t for _, t in channel_lines)))
        notes["channels"] = channel_lines
    return notes, errors


def default_avoid_list(samples_text):
    folded = map_apostrophes(samples_text).casefold()
    return [phrase for phrase, regex in BANNED_RES if not regex.search(folded)]


def _sample_texts(samples_dir):
    texts = []
    for path in sorted(Path(samples_dir).iterdir(), key=lambda p: p.name):
        if path.is_file() and not path.name.startswith("."):
            try:
                texts.append(read_text_file(path))
            except InputError:
                continue
    return "\n\n".join(texts)


def placeholder_values(profile, notes, samples_text, date_text):
    exposed = profile.get("exposed") or {}
    values = {}
    for key in DISPLAY_KEYS:
        values["exposed." + key] = display_value(key, exposed.get(key))
    values["meta.word_count"] = "{0:,}".format(int(profile.get("word_count") or 0))
    values["meta.doc_count"] = str(int(profile.get("doc_count") or 0))
    values["meta.date"] = date_text
    values["meta.moreme_version"] = MOREME_VERSION
    values["notes.how_i_sound"] = notes.get("how_i_sound", "")
    values["notes.do"] = "\n".join("- " + item for item in notes.get("do", []))
    values["notes.dont"] = "\n".join("- " + item for item in notes.get("dont", []))
    avoid = []
    seen = set()
    for word in default_avoid_list(samples_text) + list(notes.get("avoid_words", [])):
        key = map_apostrophes(word).casefold()
        if key not in seen:
            seen.add(key)
            avoid.append(word)
    values["notes.avoid_words"] = "\n".join("- " + word for word in avoid)
    values["notes.examples"] = "\n\n".join(
        "From {0}:\n{1}".format(name, excerpt) for name, excerpt in notes.get("examples", [])
    )
    values["notes.channels"] = "\n".join("- {0}: {1}".format(label, text) for label, text in notes.get("channels", []))
    dash = exposed.get("em_dash_per_1k")
    if not dash:
        values["rules.dash_line"] = "Do not use long dashes. Use commas, periods, colons, or parentheses instead."
    else:
        values["rules.dash_line"] = "Long dashes are fine. My samples use about {0} per 1,000 words.".format(
            display_value("em_dash_per_1k", dash))
    return values


def render_template(template, values):
    unknown = []

    def replace(match):
        key = match.group(1)
        if key in values:
            return values[key]
        unknown.append(key)
        return match.group(0)

    rendered = PLACEHOLDER_RE.sub(replace, template)
    errors = [error("unknown_placeholder", "The template uses an unknown placeholder: {{" + key + "}}.")
              for key in unknown]
    return rendered, errors


def default_template_path():
    return Path(__file__).resolve().parent / "templates" / "my-voice" / "SKILL.md.tmpl"


def replace_folder(new_dir, target):
    """Move new_dir to target, replacing target if it exists."""
    new_dir, target = Path(new_dir), Path(target)
    if target.exists():
        old = target.parent / ".{0}.old-{1}".format(target.name, secrets.token_hex(4))
        os.replace(str(target), str(old))
        os.replace(str(new_dir), str(target))
        shutil.rmtree(str(old), ignore_errors=True)
    else:
        os.replace(str(new_dir), str(target))


def cmd_build_skill(args):
    profile_path, notes_path, samples_dir = Path(args.profile), Path(args.notes), Path(args.samples)
    profile = load_profile(profile_path)
    if not notes_path.is_file():
        raise InputError("Notes file not found: " + notes_path.name)
    if not samples_dir.is_dir():
        raise InputError("Samples folder not found: " + samples_dir.name)
    template_path = Path(args.template) if args.template else default_template_path()
    if not template_path.is_file():
        raise InputError("Template not found: " + template_path.name)
    date_text = args.date or datetime.date.today().isoformat()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_text):
        raise InputError("--date must look like 2026-10-19")
    notes_text = read_text_file(notes_path)
    template = read_text_file(template_path)
    out_dir = Path(args.out)
    skill_dir = out_dir / "my-voice"
    zip_path = out_dir / "my-voice.zip"

    notes, errors = check_notes(parse_notes(notes_text), samples_dir)
    rendered = None
    if not errors:
        samples_text = _sample_texts(samples_dir)
        values = placeholder_values(profile, notes, samples_text, date_text)
        rendered, render_errors = render_template(template, values)
        errors.extend(render_errors)
        if not errors:
            errors.extend(validate_skill_text(rendered))
    if errors:
        emit_json(collections.OrderedDict([
            ("ok", False), ("skill_dir", str(skill_dir)), ("zip", None), ("errors", errors), ("warnings", []),
        ]))
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".my-voice.tmp-", dir=str(out_dir)))
    try:
        with open(str(tmp / "SKILL.md"), "wb") as handle:
            handle.write(rendered.encode("utf-8"))
        replace_folder(tmp, skill_dir)
    finally:
        if tmp.exists():
            shutil.rmtree(str(tmp), ignore_errors=True)
    package_skill(skill_dir, zip_path)
    emit_json(collections.OrderedDict([
        ("ok", True), ("skill_dir", str(skill_dir)), ("zip", str(zip_path)), ("errors", []), ("warnings", []),
    ]))
    return 0


# ---------------------------------------------------------------------------
# package
# ---------------------------------------------------------------------------


def skill_files(skill_dir):
    """Every regular file to ship, as (archive path, file path), sorted."""
    skill_dir = Path(skill_dir)
    base = skill_dir.name
    found = []
    for root, dirs, files in os.walk(str(skill_dir)):
        dirs[:] = [d for d in dirs if d != "__pycache__" and not d.startswith(".")
                   and not os.path.islink(os.path.join(root, d))]
        for name in files:
            full = os.path.join(root, name)
            if name.startswith(".") or name.endswith(".pyc") or os.path.islink(full) or not os.path.isfile(full):
                continue
            rel = os.path.relpath(full, str(skill_dir)).replace(os.sep, "/")
            found.append((base + "/" + rel, full))
    found.sort(key=lambda item: item[0])
    return found


def package_skill(skill_dir, out_zip):
    skill_dir = Path(skill_dir)
    if not (skill_dir / "SKILL.md").is_file():
        raise InputError("There is no SKILL.md in " + skill_dir.name)
    out_resolved = os.path.normcase(os.path.abspath(str(out_zip)))
    files = [item for item in skill_files(skill_dir)
             if os.path.normcase(os.path.abspath(item[1])) != out_resolved]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for arcname, full in files:
            info = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            with open(full, "rb") as handle:
                archive.writestr(info, handle.read())
    atomic_write_bytes(out_zip, buffer.getvalue())
    return len(files)


def cmd_package(args):
    count = package_skill(args.skill_dir, args.out)
    emit_json(collections.OrderedDict([("ok", True), ("out", str(args.out)), ("files", count), ("warnings", [])]))
    return 0


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


def _real(path):
    return os.path.normcase(os.path.realpath(os.path.abspath(str(path))))


def _inside(child, parent):
    child, parent = _real(child), _real(parent)
    return child == parent or child.startswith(parent.rstrip(os.sep) + os.sep)


def cmd_install(args):
    src = Path(args.skill_dir)
    if not src.is_dir():
        raise InputError("Skill folder not found: " + src.name)
    if args.project is not None and args.personal:
        raise InputError("Choose one: --project or --personal, not both.")
    base = Path(os.path.abspath(str(src))).name
    home = Path.home()
    if args.personal:
        route = "personal"
        skills_dir = home / ".claude" / "skills"
        project = None
    else:
        route = "project"
        project = Path(os.path.abspath(args.project if args.project is not None else os.getcwd()))
        skills_dir = project / ".claude" / "skills"
    target = skills_dir / base
    if os.environ.get("MOREME_TEST_GUARD") == "1" and _inside(target, home / ".claude"):
        raise InputError(
            "MOREME_TEST_GUARD is set, so install will not write inside the home .claude folder: " + str(target)
        )
    if route == "project" and _real(project) == _real(home):
        emit_json(collections.OrderedDict([
            ("ok", False), ("reason", "project_is_home"), ("installed", None), ("warnings", []),
        ]))
        return 0
    errors = validate_skill_dir(src)
    if errors:
        raise InputError("The skill in {0} did not pass validate-skill: {1}".format(
            base, "; ".join(e["code"] for e in errors)))
    if target.exists() and not args.replace:
        raise InputError(
            "{0} is already installed at {1}. Ask the user whether to replace it, then run again with --replace.".format(
                base, target)
        )
    skills_dir.mkdir(parents=True, exist_ok=True)
    tmp = skills_dir / ".{0}.tmp-{1}".format(base, secrets.token_hex(4))
    try:
        shutil.copytree(str(src), str(tmp), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        replace_folder(tmp, target)
    finally:
        if tmp.exists():
            shutil.rmtree(str(tmp), ignore_errors=True)
    emit_json(collections.OrderedDict([
        ("ok", True), ("installed", str(target)), ("route", route), ("warnings", []),
    ]))
    return 0


# ---------------------------------------------------------------------------
# blind A/B
# ---------------------------------------------------------------------------

MAPPING_FILE = "ab-mapping.json"
RESULT_FILE = "ab-result.json"


def cmd_ab_shuffle(args):
    folder = Path(args.out)
    if secrets.randbelow(2) == 0:
        a_arm, b_arm = "with", "without"
    else:
        a_arm, b_arm = "without", "with"
    mapping = collections.OrderedDict([
        ("schema_version", SCHEMA_VERSION), ("A", a_arm), ("B", b_arm), ("created", now_iso()),
    ])
    write_json_file(folder / MAPPING_FILE, mapping)
    emit_json(collections.OrderedDict([("labels", ["A", "B"]), ("warnings", [])]))
    return 0


def _load_mapping(folder):
    path = Path(folder) / MAPPING_FILE
    if not path.is_file():
        raise InputError("No " + MAPPING_FILE + " in " + Path(folder).name + ". Run ab-shuffle first.")
    data = load_json_file(path, "Mapping file")
    if not isinstance(data, dict) or sorted([data.get("A"), data.get("B")], key=str) != ["with", "without"]:
        raise InputError("The A/B mapping file is not valid: " + MAPPING_FILE)
    return data


def cmd_ab_present(args):
    folder = Path(args.dir)
    mapping = _load_mapping(folder)
    drafts = {}
    for arm in ("with", "without"):
        path = folder / "draft-{0}.md".format(arm)
        if not path.is_file():
            raise InputError("Missing draft file: " + path.name)
        drafts[arm] = read_text_file(path).strip()
    text = "Draft A\n\n{0}\n\nDraft B\n\n{1}\n".format(drafts[mapping["A"]], drafts[mapping["B"]])
    sys.stdout.write(text)
    sys.stdout.flush()
    return 0


def cmd_ab_reveal(args):
    folder = Path(args.dir)
    result_path = folder / RESULT_FILE
    if result_path.exists():
        raise InputError("The A/B result was already revealed: " + RESULT_FILE)
    mapping = _load_mapping(folder)
    pick = args.pick.upper()
    result = collections.OrderedDict([
        ("schema_version", SCHEMA_VERSION),
        ("picked", pick),
        ("picked_arm", mapping[pick]),
        ("mapping", collections.OrderedDict([("A", mapping["A"]), ("B", mapping["B"])])),
        ("revealed", now_iso()),
    ])
    write_json_file(result_path, result)
    shown = collections.OrderedDict(result)
    shown["warnings"] = []
    emit_json(shown)
    return 0


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def version_info():
    return collections.OrderedDict([
        ("analyze_version", ANALYZE_VERSION),
        ("schema_version", SCHEMA_VERSION),
        ("python", "{0}.{1}.{2}".format(*sys.version_info[:3])),
    ])


def _pick(value):
    value = value.strip().upper()
    if value not in ("A", "B"):
        raise argparse.ArgumentTypeError("type A or B")
    return value


def build_parser():
    parser = argparse.ArgumentParser(
        prog="analyze.py",
        description="MoreMe analyze.py: measure writing style from your own samples. "
                    "Uses only the Python standard library and opens no network connections.",
        epilog="Add --debug to show full error details.",
    )
    parser.add_argument("--version", action="store_true", help="print version information as JSON and exit")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    p = sub.add_parser("profile", help="measure one or more text files")
    p.add_argument("files", nargs="+", metavar="FILE", help="text files you wrote")
    p.add_argument("--view", choices=("exposed", "all"), default="exposed",
                   help="exposed (default) shows the numbers a skill may use; all adds eval-only data")
    p.add_argument("--out", metavar="PATH", help="write the profile to PATH instead of printing it")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("compare", help="measure the distance between two profiles")
    p.add_argument("profile_a", metavar="PROFILE_A")
    p.add_argument("profile_b", metavar="PROFILE_B")
    p.add_argument("--reference-stats", metavar="PATH", help="reference stats file used for z-scores")
    p.add_argument("--out", metavar="PATH", help="write the result to PATH")
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("attribute", help="guess which writer a draft profile is closest to")
    p.add_argument("draft_profile", metavar="DRAFT_PROFILE")
    p.add_argument("--candidates", required=True, metavar="DIR", help="folder of candidate profiles (*.json)")
    p.add_argument("--reference-stats", required=True, metavar="PATH")
    p.add_argument("--out", metavar="PATH", help="write the result to PATH")
    p.set_defaults(func=cmd_attribute)

    p = sub.add_parser("reference-stats", help="build reference stats from a train folder")
    p.add_argument("train_dir", metavar="TRAIN_DIR", help="one subfolder of .txt files per writer")
    p.add_argument("--chunk-words", type=int, default=1000, metavar="N", help="words per chunk (default 1000)")
    p.add_argument("--out", required=True, metavar="PATH")
    p.set_defaults(func=cmd_reference_stats)

    p = sub.add_parser("report", help="describe a profile in plain words")
    p.add_argument("profile", metavar="PROFILE")
    p.add_argument("--out", metavar="PATH", help="write the text to PATH")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("validate-skill", help="check a skill folder against the skill rules")
    p.add_argument("dir", metavar="DIR")
    p.set_defaults(func=cmd_validate_skill)

    p = sub.add_parser("build-skill", help="fill the my-voice template and build my-voice.zip")
    p.add_argument("profile", metavar="PROFILE")
    p.add_argument("notes", metavar="NOTES")
    p.add_argument("--samples", required=True, metavar="DIR")
    p.add_argument("--out", required=True, metavar="DIR")
    p.add_argument("--template", metavar="PATH")
    p.add_argument("--date", metavar="YYYY-MM-DD")
    p.set_defaults(func=cmd_build_skill)

    p = sub.add_parser("package", help="zip a skill folder (same bytes every time)")
    p.add_argument("skill_dir", metavar="SKILL_DIR")
    p.add_argument("--out", required=True, metavar="ZIP")
    p.set_defaults(func=cmd_package)

    p = sub.add_parser("install", help="copy a skill into a Claude Code skills folder")
    p.add_argument("skill_dir", metavar="SKILL_DIR")
    p.add_argument("--project", metavar="PROJECT_DIR", help="project folder (default: the current folder)")
    p.add_argument("--personal", action="store_true", help="install into your personal skills folder")
    p.add_argument("--replace", action="store_true", help="replace an installed copy")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("ab-shuffle", help="assign the A and B labels at random")
    p.add_argument("--out", required=True, metavar="DIR")
    p.set_defaults(func=cmd_ab_shuffle)

    p = sub.add_parser("ab-present", help="print draft A and draft B")
    p.add_argument("dir", metavar="DIR")
    p.set_defaults(func=cmd_ab_present)

    p = sub.add_parser("ab-reveal", help="record the pick and show which draft was which")
    p.add_argument("dir", metavar="DIR")
    p.add_argument("--pick", required=True, type=_pick, metavar="A|B")
    p.set_defaults(func=cmd_ab_reveal)
    return parser


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    debug = "--debug" in argv
    argv = [a for a in argv if a != "--debug"]
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    try:
        if args.version:
            emit_json(version_info())
            return 0
        if not getattr(args, "command", None):
            parser.print_usage(sys.stderr)
            sys.stderr.write("analyze.py: error: choose a command, or run with --help\n")
            return 2
        return args.func(args)
    except InputError as exc:
        sys.stderr.write("Error: {0}\n".format(exc))
        return 2
    except Exception as exc:  # internal error: one line unless --debug
        if debug:
            traceback.print_exc()
        sys.stderr.write("Internal error ({0}): {1}\n".format(type(exc).__name__, str(exc).splitlines()[0] if str(exc) else ""))
        return 1


def configure_stdio():
    """Print UTF-8 regardless of the console code page (Windows cp1252 consoles)."""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, io.UnsupportedOperation):
            buffer = getattr(stream, "buffer", None)
            if buffer is not None:
                setattr(sys, name, io.TextIOWrapper(buffer, encoding="utf-8"))


if __name__ == "__main__":
    configure_stdio()
    sys.exit(main())
