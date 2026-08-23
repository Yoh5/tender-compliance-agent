"""Quantified requirements, tested against the wording that produced them.

Every case below traces to a sentence in `samples/real_requirements.json`,
quoted from a published notice. That is deliberate: the module exists because
reading real material showed the original design could not answer this family
of obligations at all, and the tests should keep pointing at the evidence.
"""

import pytest

from tender_compliance.capacity import (
    read_threshold,
    Aggregation,
    Assessment,
    Measure,
    Profile,
    Threshold,
    assess,
)
from pathlib import Path

from tender_compliance.coverage import Status, check
from tender_compliance.evidence import build
from tender_compliance.library import profile

LIBRARY_FILE = Path(__file__).resolve().parent.parent / "samples" / "evidence_library.json"
TODAY = __import__("datetime").date(2026, 8, 23)


@pytest.fixture(scope="module")
def library_and_deadline():
    from tender_compliance.library import load
    return load(LIBRARY_FILE)

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


class TestReadingAThresholdOutOfTheBuyersSentence:
    """Verbatim wording from three buyers. The numbers decide admissibility, a
    misread digit is invisible in the output, and the phrasing is regular enough
    that a regex is both more accurate than a model and auditable."""

    def test_the_antai_turnover_floor(self):
        # "IV.7 MINIMAUX REQUIS", rc_ANTAI_2026.pdf page 13.
        threshold = read_threshold(
            "ne retiendra que les candidats, seuls ou en groupement, dont le "
            "chiffre d'affaires du dernier exercice disponible est supérieur ou "
            "égal à 138 000 000 euros hors taxe."
        )
        assert threshold.measure is Measure.TURNOVER
        assert threshold.minimum == 138_000_000
        assert threshold.window_years == 1
        assert threshold.strict is False

    def test_the_ministry_of_education_grid(self):
        # 22-87951: three years, averaged, and strictly greater.
        threshold = read_threshold(
            "chiffre d'affaires annuel global moyen sur les trois derniers "
            "exercices disponibles. si x est strictement supérieur à "
            "3 124 998 d'euros HT : 2/2"
        )
        assert threshold.minimum == 3_124_998
        assert threshold.window_years == 3
        assert threshold.aggregation is Aggregation.AVERAGE
        assert threshold.strict is True

    def test_a_reference_count_over_five_years(self):
        threshold = read_threshold(
            "Un dossier de références de prestations comparables au titre des "
            "cinq (5) dernières années. si x est supérieur ou égal à 4: 2/2"
        )
        assert threshold.measure is Measure.REFERENCES
        assert threshold.minimum == 4
        assert threshold.window_years == 5
        assert threshold.aggregation is Aggregation.TOTAL

    def test_french_thousands_separators_are_not_decimal_points(self):
        # Reading "3 124 998" the English way gives 3. The separators in these
        # documents are ordinary spaces, non-breaking spaces and narrow ones,
        # sometimes all three in the same file.
        for spacing in ["3 124 998", "3\u00a0124\u00a0998", "3\u202f124\u202f998"]:
            threshold = read_threshold(
                f"chiffre d'affaires supérieur à {spacing} euros")
            assert threshold.minimum == 3_124_998

    @pytest.mark.parametrize("text", [
        "Preuve d'une assurance pour les risques professionnels",
        "Lettre de candidature ou formulaire DC1",
        "Une déclaration sur l'honneur relative aux motifs d'exclusion",
    ])
    def test_paperwork_states_no_threshold(self, text):
        assert read_threshold(text) is None

    def test_a_requirement_naming_no_figure_is_not_a_threshold(self):
        # "déclaration concernant le chiffre d'affaires global sur les trois
        # derniers exercices" asks for a declaration, not a minimum. Inventing a
        # threshold here would fail a company for a number nobody demanded.
        assert read_threshold(
            "déclaration concernant le chiffre d'affaires global et le chiffre "
            "d'affaires concernant les prestations objet du marché, réalisés au "
            "cours des trois derniers exercices disponibles"
        ) is None

    def test_a_turnover_of_nine_euros_is_a_misreading_not_a_requirement(self):
        # Refusing to read beats reading wrong: the floor is what stops a stray
        # digit becoming a threshold the whole matrix is judged against.
        assert read_threshold("chiffre d'affaires supérieur à 9 euros") is None


