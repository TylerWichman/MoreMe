"""Eval task list (AD-006 Tasks) and prompt rendering.

eval/tasks/tasks.json holds 8 dev tasks and 8 held-out tasks per persona. Each
task names a topic and a channel. Topics never quote corpus text. Held-out
topics come from held-out document titles where a title names a topic, else from
the persona's register line in PROVENANCE.md (both are metadata; no held-out
text is read). Target length comes from split.json word counts.

The rendered prompt is identical in every arm. The samples-pasted arm adds a
fixed prefix with 3 train excerpts; explicit mode (only if the dev smoke's
real-skill invocation rate is below 80%) adds a text prefix.

    python -m harness.tasks build     (from eval/) rewrite tasks.json from TOPICS
    python -m harness.tasks check     verify tasks.json matches TOPICS and split.json
"""
import random
import sys

from harness import common

CHANNELS = {
    "email": ("an email to a colleague", "email"),
    "post": ("a short blog post", "post"),
    "note": ("a note to a friend", "note"),
}
CHANNEL_CYCLE = ("email", "post", "note", "email", "post", "note", "email", "post")

PROMPT_TEMPLATE = "Write {channel_phrase} about {topic}. Aim for about {words} words. Reply with the {noun} only."

# Explicit-mode prefixes (AD-006, used only if the switch check fires).
# The neutral prefix has the same length in characters as the skill prefix.
EXPLICIT_PREFIX = "Use my-voice skill:"
NEUTRAL_PREFIX = "Please do the task:"

SAMPLES_INTRO = ("Here are three short samples of my writing. Match my style in what you write.")
SAMPLES_EXCERPT_WORDS = 150

# (source, topic). source: "heldout-title", "dev-title", "train-title", or "register".
TOPICS = {
    "modern-a": {
        "heldout": [
            ("heldout-title", "the anniversary of a public website your team runs"),
            ("heldout-title", "replacing an old paper-based payments process with a digital service"),
            ("heldout-title", "what your team delivered over the last year and a bit"),
            ("heldout-title", "how to change a large, slow organization"),
            ("register", "why services should be built around users, not around the org chart"),
            ("register", "lessons from rebuilding a service people depend on every day"),
            ("register", "thanking a team after a big launch"),
            ("register", "what comes next for your digital team"),
        ],
        "dev": [
            ("dev-title", "why your team exists and what it is for"),
            ("dev-title", "moving from publishing information to running transactions online"),
            ("dev-title", "working in the open"),
            ("dev-title", "working together across departments"),
            ("register", "a progress update on a digital project"),
            ("register", "hiring people with digital skills"),
            ("register", "asking colleagues to try a new way of working"),
            ("register", "what you learned from a project that went wrong"),
        ],
    },
    "modern-b": {
        "heldout": [
            ("heldout-title", "how the falling cost of making things might change why people work"),
            ("heldout-title", "using open organization principles to cut energy use in a factory"),
            ("heldout-title", "what the sharing economy means for how companies are run"),
            ("register", "a business book you read recently and what your team can take from it"),
            ("register", "building trust in a team that works across countries"),
            ("register", "how managers can share decisions with their teams"),
            ("register", "encouraging people to share what they know at work"),
            ("register", "helping a company adapt to fast change"),
        ],
        "dev": [
            ("dev-title", "how communities form around a shared interest and who connects people"),
            ("dev-title", "examples of the sharing economy in daily life"),
            ("register", "why transparency helps a team"),
            ("register", "a lesson from working with people from another culture"),
            ("register", "running a meeting where everyone speaks up"),
            ("register", "what motivates people at work besides pay"),
            ("register", "a simple framework you use to think about teams"),
            ("register", "keeping energy up during a long project"),
        ],
    },
    "era-c": {
        "heldout": [
            ("register", "a recent trip to town and who you met there"),
            ("register", "the weather and how it has changed your plans"),
            ("register", "a funny thing that happened with a neighbor"),
            ("register", "a new hobby you have taken up"),
            ("register", "news about your family"),
            ("register", "a book you have been reading"),
            ("register", "a visit you are planning"),
            ("register", "a small mishap around the house"),
        ],
        "dev": [
            ("register", "an outing you enjoyed last weekend"),
            ("register", "the garden this season"),
            ("register", "an old friend you ran into"),
            ("register", "a meal you cooked for guests"),
            ("register", "a long walk in the country"),
            ("register", "a letter you received that made you laugh"),
            ("register", "plans for the holidays"),
            ("register", "an animal that has been causing trouble"),
        ],
    },
    "era-d": {
        "heldout": [
            ("register", "a day of worrying news and how you coped"),
            ("register", "a visit from friends"),
            ("register", "a sleepless night"),
            ("register", "rumors going around town"),
            ("register", "sewing and chores on a quiet day"),
            ("register", "a quarrel and making up afterward"),
            ("register", "missing someone who is far away"),
            ("register", "a sudden change of plans"),
        ],
        "dev": [
            ("register", "a restless day spent waiting for news"),
            ("register", "an evening of music with family"),
            ("register", "a walk in the rain"),
            ("register", "reading late at night"),
            ("register", "a conversation that stayed with you"),
            ("register", "a small celebration"),
            ("register", "feeling homesick"),
            ("register", "a day when nothing went right"),
        ],
    },
    "era-e": {
        "heldout": [
            ("register", "the first week of planting a vegetable garden"),
            ("register", "battling weeds"),
            ("register", "a neighbor's advice about your garden"),
            ("register", "pests eating the vegetables"),
            ("register", "the first harvest of the year"),
            ("register", "garden tools that never seem to work"),
            ("register", "the weather spoiling your garden plans"),
            ("register", "why everyone should grow something"),
        ],
        "dev": [
            ("register", "getting the soil ready in spring"),
            ("register", "a vegetable that refused to grow"),
            ("register", "birds in the garden"),
            ("register", "watering during a dry spell"),
            ("register", "a cat that keeps digging in the beds"),
            ("register", "reading seed catalogs in winter"),
            ("register", "giving away too many tomatoes"),
            ("register", "the end of the growing season"),
        ],
    },
    "era-f": {
        "heldout": [
            ("heldout-title", "not being discouraged by setbacks"),
            ("heldout-title", "the value of owning a home"),
            ("heldout-title", "impressions from a trip abroad"),
            ("register", "doing every task well, however small"),
            ("register", "the habit of saving money"),
            ("register", "good manners and why they matter"),
            ("register", "being honest when it costs you something"),
            ("register", "making the most of your time at school"),
        ],
        "dev": [
            ("dev-title", "the hard side and the pleasant side of life"),
            ("train-title", "helping others"),
            ("train-title", "living simply"),
            ("train-title", "setting a good example"),
            ("train-title", "doing your best"),
            ("train-title", "saying plainly what things are"),
            ("register", "keeping your things clean and in order"),
            ("register", "using your spare time well"),
        ],
    },
}


