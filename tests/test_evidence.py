"""Matching, tested on the failures that cost a tender rather than a glance.

No model runs here. `resolve` and `to_row` are the two functions that must never
be wrong, and both are pure — the proposer is a parameter precisely so these
tests can state what the tool is allowed to assert without one.

The library is the real sample fixture, so the date cases below are the same
ones `test_library.py` pins.
"""

from datetime import date
from pathlib import Path

import pytest

from tender_compliance.coverage import Citation, Stage, Status, check
from tender_compliance.evidence import (
    Match,
    Suggestion,
    build,
    find,
    resolve,
    to_row,
)
from tender_compliance.library import load
from tender_compliance.obligations import Obligation
from tender_compliance.validity import Document

LIBRARY_FILE = Path(__file__).resolve().parent.parent / "samples" / "evidence_library.json"
TODAY = date(2026, 8, 23)

ASSURANCE = "Attestation d'assurance responsabilité civile professionnelle"
URSSAF = "Attestation de vigilance URSSAF"
ISO = "Certificat ISO/IEC 27001"
LABEL = "Label ExpertCyber"


@pytest.fixture(scope="module")
def library_and_deadline():
    return load(LIBRARY_FILE)


@pytest.fixture(scope="module")
def library(library_and_deadline):
    return library_and_deadline[0]


@pytest.fixture(scope="module")
def deadline(library_and_deadline):
    return library_and_deadline[1]


def obligation(text="Preuve d'une assurance pour les risques professionnels", **kwargs):
    defaults = dict(
        source=Citation(document="rc.pdf", page=5),
        stage=Stage.BID,
    )
    defaults.update(kwargs)
    return Obligation(text=text, **defaults)


class TestTheModelCannotInventEvidence:
    """The library is the ground truth about what the company holds."""

    def test_a_document_not_in_the_library_is_dropped(self, library):
        match = resolve(
            obligation(),
            [Suggestion(document="Attestation HDS", page=1)],
            library,
        )
        assert match.document is None
        assert match.certain is True          # confidently absent
        assert "not in the library" in match.reason

    def test_a_real_document_is_kept(self, library):
        match = resolve(obligation(), [Suggestion(document=ASSURANCE, page=2)], library)
        assert match.document is not None
        assert match.document.name == ASSURANCE
        assert match.certain is True

    def test_the_real_one_survives_alongside_an_invented_one(self, library):
        match = resolve(
            obligation(),
            [Suggestion(document="Attestation Qualiopi", page=1),
             Suggestion(document=ASSURANCE, page=2)],
            library,
        )
        assert match.document.name == ASSURANCE
        assert match.certain is True


class TestTheCitationComesFromTheLibrary:
    """This class used to assert the opposite, and the opposite was wrong.

    The first design demanded a page from the model and downgraded the row when
    none came. Run against a real consultation file it degraded nearly every
    row: the library describes documents by name and date, so the model was
    being asked for something it had no way to know. A matrix where everything
    says "review" says nothing at all.

    The document's declared page is data — it is where the company says its own
    proof sits — so that is what the citation uses.
    """

    def test_a_match_with_no_page_from_the_model_still_cites_the_document(self, library):
        match = resolve(obligation(), [Suggestion(document=ASSURANCE)], library)
        assert match.certain is True
        assert match.citation is not None
        assert match.citation.document == ASSURANCE
        assert match.citation.page >= 1

    def test_page_zero_falls_back_rather_than_leaking_a_zero_based_index(self, library):
        # coverage.check refuses page 0 outright — it is the signature of an
        # index that escaped its conversion.
        match = resolve(obligation(), [Suggestion(document=ASSURANCE, page=0)], library)
        assert match.citation.page >= 1

    def test_a_page_the_model_gives_is_used_as_a_refinement(self, library):
        # Inside a document the library already vouches for, a specific page is
        # useful; it is not permission to cite a document that is not there.
        match = resolve(obligation(), [Suggestion(document=ASSURANCE, page=7)], library)
        assert match.citation.page == 7

    def test_the_row_it_produces_passes_the_matrix_check(self, library, deadline):
        match = resolve(obligation(), [Suggestion(document=URSSAF)], library)
        row = to_row(match, deadline, today=TODAY)
        assert row.status is Status.COVERED
        assert row.evidence is not None
        assert check([row]) == []


