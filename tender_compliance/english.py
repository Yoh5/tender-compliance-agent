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

    # Un dernier filtre sur ce qui est revenu, pas sur ce qui est parti : le
    # compteur en amont a deja tranche, et il lui arrive de se tromper vers le
    # bas. Une glose qui redit l'exigence n'est pas une traduction.
    gloses = {rang: glose for rang, glose in gloses.items()
              if _ajoute_quelque_chose(glose, rows[rang].requirement)}

    return [replace(row, gloss=gloses[rang]) if rang in gloses else row
            for rang, row in enumerate(rows)]


_ENUMERATEUR = _re.compile(
    r"^\s*(?:\d{1,3}|[a-z]|[ivxlcdm]{1,4})\s*[.)\]]\s+", _re.IGNORECASE)
"""A leading list marker: `2. `, `a) `, `iv] `. Translators add and drop these
freely, and a difference of numbering is not a difference of meaning."""


def _mots_nus(texte: str) -> list:
    """The words, in order, stripped of case, punctuation and list marker."""
    return _re.findall(r"[^\W_]+", _ENUMERATEUR.sub("", texte or "").lower(),
                       _re.UNICODE)


def _ajoute_quelque_chose(glose: str, exigence: str) -> bool:
    """Whether this translation says anything the requirement did not.

    Observed on the European Parliament pack, 2026-09-04: three English
    fragments were judged non-English by the counter, sent to the translator,
    and came back as themselves with a number in front —

        MISSING  p16  employ fewer than 250 persons
                  EN 2. employ fewer than 250 persons

    The counter's bar is two English function words, and these fragments carry
    one. Lowering it is not an option: a French fragment such as "Assurance
    responsabilite civile" carries none either, and it would stop being glossed
    — losing the rows this feature exists for, to save three it does not.

    So the bar stays and the output is checked instead.

    The first version of this test was exact equality of the words. The document
    itself refused it on the very next run:

        MISSING  p16  an annual balance sheet total not exceeding EUR 43 million.
                  EN 4. Annual balance sheet total not exceeding EUR 43 million.

    Not an echo — the translator dropped one article — and useless all the same.
    So the question is not whether the two strings match but whether the gloss
    brings a word the requirement did not already have. That is what a reader
    gains or does not gain, and it is why the rule holds across two languages:
    French and English almost never spell a word the same way, so a real gloss
    of a French line brings new words by construction. One that brings none was
    never translating anything.

    The call is still paid for. That is the honest cost of deciding on what came
    back rather than guessing beforehand, and it buys a report that never shows
    a row glossed with itself.

    A gloss with no word at all — empty, or reduced to a dash — needs no special
    case: it brings no new word because it brings none.
    """
    return bool(set(_mots_nus(glose)) - set(_mots_nus(exigence)))


# ---------------------------------------------------------------- the counter

_MOT = _re.compile(r"[^\W\d_]+", _re.UNICODE)

_ADRESSE = _re.compile(r"\S+@\S+|(?:https?://|www\.)\S+", _re.IGNORECASE)
"""URLs and email addresses, removed before a single word is counted.

They are not written in any language, and they vote: the path
`/budget/explained/management/protecting/protect_en.cfm` tokenises into a dozen
words, one of which is « en ». That was enough to drag a plainly English
sentence back across the line. These files are full of links — the French DC1
requirement carries `economie.gouv.fr` inside the sentence that states it — so
this is the common case, not the exotic one.
"""

_ANGLAIS = frozenset("""
the of and to in for by is are be been shall must that this these those with
which not any all from will have has at as its their our your if when where
who whose than then such each may can should would upon into within without
under over before after during including provided both between during other
an was were do does no more less fewer only also however unless until while
whether above below against among across through since they them we what why
how it being every another several many much few some most least same therefore
thus whereas thereof herein hereby
""".split())
"""English function words. Deliberately does NOT contain `a`, `on`, `or`, `but`
or `car`: each is an ordinary French word, and a list that counts them votes for
English on French prose.

The second line was added on 2026-09-04, after two five-word requirements in the
European Parliament pack were sent to the translator and came back as
themselves. `employ fewer than 250 persons` carried exactly one word this list
knew. A short line has few function words in it, so a thin list does not merely
lose precision on short lines — it fails on them."""

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
    mots = [m.lower() for m in _MOT.findall(_ADRESSE.sub(" ", text or ""))]
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