def render_prompt(task):
    phrase, noun = CHANNELS[task["channel"]]
    return PROMPT_TEMPLATE.format(channel_phrase=phrase, topic=task["topic"], words=task["target_words"], noun=noun)


def build(split=None):
    split = split or common.load_split()
    out = {"schema_version": "1",
           "prompt_template": PROMPT_TEMPLATE,
           "channels": dict((k, list(v)) for k, v in CHANNELS.items()),
           "length_rule": "median held-out document word count from eval/split.json, clamped to 120-400",
           "tasks": []}
    for persona in common.RUN_ORDER:
        n = common.target_length(split, persona)
        for which in ("dev", "heldout"):
            for i, (source, topic) in enumerate(TOPICS[persona][which]):
                task = {"id": "%s-%s-%02d" % (persona, which, i + 1), "persona": persona, "split": which,
                        "channel": CHANNEL_CYCLE[i], "topic": topic, "topic_source": source, "target_words": n}
                task["prompt"] = render_prompt(task)
                out["tasks"].append(task)
    return out


def load(path=None):
    return common.read_json(path or common.TASKS_JSON)


def select(tasks_doc, persona=None, which=None):
    return [t for t in tasks_doc["tasks"]
            if (persona is None or t["persona"] == persona) and (which is None or t["split"] == which)]


def train_excerpts(split, persona, n=3, words_each=SAMPLES_EXCERPT_WORDS, seed=common.SAMPLES_SEED):
    """3 fixed train excerpts per persona for the samples-pasted arm: the train
    text (files in sorted order, joined by a blank line) is cut into consecutive
    150-word chunks and 3 are drawn with a seeded RNG. Same 3 for every task."""
    an = common.load_analyze()
    files = sorted(common.split_files(split, persona, "train"))
    text = "\n\n".join(common.read_corpus_text(split, f, allow=("train",)).strip("\n") for f in files)
    chunks = an.chunk_text(text, words_each)
    rng = random.Random("%s:%s" % (seed, persona))
    picks = sorted(rng.sample(range(len(chunks)), n))
    return [chunks[i] for i in picks]


def arm_prompt(task_prompt, arm, mode="auto", excerpts=None):
    """Full prompt for one arm. mode is "auto" (pre-registered default) or
    "explicit" (switch check fired)."""
    body = task_prompt
    if arm == "samples-pasted":
        if not excerpts or len(excerpts) != 3:
            raise ValueError("samples-pasted needs exactly 3 excerpts")
        parts = [SAMPLES_INTRO, ""]
        for i, ex in enumerate(excerpts):
            parts += ["Sample %d:" % (i + 1), ex.strip(), ""]
        body = "\n".join(parts) + task_prompt
    if mode == "explicit":
        prefix = EXPLICIT_PREFIX if arm == "with" else NEUTRAL_PREFIX
        body = prefix + " " + body
    elif mode != "auto":
        raise ValueError("mode must be auto or explicit")
    return body


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "check"
    fresh = build()
    if cmd == "build":
        common.write_json(common.TASKS_JSON, fresh)
        print("wrote %d tasks" % len(fresh["tasks"]))
        return 0
    saved = load()
    if saved != fresh:
        print("tasks.json differs from TOPICS/split.json; run: python -m harness.tasks build", file=sys.stderr)
        return 1
    print("ok: %d tasks" % len(saved["tasks"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
