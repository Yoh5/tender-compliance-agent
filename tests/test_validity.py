"""The date arithmetic, checked against the cases that lose tenders.

The demo of this project rests on one moment: an attestation that is valid
today and expired on the day the bid is due. Every test below exists so that
moment cannot quietly stop working.

Note what is *not* tested here: no language model, no network, no fixture
files. This module is arithmetic, and arithmetic is the part a jury — or a
bidder — must be able to check by hand.
"""

from datetime import date

import pytest

from tender_compliance.validity import (
    Document,
    Requirement,
    Validity,
    assess,
    blocking,
    days_of_slack,
)

DEADLINE = date(2026, 9, 14)
TODAY = date(2026, 8, 23)


def test_a_document_valid_past_the_deadline_is_valid():
    doc = Document("Insurance attestation", expires_on=date(2026, 12, 31))
    assert assess(doc, DEADLINE, today=TODAY) is Validity.VALID


def test_the_case_this_project_exists_for():
    # Valid today. Not on the day the bid is due. A human reading the folder
    # sees a valid attestation — because it *is* valid, on the day they read it.
    doc = Document("Insurance attestation", expires_on=date(2026, 9, 3))
    assert assess(doc, DEADLINE, today=TODAY) is Validity.EXPIRES_BEFORE_DEADLINE


def test_an_already_expired_document_is_not_confused_with_the_previous_case():
    # Both are failures, but not the same conversation: one is "renew before
    # the 14th", the other is "you have been bidding with this for a month".
    doc = Document("Insurance attestation", expires_on=date(2026, 7, 1))
    assert assess(doc, DEADLINE, today=TODAY) is Validity.EXPIRED


def test_expiry_on_the_deadline_itself_still_counts():
    # "Valable jusqu'au 14/09" is valid on the 14th. Off by one here flips a
    # verdict on every document that expires the day of the submission.
    doc = Document("Insurance attestation", expires_on=DEADLINE)
    assert assess(doc, DEADLINE, today=TODAY) is Validity.VALID


def test_a_missing_expiry_is_never_reported_as_valid():
    # The failure this module refuses. A date we could not read is not a date
    # that does not exist.
    doc = Document("Insurance attestation", expires_on=None)
    assert assess(doc, DEADLINE, today=TODAY) is Validity.UNKNOWN


def test_a_document_that_genuinely_never_expires_is_valid():
    # A Kbis extract carries no expiry. Reporting it UNKNOWN forever would
    # train the reader to ignore the status column — which is how a real
    # expiry gets missed.
    doc = Document("Kbis extract", has_expiry=False)
    assert assess(doc, DEADLINE, today=TODAY) is Validity.VALID


class TestMaximumAge:
    """"Attestation de moins de 6 mois" — a different rule from expiry."""

    REQUIREMENT = Requirement(max_age_months=6)

    def test_a_recent_document_passes(self):
        doc = Document("Tax clearance", issued_on=date(2026, 7, 1), has_expiry=False)
        assert assess(doc, DEADLINE, today=TODAY, requirement=self.REQUIREMENT) is Validity.VALID

    def test_an_old_one_is_refused_even_though_it_never_expires(self):
        # Perfectly valid, and still rejected. Expiry alone would call this
        # VALID and the bidder would find out at the opening.
        doc = Document("Tax clearance", issued_on=date(2025, 11, 1), has_expiry=False)
        assert assess(doc, DEADLINE, today=TODAY, requirement=self.REQUIREMENT) is Validity.TOO_OLD

    def test_the_age_is_counted_from_the_deadline_not_from_today(self):
        # Issued 2026-03-15. Six months before the deadline is 2026-03-14, so
        # it passes — but six months before *today* is 2026-02-23, which would
        # also pass. The discriminating case is the other way round: a document
        # that is young enough now and too old by the deadline.
        doc = Document("Tax clearance", issued_on=date(2026, 3, 1), has_expiry=False)
        assert assess(doc, DEADLINE, today=TODAY, requirement=self.REQUIREMENT) is Validity.TOO_OLD
        assert assess(doc, date(2026, 8, 25), today=TODAY, requirement=self.REQUIREMENT) is Validity.VALID

    def test_without_an_issue_date_nothing_is_asserted(self):
        doc = Document("Tax clearance", issued_on=None, has_expiry=False)
        assert assess(doc, DEADLINE, today=TODAY, requirement=self.REQUIREMENT) is Validity.UNKNOWN

    def test_age_is_checked_before_expiry(self):
        # Inside its own validity, past the buyer's age limit. Checking expiry
        # first would return VALID and hide the real problem.
        doc = Document(
            "Tax clearance", issued_on=date(2025, 1, 1), expires_on=date(2027, 1, 1)
        )
        assert assess(doc, DEADLINE, today=TODAY, requirement=self.REQUIREMENT) is Validity.TOO_OLD


