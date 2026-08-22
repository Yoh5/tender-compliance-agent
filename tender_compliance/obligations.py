"""Pulling obligations out of a tender pack. NOT IMPLEMENTED YET.

This is the first of the three hard parts, and the only one where a language
model is genuinely the right tool: the obligations are written in prose, they
are scattered across four or five documents, and the same requirement is worded
differently by every buyer. No pattern matching survives contact with that.

The invariants below are the design, and they are written before the code
because they are what the code will be judged on.

INVARIANT 1 — EVERY OBLIGATION CITES ITS PAGE

An obligation without a page reference is unusable: the bidder cannot check it,
and cannot argue it with the buyer. The extractor returns a page or it returns
nothing. It never returns a requirement it cannot locate.

INVARIANT 2 — BID-STAGE AND PERFORMANCE ARE SEPARATED AT EXTRACTION

Not later, not by a filter over the results. The distinction (see
`coverage.py`) decides whether the headline number means anything, and it can
only be made while the surrounding text is still available — "the holder shall
provide monthly reports" and "the candidate shall provide an attestation" are
grammatically identical and differ only in context.

When the context does not settle it, the obligation is marked BID. A
performance obligation wrongly counted as blocking costs a pointless check; a
blocking obligation wrongly filed as performance costs the tender.

INVARIANT 3 — THE MODEL NEVER MERGES OR DEDUPLICATES

Two obligations that look like one are still two rows, each with its own page.
Merging is a decision, and a decision made silently over a document the reader
has not seen is the kind that surfaces at the opening.
"""

from __future__ import annotations

from dataclasses import dataclass

from tender_compliance.coverage import Citation, Stage


@dataclass(frozen=True)
class Obligation:
    """One requirement, as stated by the tender pack."""

    text: str
    """Quoted or closely paraphrased — never summarised into a category. The
    bidder has to recognise it when they open the document at that page."""

    source: Citation
    stage: Stage
    max_age_months: int | None = None
    """Set when the pack demands a recent document ("de moins de 6 mois"), so
    `validity.assess` can apply the age rule. Read from the text, applied by
    code."""


def extract(pages: list[str]) -> list[Obligation]:
    """Read a tender pack and return what it requires of a bidder.

    Not implemented. The signature takes pages rather than a blob so that a
    page number is always available to cite — the alternative, recovering the
    page after the fact by searching for the sentence, fails on the sentences
    that appear twice.
    """
    raise NotImplementedError(
        "obligation extraction is not built yet — see the invariants above"
    )
