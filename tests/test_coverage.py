"""The matrix counts what it says it counts.

Two properties are worth more than all the rest here:

  · the headline is derived from the rows, never asserted — so it cannot say
    "31 covered" over a matrix holding 30;
  · performance obligations stay out of the admissibility count — mixing them
    inflates "missing" with items that block nothing, and a reader who catches
    that once stops trusting every number on the page.
"""

import pytest

from tender_compliance.coverage import (
    Citation,
    Measurement,
    Row,
    Stage,
    Status,
    check,
    measure,
    ordered,
)

PACK = Citation("RC.pdf", 4)


def row(status: Status, *, stage: Stage = Stage.BID, evidence: Citation | None = None) -> Row:
    if status is Status.COVERED and evidence is None:
        evidence = Citation("attestation.pdf", 1)
    return Row("A requirement", PACK, status, stage, evidence)


class TestCounting:
    def test_the_headline_is_derived_from_the_rows(self):
        rows = [row(Status.COVERED)] * 31 + [row(Status.MISSING)] * 9
        result = measure(rows)
        assert result.total == 40
        assert result.counts[Status.COVERED] == 31
        assert "31 covered" in result.headline
        assert "9 missing" in result.headline

    def test_a_status_with_no_rows_is_left_out_of_the_headline(self):
        # "0 expired before the deadline" reads as a finding. Absence of a
        # problem should not occupy the same space as a problem.
        result = measure([row(Status.COVERED)] * 3)
        assert "expired" not in result.headline
        assert "review" not in result.headline

    def test_everything_that_is_not_covered_blocks(self):
        rows = [
            row(Status.COVERED),
            row(Status.MISSING),
            row(Status.EXPIRED),
            row(Status.NEEDS_REVIEW),
        ]
        assert measure(rows).blocking == 3

    def test_an_empty_matrix_does_not_crash_and_claims_nothing(self):
        result = measure([])
        assert result.total == 0
        assert result.blocking == 0
        assert result.headline == "0 obligations"


class TestBidVersusPerformance:
    """The distinction that decides whether the report is believable."""

    def test_performance_obligations_stay_out_of_the_count(self):
        rows = [
            row(Status.COVERED),
            row(Status.MISSING, stage=Stage.PERFORMANCE),
            row(Status.MISSING, stage=Stage.PERFORMANCE),
        ]
        result = measure(rows)
        # Two missing items — neither of which stops the envelope being opened.
        assert result.total == 1
        assert result.blocking == 0
        assert result.performance_total == 2

    def test_they_are_reported_rather_than_dropped(self):
        # They matter for pricing and for the offer. Silently discarding them
        # would trade one wrong report for another.
        result = measure([row(Status.MISSING, stage=Stage.PERFORMANCE)])
        assert result.performance_total == 1


class TestOrdering:
    def test_blockers_come_first(self):
        rows = [
            row(Status.COVERED),
            row(Status.NEEDS_REVIEW),
            row(Status.MISSING),
            row(Status.EXPIRED),
        ]
        assert [r.status for r in ordered(rows)] == [
            Status.MISSING,
            Status.EXPIRED,
            Status.NEEDS_REVIEW,
            Status.COVERED,
        ]

    def test_equal_severity_keeps_the_order_of_the_tender_pack(self):
        # So the reader can follow the document rather than hunt through it.
        first = Row("first", Citation("RC.pdf", 2), Status.MISSING)
        second = Row("second", Citation("RC.pdf", 9), Status.MISSING)
        assert [r.requirement for r in ordered([first, second])] == ["first", "second"]


class TestStructuralChecks:
    """Validation of the report, not of the tender."""

    def test_covered_without_a_citation_is_refused(self):
        # The one thing the tool promises never to do: assert what it cannot
        # show. Better a loud failure here than a printed claim.
        bad = Row("A requirement", PACK, Status.COVERED, evidence=None)
        problems = check([bad])
        assert len(problems) == 1
        assert "needs review" in problems[0]

    def test_missing_while_citing_evidence_is_refused(self):
        bad = Row("A requirement", PACK, Status.MISSING, evidence=Citation("x.pdf", 1))
        assert len(check([bad])) == 1

    def test_a_page_number_below_one_is_refused(self):
        # A zero page is the signature of a 0-based index leaking out of a PDF
        # reader. Every citation in the report would then be off by one, which
        # is worse than no citation: it looks checkable and is not.
        bad = Row("A requirement", Citation("RC.pdf", 0), Status.MISSING)
        assert len(check([bad])) == 1

    def test_a_sound_matrix_reports_nothing(self):
        assert check([row(Status.COVERED), row(Status.MISSING)]) == []


def test_the_measurement_holds_no_number_it_was_told():
    # Every field of `Measurement` is computed from the rows. If one were ever
    # passed in, a caller could hand it a total that does not match its own
    # matrix — and that is the number everyone repeats.
    rows = [row(Status.COVERED), row(Status.MISSING)]
    result = measure(rows)
    assert result.total == len(rows)
    assert sum(result.counts.values()) == result.total
    assert isinstance(result, Measurement)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
