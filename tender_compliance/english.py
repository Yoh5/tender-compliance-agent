"""An English gloss beside each French quotation. Decoration, walled off.

WHY THIS EXISTS

Every row this tool prints quotes the tender word for word, and `obligations.
anchor` checks that the quotation really is on the page it cites. That check is
the product. It is also why the rows are in French: the tender is French, and a
translated "quotation" is not a quotation — it is the model's paraphrase wearing
a citation.

But a reader who does not read French sees a verdict and an opaque sentence. So
each row carries a translation *beside* the quotation, never instead of it.

A row already written in English carries none: printing the same sentence twice
is not a service. That is decided per row rather than per file, because a pack
that quotes an English annex inside a French règlement is one file with two
languages in it, and the reader meets them one after another.

WHY IT RUNS LAST, AND SEPARATELY

The obvious implementation asks the extraction agent for a translation while it
is already reading the page — one field more on the schema, no extra call. It
was rejected: adding work to that call risks the thing it is there for. On
2026-09-03 the extraction phase silently dropped article IV.7 of the ANTAI file,
the turnover floor the whole demonstration turns on, for no reason anyone can
point at. Recall in that phase is the scarce resource, and this feature is not
worth spending any of it.

So the translation runs afterwards, over rows that are already decided, in its
own call, with no tools — it cannot read the tender, so it cannot start deciding
things about it. If it fails, `attach` returns the rows it was given and the
report is byte for byte the report we would have printed anyway. A translation
that did not arrive is a missing convenience; a report that did not arrive is a
lost bid.
"""

from __future__ import annotations

import re as _re
from dataclasses import replace
from typing import Callable, Sequence

Translate = Callable[[Sequence[str]], list[str]]
"""Given the requirements in order, return one English line for each."""


LINES_PER_CALL = 20
"""How many requirements are translated per round trip.

Higher than the evidence phase's five because nothing here has to be matched
back to anything: a mistranslated line is a cosmetic error, while a misaligned
*match* is a wrong verdict. The alignment is still checked — a batch whose
answer has the wrong length is refused whole — but the cost of being wrong is
what sets the size, and here it is low.
"""


def attach(rows: list, translate: Translate) -> list:
    """Return `rows` with `gloss` filled in, or return `rows` unchanged.

    There is no partial outcome on purpose. A translator that returns the wrong
    number of lines has lost track of which line is which, and a gloss attached
    to the wrong requirement is worse than no gloss: it reads as though the tool
    understood the document and got it wrong.
    """
    if not rows:
        return rows

    # Ligne par ligne, pas fichier par fichier : un dossier qui cite une annexe
    # anglaise dans un règlement français est un fichier avec deux langues
    # dedans, et le lecteur les rencontre l'une après l'autre.
    a_traduire = [(rang, row.requirement) for rang, row in enumerate(rows)
                  if not looks_english(row.requirement)]
    if not a_traduire:
        return rows

    try:
        traduites = translate([texte for _, texte in a_traduire])
    except Exception:
        return rows

    if not isinstance(traduites, (list, tuple)) or len(traduites) != len(a_traduire):
        return rows

    gloses = {rang: " ".join(str(t).split())
              for (rang, _), t in zip(a_traduire, traduites)}
    return [replace(row, gloss=gloses[rang]) if rang in gloses else row
            for rang, row in enumerate(rows)]


# ---------------------------------------------------------------- the counter

_MOT = _re.compile(r"[^\W\d_]+", _re.UNICODE)

_ANGLAIS = frozenset("""
the of and to in for by is are be been shall must that this these those with
which not any all from will have has at as its their our your if when where
who whose than then such each may can should would upon into within without
under over before after during including provided both between during other
""".split())

_FRANCAIS = frozenset("""
le la les un une des du de et ou au aux dans pour par sur est sont qui que ne
pas ce cette ces son sa ses leur leurs avec sans sous chaque tout tous toute
toutes plus moins lors dont ainsi doit doivent peut peuvent etre être avoir
cas si en aucun aucune celui celle ceux mais donc
""".split())

_ELISIONS = frozenset("d l qu n s j m t c".split())
"""What an apostrophe leaves behind: « d'une », « l'honneur », « qu'il ». These
are French by construction — English does not elide like this — and they survive
tokenising, so they are worth counting."""


def looks_english(text: str) -> bool:
    """True when this requirement is already in English and needs no gloss.

    Decided here, in code, from the words themselves. Asking the model which
    language it is looking at would hand it the decision about what the reader
    sees, and this is precisely the sort of call that does not need one:
    function words separate the two languages sharply, and a counter can be
    read, tested, and disagreed with.

    THE ASYMMETRY IS DELIBERATE. A missing gloss makes a row unreadable to the
    audience it was added for; a redundant one is clutter. So the answer is
    False whenever the evidence is thin — a form code, a date, a bare reference
    — and English has to be shown rather than assumed.
    """
    mots = [m.lower() for m in _MOT.findall(text or "")]
    anglais = sum(1 for m in mots if m in _ANGLAIS)
    francais = sum(1 for m in mots if m in _FRANCAIS or m in _ELISIONS)
    return anglais >= 2 and anglais > 2 * francais


def translator(agent_factory) -> Translate:
    """A `Translate` backed by a Strands agent, batched.

    `agent_factory` is called with no tools. The reading tools exist so the
    obligation agent can check a wording against the page it came from; a
    translator that could do the same could also be asked whether the wording is
    really there, which is a verdict, and verdicts are not this module's to make.
    """
    from pydantic import BaseModel, Field

    class _Lines(BaseModel):
        lines: list[str] = Field(
            default_factory=list,
            description="one English line per numbered requirement, same order",
        )

    def translate(textes: Sequence[str]) -> list[str]:
        sortie: list[str] = []
        for depart in range(0, len(textes), LINES_PER_CALL):
            lot = list(textes[depart:depart + LINES_PER_CALL])
            numerotees = "\n".join(f"{i}. {t}" for i, t in enumerate(lot, start=1))
            reponse = agent_factory().structured_output(
                _Lines, f"{_BRIEF}\n\n{numerotees}"
            )
            lignes = list(reponse.lines)
            if len(lignes) != len(lot):
                raise ValueError(
                    f"translator returned {len(lignes)} lines for {len(lot)} "
                    f"requirements; refusing to guess which is which")
            sortie.extend(lignes)
        return sortie

    return translate


_BRIEF = """\
Translate each numbered requirement from a French public-procurement file into
plain English, for a reader who does not read French.

- Return exactly one line per number, in the same order. Never merge, split,
  reorder or omit a line.
- Keep it short: this is read beside the French original, not instead of it.
- Keep French administrative names as they are — DC1, DC2, DC4, DUME, Kbis,
  URSSAF, acte d'engagement — and translate the sentence around them. A bidder
  has to ask for the form by its real name.
- Translate what the line says. Do not judge whether it is satisfied, do not add
  advice, and do not comment on whether a document exists.
"""
