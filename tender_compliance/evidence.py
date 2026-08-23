"""Matching an obligation to the document that proves it.

The second hard part, and the one where a model is most useful and most
dangerous. Useful, because "attestation d'assurance responsabilité civile
professionnelle" and "RC Pro" are the same paper and no string comparison knows
that. Dangerous, because a model asked "does this document satisfy this
requirement?" will nearly always find a way to say yes.

The asymmetry decides everything here. A missed match costs a needless look in a
folder. A wrong match costs the tender, and costs it *invisibly*: the matrix
says covered, nobody checks, the envelope goes out short.

WHAT THE MODEL IS ALLOWED TO DO, AND WHAT IT IS NOT

It may make the semantic leap — obligation to document name — because that is
the part it is genuinely good at. It may not:

  * name a document that is not in the library (`resolve` drops those; the
    library is the ground truth about what the company holds, not the model);
  * assert coverage without a page (invariant 1);
  * decide whether a document is still good on the submission date, which is
    arithmetic and belongs to `validity.assess` (invariant 2);
  * resolve its own ambiguity — two candidates for one obligation is a fact
    about the evidence, and it is reported rather than picked from.

UNCERTAINTY PROPAGATES, IT DOES NOT RESET

An obligation extracted from a page whose text is stored as images is itself
unverified (`obligations.anchored`). Nothing matched against it can be more
certain than it is, so those rows are NEEDS_REVIEW whatever the library holds.
A pipeline that lets confidence recover at each step ends up confident about
nothing in particular.

ABSENCE IS NOT ALWAYS MISSING

Two findings from the real files, both making MISSING the wrong default:

  * conditional obligations — "l'attestation de l'Administration fiscale **en
    cas de** non-assujettissement à la TVA" does not apply to most bidders.
    Reporting it missing is noise, and noise is how a report stops being read.
  * obligations with alternatives — "attestations du destinataire ou, à défaut,
    une déclaration de l'opérateur économique. Ou PARTIE IV C 1b) du DUME."
    Finding nothing on one route says nothing about the other two.

Both become NEEDS_REVIEW with a reason. Only a plain, unconditional, single-route
obligation with nothing to answer it is reported MISSING.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from tender_compliance.coverage import Citation, Row, Status
from tender_compliance.obligations import Obligation
from tender_compliance.validity import Document, Requirement, Validity, assess


@dataclass(frozen=True)
class Suggestion:
    """What the model offers for one obligation. Unverified by construction."""

    document: str
    """Must name a document in the library, verbatim. Anything else is dropped."""

    page: int | None = None
    """Where in that document the point is proven. Absent means the row cannot
    be COVERED — see invariant 1."""

    reason: str = ""


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
    """Why this document, or why nothing — in one sentence, for the reader who
    disagrees and wants somewhere to start."""


def _by_name(library: list[Document]) -> dict[str, Document]:
    return {document.name: document for document in library}


def resolve(
    obligation: Obligation,
    suggestions: list[Suggestion],
    library: list[Document],
) -> Match:
    """Decide what the evidence supports. No model runs here.

    This is the function that must never be wrong, which is why it is separate
    from whatever produced the suggestions.
    """
    known = _by_name(library)

    # The library is the ground truth about what the company holds. A model
    # naming a document that is not in it has invented the document, and that
    # is the failure this whole module exists to make impossible.
    usable = [s for s in suggestions if s.document in known]
    invented = len(suggestions) - len(usable)

    if not usable:
        return _nothing_found(obligation, invented)

    distinct = {s.document for s in usable}
    if len(distinct) > 1:
        return Match(
            obligation, None, None, certain=False,
            reason=(
                f"{len(distinct)} documents could answer this "
                f"({', '.join(sorted(distinct))}) — which one is a decision for "
                f"the bidder, not for the tool"
            ),
        )

    best = usable[0]
    document = known[best.document]

    if best.page is None or best.page < 1:
        return Match(
            obligation, document, None, certain=False,
            reason=(
                f"{document.name} looks like the answer, but no page was given — "
                f"a claim that cannot be shown to the buyer is not a claim"
            ),
        )

    citation = Citation(document=document.name, page=best.page)

    if not obligation.anchored:
        # The obligation itself could not be located in the tender text.
        return Match(
            obligation, document, citation, certain=False,
            reason=(
                f"{document.name} would answer this, but the requirement itself "
                f"could not be verified against the tender text"
            ),
        )

    return Match(
        obligation, document, citation, certain=True,
        reason=best.reason or f"answered by {document.name}",
    )


def _nothing_found(obligation: Obligation, invented: int) -> Match:
    """Nothing in the library was proposed — which is not always MISSING."""
    if not obligation.anchored:
        reason = ("nothing found, and the requirement itself could not be "
                  "verified against the tender text")
    elif obligation.conditional:
        reason = ("nothing found, but this requirement applies only in a stated "
                  "case — check whether it concerns this bidder at all")
    elif obligation.has_alternatives:
        reason = ("nothing found on this route, but the tender allows more than "
                  "one way to satisfy it")
    else:
        reason = "nothing in the library answers this"
        if invented:
            reason += f" ({invented} suggested document(s) are not in the library)"
        return Match(obligation, None, None, certain=True, reason=reason)

    return Match(obligation, None, None, certain=False, reason=reason)


# How a date verdict becomes a matrix status. Written as a table because the
# mapping is a decision, and a decision buried in an if-chain is a decision
# nobody re-reads.
_STATUS_FOR = {
    Validity.VALID: Status.COVERED,
    Validity.EXPIRES_BEFORE_DEADLINE: Status.EXPIRED,
    Validity.EXPIRED: Status.EXPIRED,
    Validity.TOO_OLD: Status.EXPIRED,
    Validity.UNKNOWN: Status.NEEDS_REVIEW,
}

_DATE_NOTE = {
    Validity.EXPIRES_BEFORE_DEADLINE: "valid today, expired on the submission date",
    Validity.EXPIRED: "already out of date",
    Validity.TOO_OLD: "valid, but older than the buyer accepts",
    Validity.UNKNOWN: "no usable date on the document",
}


def to_row(match: Match, deadline: date, *, today: date) -> Row:
    """Turn a match into a matrix row, applying the date rules by arithmetic.

    Invariant 2 lives here: the matcher said *which* document, this says whether
    it still counts, and the model is nowhere near the second question.
    """
    obligation = match.obligation
    base = dict(
        requirement=obligation.text,
        source=obligation.source,
        stage=obligation.stage,
    )

    if match.document is None:
        status = Status.MISSING if match.certain else Status.NEEDS_REVIEW
        return Row(**base, status=status, evidence=None, note=match.reason)

    verdict = assess(
        match.document,
        deadline,
        today=today,
        requirement=Requirement(max_age_months=obligation.max_age_months),
    )
    status = _STATUS_FOR[verdict]
    note = _DATE_NOTE.get(verdict, match.reason)

    # A document that is fine on the dates still cannot carry a COVERED row when
    # the match itself is uncertain. Downgrading here rather than earlier keeps
    # the date verdict visible: the reader learns both what was found and why it
    # is not being asserted.
    if status is Status.COVERED and not match.certain:
        return Row(**base, status=Status.NEEDS_REVIEW,
                   evidence=match.citation, note=match.reason)

    # An EXPIRED row keeps its citation: the remedy is renewing that document,
    # and the reader needs to know which one.
    evidence = match.citation if status is not Status.MISSING else None
    return Row(**base, status=status, evidence=evidence, note=note)


Propose = Callable[[Obligation, list[Document]], list[Suggestion]]
"""How suggestions are obtained. Injected for the same reason as in
`obligations.py`: the deciding logic must be testable with no model, key or
network, and the model must be replaceable without touching it."""


def find(obligation: Obligation, library: list[Document], propose: Propose) -> Match:
    """Look for the document that answers one obligation."""
    return resolve(obligation, propose(obligation, library), library)


def build(
    obligations: list[Obligation],
    library: list[Document],
    deadline: date,
    *,
    today: date,
    propose: Propose,
) -> list[Row]:
    """The compliance matrix for one tender against one evidence library."""
    return [
        to_row(find(obligation, library, propose), deadline, today=today)
        for obligation in obligations
    ]
