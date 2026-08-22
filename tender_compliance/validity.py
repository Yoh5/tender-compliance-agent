"""Is this document still good on the day the bid is submitted?

WHY THIS IS CODE AND NOT A PROMPT

This is the module the whole project is built around, and it contains no
language model on purpose.

A tender is lost when an insurance attestation expires eleven days before the
submission date. Nobody catches that by reading: the expiry sits on page 3 of
one document, the deadline sits on page 1 of another, and the gap between them
is arithmetic. A model asked to do that arithmetic will usually get it right —
and when it gets it wrong, the answer looks exactly like the answer it gets
right. There is no tell.

So dates are computed here, by code that can be checked by hand, and the model
is never asked whether something is still valid. It may only tell us what the
document *says* — the dates it carries. What follows from those dates is not
its business.

THE QUESTION IS NOT "IS IT VALID TODAY"

That is the mistake this module exists to prevent. A certificate valid today
and expiring in three weeks is worthless for a bid due in five. The reference
date is always the submission deadline, never today — and the two differ
exactly in the cases that cost the tender.

TWO RULES, OFTEN BOTH AT ONCE

French tender packs mix two different requirements, and they are not the same
check:

  · an EXPIRY — "valid until 31/12" — the document stops being good on a date
    it carries itself;
  · a MAXIMUM AGE — "attestation de moins de 6 mois" — the document never
    expires, but the buyer refuses it past a certain age.

A document can satisfy one and fail the other. Both are evaluated.

SILENCE IS NOT A PASS

A document with no expiry date can mean two very different things: it genuinely
never expires (a Kbis extract does not, a diploma does not), or we failed to
read the date. Treating the second as the first would let an expired attestation
through in silence — the exact failure this tool is supposed to prevent. So the
caller must say whether the document type carries an expiry at all, and when
that is unknown, the verdict is UNKNOWN, never VALID.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class Validity(str, Enum):
    """The verdict on one document against one deadline.

    Deliberately not a boolean. "Valid / not valid" would collapse four
    situations that call for four different actions: do nothing, renew before
    the deadline, renew now, or go and look at the document.
    """

    VALID = "valid"
    """Good on the submission date. Nothing to do."""

    EXPIRES_BEFORE_DEADLINE = "expires_before_deadline"
    """Good today, not on the submission date. This is the one that loses
    tenders, and the one a human reader never catches."""

    EXPIRED = "expired"
    """Already out of date. Obvious once seen — but nobody re-reads a folder of
    forty attestations before every bid."""

    TOO_OLD = "too_old"
    """Within its own validity, but older than the buyer accepts. A document
    that is perfectly valid and still refused."""

    UNKNOWN = "unknown"
    """No usable date. Not a pass, not a failure: something to go and look at.
    Reporting this as VALID is the failure mode this module refuses."""


# A document expiring ON the submission date is accepted. French attestations
# are written "valable jusqu'au X" and X is inclusive — the last day counts.
# Fixed here rather than left to each caller: an inclusive/exclusive boundary
# decided in three places will eventually be decided differently in one of them.
EXPIRY_IS_INCLUSIVE = True


@dataclass(frozen=True)
class Document:
    """One piece of evidence from the company's library.

    `expires_on` is `None` for two opposite reasons — the document has no
    expiry, or we could not read one. `has_expiry` separates them, and nothing
    else can: that is why it is a required field rather than an inference.
    """

    name: str
    issued_on: date | None = None
    expires_on: date | None = None
    has_expiry: bool = True
    """False only for document types that genuinely never expire (a Kbis
    extract, a diploma). Leave it True whenever there is any doubt: the cost of
    a needless review is a glance, the cost of a missed expiry is the tender."""


@dataclass(frozen=True)
class Requirement:
    """What the tender pack asks of that document."""

    max_age_months: int | None = None
    """"Attestation de moins de 6 mois" → 6. `None` when the buyer sets no age
    limit."""


def _months_before(reference: date, months: int) -> date:
    """The date `months` before `reference`, clamped to a real calendar day.

    Written out rather than pulled from `dateutil` so the project keeps one
    fewer dependency, and so the clamping rule is visible: three months before
    31 May is 28 (or 29) February, not 31 February. Getting this wrong shifts a
    boundary by up to three days — enough to flip a verdict on a document
    issued near the limit.
    """
    total = reference.month - 1 - months
    year = reference.year + total // 12
    month = total % 12 + 1
    day = min(reference.day, _days_in_month(year, month))
    return date(year, month, day)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year + month // 12, month % 12 + 1, 1) - date(year, month, 1)).days


def assess(
    document: Document,
    deadline: date,
    *,
    today: date,
    requirement: Requirement | None = None,
) -> Validity:
    """The verdict for one document against one submission deadline.

    `today` is passed in rather than read from the clock. A function that reads
    the clock cannot be tested against the case that matters — the day before
    an expiry — and a report that changes depending on when it was run is a
    report nobody can check.
    """
    requirement = requirement or Requirement()

    # Age is checked first: a document can be inside its own validity and still
    # be refused for being too old. Reporting VALID here would send the bidder
    # to the submission with a document the buyer will reject.
    if requirement.max_age_months is not None:
        if document.issued_on is None:
            return Validity.UNKNOWN
        oldest_accepted = _months_before(deadline, requirement.max_age_months)
        if document.issued_on < oldest_accepted:
            return Validity.TOO_OLD

    if not document.has_expiry:
        return Validity.VALID

    if document.expires_on is None:
        return Validity.UNKNOWN

    if _is_past(document.expires_on, today):
        return Validity.EXPIRED

    if _is_past(document.expires_on, deadline):
        return Validity.EXPIRES_BEFORE_DEADLINE

    return Validity.VALID


def _is_past(expiry: date, reference: date) -> bool:
    """Has `expiry` gone by, as of `reference`?"""
    return expiry < reference if EXPIRY_IS_INCLUSIVE else expiry <= reference


def days_of_slack(document: Document, deadline: date) -> int | None:
    """How many days the document has left after the deadline, or `None`.

    Negative means it expires before the bid is due — and the magnitude is what
    makes the finding actionable: minus three days is a phone call, minus ninety
    is a renewal to start today. A status alone does not carry that.
    """
    if not document.has_expiry or document.expires_on is None:
        return None
    return (document.expires_on - deadline).days


def blocking(verdict: Validity) -> bool:
    """Would this stop the bid from being accepted?

    UNKNOWN counts as blocking. It is not known to be a problem — which is
    precisely why it must be looked at before the deadline rather than
    discovered after it.
    """
    return verdict is not Validity.VALID
