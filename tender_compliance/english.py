"""An English gloss beside each French quotation. Decoration, walled off.

WHY THIS EXISTS

Every row this tool prints quotes the tender word for word, and `obligations.
anchor` checks that the quotation really is on the page it cites. That check is
the product. It is also why the rows are in French: the tender is French, and a
translated "quotation" is not a quotation — it is the model's paraphrase wearing
a citation.

But a reader who does not read French sees a verdict and an opaque sentence. So
each row carries a translation *beside* the quotation, never instead of it.

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

    try:
        traduites = translate([row.requirement for row in rows])
    except Exception:
        return rows

    if not isinstance(traduites, (list, tuple)) or len(traduites) != len(rows):
        return rows

    return [replace(row, gloss=" ".join(str(t).split()))
            for row, t in zip(rows, traduites)]


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
