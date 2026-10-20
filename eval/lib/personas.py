"""Persona metadata shared by the e2e driver and the eval harness.

Each eval persona gets an invented first name. The simulated interviewee uses
it when asked for a name and when it signs a sample, so the model never falls
back on a name it finds elsewhere on the machine (the first labeled run signed
both A/B drafts with a name taken from the Windows user folder).

The names are made up. They are not the names of the real writers behind the
personas (those live only in eval/corpus/PROVENANCE.md), and a test checks that
no first name matches a word in any PROVENANCE author line.
"""

PERSONA_FIRST_NAMES = {
    "era-c": "Hattie",
    "era-d": "Louisa",
    "era-e": "Walter",
    "era-f": "Samuel",
    "modern-a": "Graham",
    "modern-b": "Dale",
}


def persona_first_name(persona_id):
    """The invented first name for a persona id (KeyError if unknown)."""
    return PERSONA_FIRST_NAMES[persona_id]


def name_rule(persona_id):
    """One rule line for a simulated interviewee brief."""
    n = persona_first_name(persona_id)
    return ("- Your first name is %s. In your first answer, mention it once in passing (for example "
            "\"I'm %s.\"). If MoreMe asks your name, say %s. When you sign a letter, note, or sample, sign it "
            "%s. Never use any other name for yourself." % (n, n, n, n))
