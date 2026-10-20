# Eval corpus licenses

The MIT license in the repository root covers the code only. It does not cover the eval corpus or any file that contains corpus text. Those files stay under the licenses of their sources, listed here per persona. Attribution, source URLs, and the changes made to each document are in `PROVENANCE.md` in this folder.

## Licenses by persona

| Persona | Era | License | Files |
|---|---|---|---|
| `modern-a` | modern | Open Government Licence v3.0 (Crown copyright). Attribution statement: "Contains public sector information licensed under the Open Government Licence v3.0." | `eval/corpus/modern-a/` |
| `modern-b` | modern | Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0). These files and every file derived from them are licensed CC BY-SA 4.0. | `eval/corpus/modern-b/` |
| `era-c` | era-diverse | Public domain in the USA (published 1914). Demo persona. | `eval/corpus/era-c/` |
| `era-d` | era-diverse | Public domain in the USA (published 1913) | `eval/corpus/era-d/` |
| `era-e` | era-diverse | Public domain in the USA (published 1870) | `eval/corpus/era-e/` |
| `era-f` | era-diverse | Public domain in the USA (published 1902) | `eval/corpus/era-f/` |

The public-domain status applies in the United States. Users elsewhere should check their local law. The public-domain texts were transcribed by Project Gutenberg volunteers; all Project Gutenberg marks and license text were removed, as Project Gutenberg's license allows for US public-domain works.

Licenses link: OGL v3.0 at https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/ and CC BY-SA 4.0 at https://creativecommons.org/licenses/by-sa/4.0/. Neither license implies endorsement by the source or its author.

## Derived files

Licensing covers every file that contains corpus text, not only this folder. Each of these files carries a header line naming its persona's license (the exact text for each persona is the `header` field in `licenses.json`):

| Derived file | Path |
|---|---|
| Generated persona skills (they quote train excerpts) | `eval/skills/<persona-id>/` |
| Skill-generation transcripts | `eval/results/**/<persona-id>/` or files named `<persona-id>*` under `eval/results/` |
| Run manifests that hold corpus text | same rule as transcripts |
| Prompts for the samples-pasted arm (they include train excerpts) | same rule as transcripts |
| Raw drafts' prompt records | same rule as transcripts |
| Demo persona e2e transcript and example run (persona `era-c`, public domain) | `docs/transcript-e2e.md`, `docs/example-run/` |

Rules:

1. Files derived from `modern-b` (CC BY-SA 4.0) are licensed CC BY-SA 4.0 and carry the `modern-b` header, which states that license and points to the attribution in `PROVENANCE.md`.
2. Files derived from `modern-a` (OGL v3.0) carry the OGL attribution statement in the `modern-a` header.
3. Files derived from a public-domain persona say so in that persona's header.
4. A file that holds text from several personas carries the header of each persona it includes.
5. Markdown files put the header in an HTML comment (`<!-- ... -->`) on the first line, or on the first line after YAML front matter. Text files put it on the first line. JSON files put it in a top-level `"license_header"` field. JSONL files put it in a `"license_header"` field of every record.
6. The header names the persona ID only. Writer names stay in `PROVENANCE.md`.

`tests/test_corpus_license_headers.py` checks rule 1 and 2 for every file under `eval/` (outside `eval/corpus/` and `eval/sourcing/`) whose path has a folder named after a non-public-domain persona or whose file name starts with that persona's ID.

The reference statistics file in `eval/` and `eval/split.json` hold numbers only (means, standard deviations, word counts), not corpus text, so they need no header.

The root README license section says the MIT license covers the code and the eval data has its own licenses (this file).
