"""Quantified requirements, tested against the wording that produced them.

Every case below traces to a sentence in `samples/real_requirements.json`,
quoted from a published notice. That is deliberate: the module exists because
reading real material showed the original design could not answer this family
of obligations at all, and the tests should keep pointing at the evidence.
"""

import pytest

from tender_compliance.capacity import (
    Aggregation,
    Assessment,
    Measure,
    Profile,
    Threshold,
    assess,
)
from tender_compliance.coverage import Status

# "si x est strictement supérieur à 3 124 998 d'euros HT : 2/2"
#                                 — Ministère de l'éducation nationale, 22-87951
TURNOVER = Threshold(
    measure=Measure.TURNOVER,
    minimum=3_124_998,
    window_years=3,
    aggregation=Aggregation.AVERAGE,
    strict=True,
    points_if_met="2/2",
)

# "si x est supérieur ou égal à 4: 2/2" over "les cinq (5) dernières années"
REFERENCES = Threshold(
    measure=Measure.REFERENCES, minimum=4, window_years=5,
    aggregation=Aggregation.TOTAL, strict=False, points_if_met="2/2",
)


class TestTurnover:
    def test_a_company_above_the_threshold_is_covered(self):
        profile = Profile(turnover_by_year=[3_400_000, 3_300_000, 3_200_000])
        result = assess(TURNOVER, profile)
        assert result.status is Status.COVERED
        assert "2/2" in result.explanation

    def test_a_company_below_it_is_told_by_how_much(self):
        # "You are short" sends someone into the accounts. A figure tells them
        # whether adding a subcontractor's turnover would close the gap.
        profile = Profile(turnover_by_year=[2_390_000, 2_140_000, 1_850_000])
        result = assess(TURNOVER, profile)
        assert result.status is Status.MISSING
        assert "short by" in result.explanation
        assert result.measured == pytest.approx(2_126_666.67, abs=1)

    def test_strictly_greater_means_strictly(self):
        # The boundary is where a bidder actually sits: buyers often set the
        # threshold from the incumbent's figures.
        exact = Profile(turnover_by_year=[3_124_998] * 3)
        assert assess(TURNOVER, exact).status is Status.MISSING

        lenient = Threshold(Measure.TURNOVER, 3_124_998, 3, Aggregation.AVERAGE, strict=False)
        assert assess(lenient, exact).status is Status.COVERED

    def test_the_average_is_over_the_window_not_the_whole_history(self):
        # A strong fourth year does not rescue three weak ones when the buyer
        # asked for three.
        profile = Profile(turnover_by_year=[2_000_000, 2_000_000, 2_000_000, 99_000_000])
        assert assess(TURNOVER, profile).status is Status.MISSING

    def test_each_year_is_a_harder_test_than_the_average(self):
        # Some buyers write it that way, and the difference is material: one bad
        # year sinks a company the average would have carried.
        profile = Profile(turnover_by_year=[5_000_000, 3_000_000, 2_000_000])
        assert assess(TURNOVER, profile).status is Status.COVERED

        each = Threshold(Measure.TURNOVER, 3_124_998, 3, Aggregation.EACH, strict=True)
        assert assess(each, profile).status is Status.MISSING


class TestTheYoungCompanyPath:
    """"Pour les candidats dans l'impossibilité, à raison de leur création
    récente…" — Ville de Paris, 22-88307."""

    def test_fewer_years_than_the_window_is_not_a_failure(self):
        # Buyers write an escape route because refusing young firms outright is
        # not what they want. MISSING here would cost a bid that was winnable.
        profile = Profile(turnover_by_year=[4_000_000, 3_800_000])
        result = assess(TURNOVER, profile)
        assert result.status is Status.NEEDS_REVIEW
        assert "recently" in result.explanation or "created" in result.explanation

    def test_it_applies_even_when_the_figures_are_strong(self):
        # The point is that the requirement cannot be evaluated as written, not
        # that the company is weak.
        profile = Profile(turnover_by_year=[50_000_000])
        assert assess(TURNOVER, profile).status is Status.NEEDS_REVIEW

    def test_and_the_measured_figure_is_still_reported(self):
        # So a human can see immediately that the alternative path is worth
        # taking rather than opening the accounts.
        profile = Profile(turnover_by_year=[4_000_000, 3_800_000])
        assert assess(TURNOVER, profile).measured == pytest.approx(3_900_000)


class TestMissingData:
    def test_no_figures_at_all_is_never_reported_as_a_shortfall(self):
        # Same rule as a missing expiry date in validity.py: silence is not a
        # verdict, in either direction.
        result = assess(TURNOVER, Profile())
        assert result.status is Status.NEEDS_REVIEW
        assert result.measured is None
        assert "nothing can be concluded" in result.explanation

    def test_an_empty_list_is_treated_the_same_as_no_list(self):
        assert assess(TURNOVER, Profile(turnover_by_year=[])).status is Status.NEEDS_REVIEW


class TestReferences:
    def test_four_references_over_five_years_pass(self):
        profile = Profile(references_by_year=[2, 1, 1, 0, 0])
        result = assess(REFERENCES, profile)
        assert result.status is Status.COVERED

    def test_three_do_not(self):
        profile = Profile(references_by_year=[1, 1, 1, 0, 0])
        assert assess(REFERENCES, profile).status is Status.MISSING

    def test_references_outside_the_window_do_not_count(self):
        # "au titre des cinq (5) dernières années" bounds the content, not the
        # validity of a certificate — two different notions of date that a
        # single expiry check would conflate.
        profile = Profile(references_by_year=[1, 1, 1, 0, 0, 9, 9])
        assert assess(REFERENCES, profile).status is Status.MISSING

    def test_greater_or_equal_includes_the_boundary(self):
        profile = Profile(references_by_year=[4, 0, 0, 0, 0])
        assert assess(REFERENCES, profile).status is Status.COVERED


class TestHowNumbersAreShown:
    """A report that prints 2131666.6666666665 looks like a bug, and a reader
    who thinks they are looking at a bug stops reading."""

    def test_large_euro_amounts_are_rendered_in_millions(self):
        profile = Profile(turnover_by_year=[2_390_000, 2_140_000, 1_850_000])
        explanation = assess(TURNOVER, profile).explanation
        assert "2,13 M€" in explanation
        assert "2126666" not in explanation

    def test_counts_stay_whole(self):
        profile = Profile(references_by_year=[1, 1, 1, 0, 0])
        explanation = assess(REFERENCES, profile).explanation
        assert "3" in explanation
        assert "3.0" not in explanation


def test_every_verdict_is_one_the_matrix_already_knows():
    # Capacity rows sit in the same matrix as document rows, so they must use
    # the same statuses. A fifth status invented here would need its own column,
    # its own severity, and its own line in the headline.
    profiles = [
        Profile(turnover_by_year=[9_000_000] * 3),
        Profile(turnover_by_year=[1] * 3),
        Profile(turnover_by_year=[1]),
        Profile(),
    ]
    for profile in profiles:
        result = assess(TURNOVER, profile)
        assert isinstance(result, Assessment)
        assert result.status in {Status.COVERED, Status.MISSING, Status.NEEDS_REVIEW}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