class TestTheCompanyProfileLoads:
    def test_years_are_reversed_to_most_recent_first(self):
        # The file lists them as a balance sheet does, oldest first; Profile
        # slices a window off the front. Getting this backwards is silent — a
        # plausible average computed from the wrong years.
        company = profile(LIBRARY_FILE)
        assert company.turnover_by_year == [2_390_000, 2_140_000, 1_850_000]

    def test_a_single_headcount_fills_the_window(self):
        company = profile(LIBRARY_FILE)
        assert company.headcount_by_year == [24, 24, 24]

    def test_a_library_with_no_profile_still_loads(self, tmp_path):
        path = tmp_path / "library.json"
        path.write_text('{"reference_deadline": "2026-10-09", '
                        '"documents": [{"name": "x"}]}', encoding="utf-8")
        company = profile(path)
        assert company.turnover_by_year is None


class TestQuantifiedRequirementsBypassTheMatcher:
    """No paper proves a turnover of 138 million. Asking a model which
    attestation does invites the confident wrong answer."""

    def test_a_threshold_row_is_decided_by_arithmetic(self, library_and_deadline):
        library, deadline = library_and_deadline
        company = profile(LIBRARY_FILE)
        asked = []

        rows = build(
            [_capacity_obligation()], library, deadline, today=TODAY,
            propose=lambda o, lib: asked.append(o) or [],
            company=company,
        )
        assert asked == [], "the matcher must not be asked about a figure"
        assert rows[0].status is Status.MISSING
        assert "138" in rows[0].note

    def test_the_shortfall_is_stated_as_a_figure(self, library_and_deadline):
        # "You are short" sends someone into the accounts. A number tells them
        # immediately whether a subcontractor's turnover could close the gap.
        library, deadline = library_and_deadline
        rows = build([_capacity_obligation()], library, deadline, today=TODAY,
                     propose=lambda o, lib: [], company=profile(LIBRARY_FILE))
        assert "short by" in rows[0].note
        assert "M€" in rows[0].note

    def test_it_cites_no_document_because_there_is_none(self, library_and_deadline):
        library, deadline = library_and_deadline
        rows = build([_capacity_obligation()], library, deadline, today=TODAY,
                     propose=lambda o, lib: [], company=profile(LIBRARY_FILE))
        assert rows[0].evidence is None
        assert check(rows) == []

    def test_ordinary_paperwork_still_goes_to_the_matcher(self, library_and_deadline):
        library, deadline = library_and_deadline
        asked = []
        build([_paper_obligation()], library, deadline, today=TODAY,
              propose=lambda o, lib: asked.append(o) or [],
              company=profile(LIBRARY_FILE))
        assert len(asked) == 1

    def test_without_a_profile_nothing_is_routed_away(self, library_and_deadline):
        # A caller that supplies no figures must not silently lose the row.
        library, deadline = library_and_deadline
        asked = []
        rows = build([_capacity_obligation()], library, deadline, today=TODAY,
                     propose=lambda o, lib: asked.append(o) or [])
        assert len(asked) == 1
        assert len(rows) == 1

    def test_the_matrix_keeps_one_row_per_obligation_in_order(self, library_and_deadline):
        library, deadline = library_and_deadline
        obligations = [_paper_obligation(), _capacity_obligation(), _paper_obligation()]
        rows = build(obligations, library, deadline, today=TODAY,
                     propose=lambda o, lib: [], company=profile(LIBRARY_FILE))
        assert len(rows) == 3
        assert [r.requirement for r in rows] == [o.text for o in obligations]


def _capacity_obligation():
    from tender_compliance.coverage import Citation, Stage
    from tender_compliance.obligations import Obligation
    return Obligation(
        text="ne retiendra que les candidats dont le chiffre d'affaires du dernier "
             "exercice disponible est supérieur ou égal à 138 000 000 euros hors taxe.",
        source=Citation(document="rc.pdf", page=13), stage=Stage.BID,
    )


def _paper_obligation():
    from tender_compliance.coverage import Citation, Stage
    from tender_compliance.obligations import Obligation
    return Obligation(
        text="Preuve d'une assurance pour les risques professionnels",
        source=Citation(document="rc.pdf", page=13), stage=Stage.BID,
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