class TestAFormIsNotAMissingDocument:
    """Nine MISSING rows for a company with nothing to look for.

    An evidence library holds papers. It cannot hold a déclaration sur
    l'honneur, a DC1 or a DUME — those are written for this tender. Reporting
    them missing is noise, and noise is how a report stops being read.
    """

    def test_a_form_with_nothing_found_is_not_missing(self, library, deadline):
        match = resolve(obligation(to_produce=True), [], library)
        assert match.certain is False
        assert "form to fill in" in match.reason
        assert to_row(match, deadline, today=TODAY).status is Status.NEEDS_REVIEW

    def test_it_still_blocks_the_bid(self, library, deadline):
        # Not a document to find is not the same as nothing to do: the form has
        # to be written before submission, so it counts among the blockers.
        from tender_compliance.coverage import measure
        row = to_row(resolve(obligation(to_produce=True), [], library),
                     deadline, today=TODAY)
        assert measure([row]).blocking == 1

    def test_a_document_that_is_not_a_form_is_still_missing(self, library, deadline):
        match = resolve(obligation(), [], library)
        assert to_row(match, deadline, today=TODAY).status is Status.MISSING

    def test_the_near_miss_is_still_named(self, library):
        match = resolve(
            obligation(to_produce=True),
            [Suggestion(document=ASSURANCE, satisfies=False)],
            library,
        )
        assert ASSURANCE in match.reason


class TestOnlyAnExplicitYesCounts:
    """Written after watching a live run, not before it.

    Told to return nothing when the library has no answer, the model returned
    the nearest document and explained in its own words that it did not answer:
    "Le Kbis n'est pas un DUME distinct", attached to a row marked covered. The
    judgement is now a field it must fill in, and only an explicit yes is taken.
    """

    def test_a_document_the_matcher_rejects_is_not_a_match(self, library):
        match = resolve(
            obligation(),
            [Suggestion(document=ASSURANCE, page=1, satisfies=False,
                        reason="related, but does not answer this")],
            library,
        )
        assert match.document is None

    def test_and_the_near_miss_is_named_rather_than_hidden(self, library):
        # "closest was X, and it does not answer this" tells a bidder where to
        # start; a bare MISSING tells them to search the whole folder.
        match = resolve(
            obligation(),
            [Suggestion(document=ASSURANCE, satisfies=False)],
            library,
        )
        assert ASSURANCE in match.reason
        assert "does not answer" in match.reason

    def test_an_affirmed_document_survives_alongside_a_rejected_one(self, library):
        match = resolve(
            obligation(),
            [Suggestion(document=ISO, satisfies=False),
             Suggestion(document=ASSURANCE, page=2, satisfies=True)],
            library,
        )
        assert match.document.name == ASSURANCE
        assert match.certain is True

    def test_rejecting_everything_still_lands_on_the_right_status(self, library, deadline):
        match = resolve(obligation(), [Suggestion(document=ISO, satisfies=False)], library)
        row = to_row(match, deadline, today=TODAY)
        assert row.status is Status.MISSING
        assert check([row]) == []

    def test_the_default_is_yes_so_a_plain_suggestion_still_matches(self, library):
        # Suggestion is also constructed by hand in tests and by any future
        # non-model proposer; requiring the flag everywhere would be noise.
        assert resolve(obligation(), [Suggestion(document=ASSURANCE)], library).certain


