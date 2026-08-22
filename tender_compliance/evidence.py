"""Matching an obligation to a document that proves it. NOT IMPLEMENTED YET.

The second hard part, and the one where a language model is most likely to be
helpful and most likely to do damage. Helpful, because "attestation d'assurance
responsabilité civile professionnelle" and "RC Pro" are the same thing and no
string comparison knows that. Damaging, because a model asked "does this
document satisfy this requirement?" will almost always find a way to say yes.

The asymmetry decides the design. A missed match costs a needless check — the
bidder looks in a folder and finds the paper. A wrong match costs the tender,
and it costs it invisibly: the matrix says covered, nobody looks, the envelope
goes out short.

INVARIANT 1 — A MATCH WITHOUT A PAGE IS NOT A MATCH

The model must name the document and the page that proves the point. When it
cannot, the row is NEEDS_REVIEW, never COVERED. `coverage.check()` enforces
this structurally, so a lapse here fails loudly instead of printing.

INVARIANT 2 — THE VERDICT ON DATES IS NOT THE MODEL'S

The matcher's job ends at "this document answers this requirement". Whether the
document is still good on the submission date is `validity.assess`, and it is
arithmetic. A model that reports a document as valid is a model deciding
something it has no way to check.

INVARIANT 3 — UNCERTAINTY GOES DOWNWARD

There are three outcomes, not two: proven, absent, and uncertain. A tool that
only has "yes" and "no" will spend its uncertainty on "yes", because that is
the answer that makes the report look finished.
"""

from __future__ import annotations

from dataclasses import dataclass

from tender_compliance.coverage import Citation
from tender_compliance.obligations import Obligation
from tender_compliance.validity import Document


@dataclass(frozen=True)
class Match:
    """What was found for one obligation, and how sure we are."""

    obligation: Obligation
    document: Document | None
    citation: Citation | None
    certain: bool
    """False routes the row to NEEDS_REVIEW. There is no numeric score: a
    confidence figure invites a threshold, a threshold invites tuning, and
    tuning a threshold on a handful of tenders produces a number that means
    nothing on the next one."""

    reason: str = ""
    """Why this document, in one sentence, for the reader who disagrees."""


def find(obligation: Obligation, library: list[Document]) -> Match:
    """Look for the document that answers this obligation.

    Not implemented. When it is, it returns a `Match` with `certain=False`
    rather than guessing — and never a `Match` with a document but no citation.
    """
    raise NotImplementedError(
        "evidence matching is not built yet — see the invariants above"
    )