class TestMonthArithmetic:
    """Month subtraction has to land on a real calendar day."""

    def test_three_months_before_the_31st_lands_in_february(self):
        # 3 months before 31 May 2026 is 28 February, not 31 February.
        doc = Document("Tax clearance", issued_on=date(2026, 2, 28), has_expiry=False)
        deadline = date(2026, 5, 31)
        assert assess(doc, deadline, today=TODAY, requirement=Requirement(3)) is Validity.VALID

        older = Document("Tax clearance", issued_on=date(2026, 2, 27), has_expiry=False)
        assert assess(older, deadline, today=TODAY, requirement=Requirement(3)) is Validity.TOO_OLD

    def test_it_crosses_years(self):
        doc = Document("Tax clearance", issued_on=date(2025, 10, 1), has_expiry=False)
        assert assess(doc, date(2026, 2, 1), today=TODAY, requirement=Requirement(6)) is Validity.VALID

    def test_a_twelve_month_limit_is_exactly_one_year(self):
        doc = Document("Tax clearance", issued_on=date(2025, 9, 14), has_expiry=False)
        assert assess(doc, DEADLINE, today=TODAY, requirement=Requirement(12)) is Validity.VALID
        older = Document("Tax clearance", issued_on=date(2025, 9, 13), has_expiry=False)
        assert assess(older, DEADLINE, today=TODAY, requirement=Requirement(12)) is Validity.TOO_OLD


class TestSlack:
    """The number of days is what makes a finding actionable."""

    def test_a_negative_number_means_it_expires_first(self):
        doc = Document("Insurance", expires_on=date(2026, 9, 3))
        assert days_of_slack(doc, DEADLINE) == -11

    def test_a_positive_number_is_room_to_spare(self):
        doc = Document("Insurance", expires_on=date(2026, 10, 14))
        assert days_of_slack(doc, DEADLINE) == 30

    def test_no_expiry_means_no_number_rather_than_zero(self):
        # Zero would read as "expires exactly on the deadline" — the tensest
        # possible situation — for a document that has no expiry at all.
        assert days_of_slack(Document("Kbis", has_expiry=False), DEADLINE) is None
        assert days_of_slack(Document("Insurance", expires_on=None), DEADLINE) is None


class TestBlocking:
    def test_only_valid_is_not_blocking(self):
        assert not blocking(Validity.VALID)
        for verdict in Validity:
            if verdict is not Validity.VALID:
                assert blocking(verdict), verdict

    def test_unknown_blocks(self):
        # Not known to be a problem — which is exactly why it has to be looked
        # at before the deadline rather than discovered after it.
        assert blocking(Validity.UNKNOWN)


def test_the_verdict_never_depends_on_the_wall_clock():
    # `today` is a parameter, not a call to `date.today()`. A report that says
    # something different depending on when it was run cannot be checked, and
    # the case that matters — the day before an expiry — could not be tested
    # at all.
    doc = Document("Insurance", expires_on=date(2026, 9, 3))
    assert assess(doc, DEADLINE, today=date(2026, 9, 2)) is Validity.EXPIRES_BEFORE_DEADLINE
    assert assess(doc, DEADLINE, today=date(2026, 9, 4)) is Validity.EXPIRED


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
