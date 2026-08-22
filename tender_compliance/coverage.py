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
    BID = "bid"
    PERFORMANCE = "performance"


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
    stage: Stage = Stage.BID
    evidence: Citation | None = None
    """Where the answer was found. `None` for MISSING — and required for
    COVERED, which `check()` enforces."""

    note: str = ""


@dataclass(frozen=True)
class Measurement:
    """The counted state of a matrix. Every field is derived, none is asserted."""

    total: int
    counts: dict[Status, int]
    blocking: int
    performance_total: int = 0

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
        return " · ".join(parts)


def measure(rows: list[Row]) -> Measurement:
    """Count the matrix. No model, no estimate, no rounding."""
    bid = [row for row in rows if row.stage is Stage.BID]
    counts = Counter(row.status for row in bid)
    return Measurement(
        total=len(bid),
        counts=dict(counts),
        # Everything that is not COVERED blocks — NEEDS_REVIEW included. It is
        # not known to be a problem, which is exactly why it must be settled
        # before the deadline rather than after it.
        blocking=sum(n for status, n in counts.items() if status is not Status.COVERED),
        performance_total=len(rows) - len(bid),
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