class TestAmbiguityIsReportedNotResolved:
    def test_two_candidates_produce_a_review(self, library):
        match = resolve(
            obligation(),
            [Suggestion(document=ASSURANCE, page=2), Suggestion(document=ISO, page=1)],
            library,
        )
        assert match.certain is False
        assert match.document is None
        assert ASSURANCE in match.reason and ISO in match.reason

    def test_the_same_document_twice_is_not_ambiguity(self, library):
        match = resolve(
            obligation(),
            [Suggestion(document=ASSURANCE, page=2), Suggestion(document=ASSURANCE, page=2)],
            library,
        )
        assert match.certain is True


class TestUncertaintyPropagates:
    """An unverified obligation cannot produce a confident row."""

    def test_an_unanchored_obligation_never_yields_a_certain_match(self, library):
        match = resolve(
            obligation(anchored=False),
            [Suggestion(document=ASSURANCE, page=2)],
            library,
        )
        assert match.certain is False
        assert "could not be verified" in match.reason

    def test_even_with_a_perfectly_good_document(self, library, deadline):
        match = resolve(
            obligation(anchored=False),
            [Suggestion(document=URSSAF, page=1)],
            library,
        )
        row = to_row(match, deadline, today=TODAY)
        assert row.status is Status.NEEDS_REVIEW

    def test_and_nothing_found_is_not_reported_missing_either(self, library):
        # Reporting MISSING would assert an absence in a document we could not
        # read. That is the one thing the extractor refuses to do.
        match = resolve(obligation(anchored=False), [], library)
        assert match.certain is False
        assert match.document is None


class TestAbsenceIsNotAlwaysMissing:
    """Both cases come from wording in samples/real_requirements.json."""

    def test_a_conditional_obligation_with_nothing_found_goes_to_review(self, library, deadline):
        # "L'attestation de l'Administration fiscale en cas de
        # non-assujettissement à la TVA" — does not concern most bidders.
        match = resolve(obligation(conditional=True), [], library)
        assert match.certain is False
        assert "applies only in a stated case" in match.reason
        assert to_row(match, deadline, today=TODAY).status is Status.NEEDS_REVIEW

    def test_an_obligation_with_alternatives_too(self, library, deadline):
        # "attestations du destinataire ou, à défaut, une déclaration [...]
        # Ou PARTIE IV C 1b) du DUME." Three routes; one empty proves nothing.
        match = resolve(obligation(has_alternatives=True), [], library)
        assert match.certain is False
        assert "more than one way" in match.reason
        assert to_row(match, deadline, today=TODAY).status is Status.NEEDS_REVIEW

    def test_a_plain_obligation_with_nothing_found_is_missing(self, library, deadline):
        # Without this, every empty row would degrade to "review" and the
        # matrix would stop naming anything as a real gap.
        match = resolve(obligation(), [], library)
        assert match.certain is True
        assert to_row(match, deadline, today=TODAY).status is Status.MISSING

    def test_a_missing_row_cites_no_evidence(self, library, deadline):
        row = to_row(resolve(obligation(), [], library), deadline, today=TODAY)
        assert row.evidence is None
        assert check([row]) == []


class TestTheDateVerdictIsNotTheMatchers:
    """Invariant 2, against the sample library's engineered cases."""

    def test_a_document_expiring_before_the_deadline_is_not_covered(self, library, deadline):
        match = resolve(obligation(), [Suggestion(document=ASSURANCE, page=2)], library)
        assert match.certain is True          # the matcher is happy
        row = to_row(match, deadline, today=TODAY)
        assert row.status is Status.EXPIRED   # the arithmetic is not
        assert "submission date" in row.note

    def test_and_it_keeps_its_citation_because_the_remedy_is_that_document(self, library, deadline):
        row = to_row(
            resolve(obligation(), [Suggestion(document=ASSURANCE, page=2)], library),
            deadline, today=TODAY,
        )
        assert row.evidence is not None
        assert row.evidence.document == ASSURANCE

    def test_a_lapsed_certificate_is_expired(self, library, deadline):
        row = to_row(
            resolve(obligation(), [Suggestion(document=ISO, page=1)], library),
            deadline, today=TODAY,
        )
        assert row.status is Status.EXPIRED

    def test_an_unreadable_date_goes_to_review_not_to_covered(self, library, deadline):
        row = to_row(
            resolve(obligation(), [Suggestion(document=LABEL, page=1)], library),
            deadline, today=TODAY,
        )
        assert row.status is Status.NEEDS_REVIEW
        assert "no usable date" in row.note

    def test_the_age_rule_comes_from_the_obligation(self, library, deadline):
        # URSSAF is valid on its own terms and refused when the buyer demands
        # one under six months. The rule was read from the tender text by
        # obligations.max_age_months and is applied here by arithmetic.
        plain = resolve(obligation(), [Suggestion(document=URSSAF, page=1)], library)
        assert to_row(plain, deadline, today=TODAY).status is Status.COVERED

        strict = resolve(
            obligation(max_age_months=6), [Suggestion(document=URSSAF, page=1)], library
        )
        assert to_row(strict, deadline, today=TODAY).status is Status.EXPIRED


