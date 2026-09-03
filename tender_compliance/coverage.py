"""The compliance matrix, and the numbers on it.

WHY THE MODEL NEVER COUNTS

"31 of 47 obligations covered" is the first thing anyone reads, and it is the
one number they will repeat to their manager. Asking a language model to
produce it would be asking it to count a list it has already been given — a
task it performs well enough to be trusted and badly enough to be wrong, with
no way to tell the two apart from the answer alone.

So the model's job ends at proposing a status for each row. The totals, the
headline, and the ordering are computed here, from the rows themselves. Anyone
can recount by hand, which is the only reason to believe the number.

WHAT BELONGS IN THE COUNT — THE DISTINCTION THAT MAKES OR BREAKS THE REPORT

A tender pack states two kinds of obligation, and mixing them ruins the tool:

  · BID-STAGE — what must be in the envelope on the submission date. A gap here
    means rejection.
  · PERFORMANCE — what the winner commits to *during* the contract: a named
    project manager, monthly reporting, an on-site response time. A gap here
    means nothing on submission day.

They read almost identically in the source text — both are "the holder shall" —
and an extractor that cannot tell them apart produces a report claiming twenty
missing items when three are actually blocking. The reader then stops trusting
the count, which costs more than not having it.

The headline therefore counts BID-STAGE only. Performance obligations are
reported, never mixed in: they matter for pricing and for the offer, just not
for admissibility.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum


class Status(str, Enum):
    """Where one obligation stands.

    Four values rather than a boolean, for the same reason as `Validity`: they
    call for four different actions, and collapsing them would hide which one.
    """

    COVERED = "covered"
    """Met, with a document cited by page."""

    MISSING = "missing"
    """Nothing in the evidence library answers this."""

    EXPIRED = "expired"
    """A document answers it, but will not be valid on the submission date.
    Kept apart from MISSING because the remedy is different — renewing beats
    producing from nothing, and it is usually possible in the time left."""

    NEEDS_REVIEW = "needs_review"
    """Something was matched, but not firmly enough to assert. This is where
    every uncertain match lands: the tool does not get to guess in the
    direction that flatters the report."""


class Stage(str, Enum):
    """When a piece is due — and, for the two bid-time values, what it costs.

    BID was one value until two real files showed it was two. Both are due
    before the deadline, so both block; they do not block the same way.
    """

    CANDIDATURE = "candidature"
    """Due to apply at all. "Les candidatures incomplètes ou demeurées
    incomplètes à la suite d'une demande de compléments sont éliminées"
    (ANTAI IV.9, DGAC 5.8). Missing one ends the bid."""

    OFFER = "offer"
    """Part of the offer itself — acte d'engagement, mémoire technique, RIB.
    "L'acheteur peut autoriser tous les soumissionnaires concernés à régulariser
    les offres irrégulières dans un délai approprié" (DGAC 6.2). Missing one is
    serious and usually recoverable, which is not the same thing."""

    PERFORMANCE = "performance"
    """Owed after award, by the holder of the contract. Not a bid blocker."""


# Display order: what blocks the bid first, what is merely uncertain last.
# A matrix sorted by page number buries the four rows that matter among forty
# that do not.
SEVERITY = {
    Status.MISSING: 0,
    Status.EXPIRED: 1,
    Status.NEEDS_REVIEW: 2,
    Status.COVERED: 3,
}


@dataclass(frozen=True)
class Citation:
    """Where an assertion comes from. Both sides of the matrix carry one.

    A row without a citation is a row nobody can defend in front of the buyer,
    which is the same as not having it.
    """

    document: str
    page: int


@dataclass(frozen=True)
class Row:
    """One obligation, and what answers it."""

    requirement: str
    source: Citation
    """Where the tender pack states it."""

    status: Status
    stage: Stage = Stage.CANDIDATURE
    evidence: Citation | None = None
    """Where the answer was found. `None` for MISSING — and required for
    COVERED, which `check()` enforces."""

    note: str = ""

    points: str = ""
    """What this row earns or forgoes on the buyer's grid ("2/2").

    Empty for the ordinary case — most requirements are pass/fail, and printing
    a grade where the buyer stated none would invent one."""

    gloss: str = ""
    """The requirement in English, for a reader who does not read French.

    Decoration, and deliberately last: it is written after every verdict exists,
    it is shown beside the quotation and never instead of it, and nothing in
    this package reads it. `english.attach` is the only writer. Empty whenever
    the translation did not arrive, which the report treats as ordinary.
    """

    slack: int | None = None
    """Days between the evidence expiring and bids being due. Negative means it
    lapses first.

    Carried on the row rather than recomputed by whoever renders it: a report
    and a summary that each work it out will eventually work it out differently.
    None when the document has no readable expiry, which is not the same as
    zero."""


@dataclass(frozen=True)
class Measurement:
    """The counted state of a matrix. Every field is derived, none is asserted."""

    total: int
    counts: dict[Status, int]
    blocking: int
    performance_total: int = 0

    fatal: int = 0
    """Open rows in the candidature pile. These end the bid.

    Split out from `blocking` because the two need different reactions on
    different days, and a single number told the reader to treat them alike."""

    regularisable: int = 0
    """Open rows in the offer pile. Serious, and usually recoverable — the buyer
    may invite a correction (DGAC 6.2). Never presented as harmless: the
    invitation is the buyer's option, not the bidder's right."""

    @property
    def headline(self) -> str:
        """The one line that gets repeated. Built here so it cannot drift from
        the numbers it summarises — two places building this sentence would
        eventually build it differently."""
        parts = [f"{self.total} obligations"]
        for status, label in (
            (Status.COVERED, "covered"),
            (Status.MISSING, "missing"),
            (Status.EXPIRED, "expired before the deadline"),
            (Status.NEEDS_REVIEW, "to review"),
        ):
            count = self.counts.get(status, 0)
            if count:
                parts.append(f"{count} {label}")
        if self.fatal:
            parts.append(f"{self.fatal} of them fatal to the candidature")
        return " · ".join(parts)


def measure(rows: list[Row]) -> Measurement:
    """Count the matrix. No model, no estimate, no rounding."""
    avant = [row for row in rows if row.stage is not Stage.PERFORMANCE]
    counts = Counter(row.status for row in avant)

    def ouvert(row: Row) -> bool:
        # NEEDS_REVIEW counts as open. It is not known to be a problem, which is
        # exactly why it has to be settled before the deadline rather than after.
        return row.status is not Status.COVERED

    return Measurement(
        total=len(avant),
        counts=dict(counts),
        blocking=sum(n for status, n in counts.items() if status is not Status.COVERED),
        performance_total=len(rows) - len(avant),
        fatal=sum(1 for row in avant
                  if ouvert(row) and row.stage is Stage.CANDIDATURE),
        regularisable=sum(1 for row in avant
                          if ouvert(row) and row.stage is Stage.OFFER),
    )


def ordered(rows: list[Row]) -> list[Row]:
    """The matrix as it should be read: blockers first.

    Ties keep their original order, so two rows of equal severity still appear
    in the order the tender pack states them — the reader can follow the
    document.
    """
    return sorted(rows, key=lambda row: SEVERITY[row.status])


def check(rows: list[Row]) -> list[str]:
    """Structural problems in the matrix itself, as plain sentences.

    Not validation of the tender — validation of the *report*. A row that
    claims COVERED without naming a page is not a small formatting issue: it is
    the tool asserting something it cannot show, which is the one thing it
    promises never to do. Better to fail loudly here than to print it.
    """
    problems: list[str] = []
    for index, row in enumerate(rows):
        if row.status is Status.COVERED and row.evidence is None:
            problems.append(
                f"row {index} ({row.requirement[:60]!r}) is marked covered but cites "
                f"no evidence — a claim that cannot be shown must be 'needs review'"
            )
        if row.status is Status.MISSING and row.evidence is not None:
            problems.append(
                f"row {index} ({row.requirement[:60]!r}) is marked missing yet cites "
                f"evidence — one of the two is wrong"
            )
        if row.source.page < 1:
            problems.append(
                f"row {index} ({row.requirement[:60]!r}) cites page {row.source.page} "
                f"of the tender pack — pages are 1-based"
            )
    return problems