class TestTheWholeMatrix:
    def test_build_produces_one_row_per_obligation(self, library, deadline):
        obligations = [
            obligation("Preuve d'une assurance pour les risques professionnels"),
            obligation("Attestation de vigilance URSSAF"),
            obligation("Certification HDS pour l'hébergement de données de santé"),
        ]
        answers = {
            obligations[0].text: [Suggestion(document=ASSURANCE, page=2)],
            obligations[1].text: [Suggestion(document=URSSAF, page=1)],
        }

        rows = build(
            obligations, library, deadline, today=TODAY,
            propose=lambda o, lib: answers.get(o.text, []),
        )
        assert len(rows) == 3
        assert [r.status for r in rows] == [
            Status.EXPIRED, Status.COVERED, Status.MISSING,
        ]

    def test_the_matrix_it_builds_is_structurally_sound(self, library, deadline):
        obligations = [
            obligation("assurance", anchored=False),
            obligation("urssaf", conditional=True),
            obligation("iso"),
        ]
        rows = build(
            obligations, library, deadline, today=TODAY,
            propose=lambda o, lib: [Suggestion(document=ISO, page=1)],
        )
        # check() is the report's own validator: no COVERED without a citation,
        # no MISSING with one, no page below 1.
        assert check(rows) == []

    def test_find_threads_the_proposer_through(self, library):
        match = find(
            obligation(), library,
            propose=lambda o, lib: [Suggestion(document=ASSURANCE, page=2)],
        )
        assert isinstance(match, Match)
        assert match.document.name == ASSURANCE

    def test_a_proposer_that_offers_nothing_is_not_an_error(self, library, deadline):
        rows = build([obligation()], library, deadline, today=TODAY,
                     propose=lambda o, lib: [])
        assert rows[0].status is Status.MISSING


def test_an_empty_library_reports_gaps_rather_than_crashing(deadline):
    match = resolve(obligation(), [Suggestion(document=ASSURANCE, page=1)], [])
    assert match.document is None
    row = to_row(match, deadline, today=TODAY)
    assert row.status is Status.MISSING


def test_every_row_this_module_can_produce_passes_the_matrix_check(library, deadline):
    """The one assertion worth more than the rest: whatever path is taken, the
    report never claims something it cannot show."""
    suggestions = [
        [],
        [Suggestion(document=ASSURANCE, page=2)],
        [Suggestion(document=ASSURANCE)],
        [Suggestion(document="invented", page=1)],
        [Suggestion(document=ASSURANCE, page=2), Suggestion(document=ISO, page=1)],
        [Suggestion(document=LABEL, page=1)],
        [Suggestion(document=URSSAF, page=1)],
    ]
    flags = [
        dict(), dict(anchored=False), dict(conditional=True),
        dict(has_alternatives=True), dict(max_age_months=6),
    ]
    rows = []
    for offer in suggestions:
        for flag in flags:
            rows.append(to_row(resolve(obligation(**flag), offer, library),
                               deadline, today=TODAY))
    assert len(rows) == 35
    assert check(rows) == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
