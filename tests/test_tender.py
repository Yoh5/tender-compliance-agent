"""The whole pipeline, run end to end without a model.

That it can be run this way is the design, not a testing convenience: `analyse`
takes both proposers as arguments, so every case below exercises the real
orchestration — extraction, verification, matching, date arithmetic, counting
and the self-check — with fabricated proposals standing in for the model.

The inputs are the real files: the ANTAI consultation file, whose text is partly
stored as images, and the fabricated evidence library.
"""

from datetime import date
from pathlib import Path

import pytest

from tender_compliance.coverage import Status
from tender_compliance.evidence import Suggestion
from tender_compliance.extraction import read
from tender_compliance.library import load
from tender_compliance.obligations import Proposal
from tender_compliance.tender import (
    PAGES_PER_BATCH,
    Analysis,
    ReportError,
    _batches,
    analyse,
)

ROOT = Path(__file__).resolve().parent.parent
LOSSY = ROOT / "samples" / "real_dce" / "rc_ANTAI_2026.pdf"
CLEAN = ROOT / "samples" / "real_dce" / "rc_2026SDCRH05.pdf"
LIBRARY_FILE = ROOT / "samples" / "evidence_library.json"

TODAY = date(2026, 8, 23)
ASSURANCE = "Attestation d'assurance responsabilité civile professionnelle"
URSSAF = "Attestation de vigilance URSSAF"


@pytest.fixture(scope="module")
def library_and_deadline():
    return load(LIBRARY_FILE)


@pytest.fixture(scope="module")
def clean():
    return read(CLEAN)


@pytest.fixture(scope="module")
def lossy():
    return read(LOSSY)


def nothing(*args, **kwargs):
    return []


class TestTheWholePipeline:
    def test_a_real_file_and_a_real_library_produce_a_matrix(self, clean, library_and_deadline):
        library, deadline = library_and_deadline

        def obligations(source):
            return [
                # Both quoted verbatim from page 5 of the DGAC file.
                Proposal(text="Preuve d'une assurance pour les risques professionnels",
                         page=5),
                Proposal(text="Pièces relatives au pouvoir des personnes habilitées "
                              "à engager le candidat", page=5),
            ]

        def evidence(obligation, lib):
            if "assurance" in obligation.text.lower():
                return [Suggestion(document=ASSURANCE, page=2, reason="the RC Pro policy")]
            return []

        result = analyse(
            clean, library, deadline, today=TODAY,
            propose_obligations=obligations, propose_evidence=evidence,
            model="test:none",
        )

        assert isinstance(result, Analysis)
        assert result.document == CLEAN.name
        assert len(result.rows) == 2
        assert result.counted.total == 2
        assert result.model == "test:none"

    def test_blockers_are_sorted_to_the_top(self, clean, library_and_deadline):
        library, deadline = library_and_deadline

        def obligations(source):
            return [
                Proposal(text="Preuve d'une assurance pour les risques professionnels",
                         page=5),
                Proposal(text="Pièces relatives au pouvoir des personnes habilitées "
                              "à engager le candidat", page=5),
            ]

        def evidence(obligation, lib):
            # The insurance is found; the other requirement is not.
            if "assurance" in obligation.text.lower():
                return [Suggestion(document=URSSAF, page=1)]
            return []

        result = analyse(clean, library, deadline, today=TODAY,
                         propose_obligations=obligations, propose_evidence=evidence)
        # MISSING outranks COVERED: sorted once here so no caller can sort
        # differently.
        assert result.rows[0].status is Status.MISSING

    def test_the_headline_comes_from_the_counts(self, clean, library_and_deadline):
        library, deadline = library_and_deadline
        result = analyse(
            clean, library, deadline, today=TODAY,
            propose_obligations=lambda s: [
                Proposal(text="Preuve d'une assurance pour les risques professionnels",
                         page=5)],
            propose_evidence=nothing,
        )
        assert "1 obligations" in result.headline
        assert "missing" in result.headline

    def test_nothing_proposed_is_an_empty_matrix_not_a_crash(self, clean, library_and_deadline):
        library, deadline = library_and_deadline
        result = analyse(clean, library, deadline, today=TODAY,
                         propose_obligations=nothing, propose_evidence=nothing)
        assert result.rows == []
        assert result.counted.total == 0
        assert result.headline


class TestWhatTheRunAdmitsItDoesNotKnow:
    def test_an_unsupported_quote_is_reported_as_rejected(self, clean, library_and_deadline):
        library, deadline = library_and_deadline
        result = analyse(
            clean, library, deadline, today=TODAY,
            propose_obligations=lambda s: [
                Proposal(text="Le candidat fournit une certification HDS délivrée "
                              "par un organisme accrédité", page=5)],
            propose_evidence=nothing,
        )
        assert result.rows == []
        assert len(result.rejected) == 1
        assert result.trustworthy is False

    def test_unreadable_pages_are_carried_into_the_report(self, lossy, library_and_deadline):
        library, deadline = library_and_deadline
        result = analyse(lossy, library, deadline, today=TODAY,
                         propose_obligations=nothing, propose_evidence=nothing)
        assert "images" in result.unreadable
        assert "13" in result.unreadable
        assert result.trustworthy is False

    def test_a_clean_run_with_nothing_dropped_is_trustworthy(self, clean, library_and_deadline):
        library, deadline = library_and_deadline
        result = analyse(
            clean, library, deadline, today=TODAY,
            propose_obligations=lambda s: [
                Proposal(text="Preuve d'une assurance pour les risques professionnels",
                         page=5)],
            propose_evidence=lambda o, lib: [Suggestion(document=URSSAF, page=1)],
        )
        assert result.trustworthy is True

    def test_the_model_is_named_for_provenance(self, clean, library_and_deadline):
        library, deadline = library_and_deadline
        result = analyse(clean, library, deadline, today=TODAY,
                         propose_obligations=nothing, propose_evidence=nothing,
                         model="openai:some-model")
        assert result.model == "openai:some-model"


class TestItRefusesToPrintWhatItCannotShow:
    def test_a_matrix_failing_its_own_check_raises(self, clean, library_and_deadline, monkeypatch):
        library, deadline = library_and_deadline

        # Force a structurally invalid matrix: a COVERED row with no citation is
        # the tool asserting something it cannot demonstrate.
        import tender_compliance.tender as module
        from tender_compliance.coverage import Citation, Row, Stage

        bad = Row(requirement="x", source=Citation(document="rc.pdf", page=1),
                  status=Status.COVERED, stage=Stage.BID, evidence=None)
        monkeypatch.setattr(module, "build_rows", lambda *a, **k: [bad])

        with pytest.raises(ReportError, match="cannot show"):
            analyse(clean, library, deadline, today=TODAY,
                    propose_obligations=nothing, propose_evidence=nothing)

    def test_the_error_names_the_offending_row(self, clean, library_and_deadline, monkeypatch):
        library, deadline = library_and_deadline
        import tender_compliance.tender as module
        from tender_compliance.coverage import Citation, Row, Stage

        bad = Row(requirement="assurance décennale", source=Citation("rc.pdf", 1),
                  status=Status.COVERED, stage=Stage.BID, evidence=None)
        monkeypatch.setattr(module, "build_rows", lambda *a, **k: [bad])

        with pytest.raises(ReportError) as error:
            analyse(clean, library, deadline, today=TODAY,
                    propose_obligations=nothing, propose_evidence=nothing)
        assert "assurance décennale" in str(error.value)


class TestBatching:
    """Page numbers survive only if they stay attached to their text."""

    def test_pages_are_grouped_without_losing_any(self, clean):
        batches = _batches(clean.pages, PAGES_PER_BATCH)
        assert sum(len(b) for b in batches) == len(clean.pages)
        assert [p.number for b in batches for p in b] == \
               [p.number for p in clean.pages]

    def test_the_last_batch_may_be_short(self):
        assert _batches(list(range(10)), 4) == [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9]]

    def test_an_empty_document_produces_no_batches(self):
        assert _batches([], 4) == []

    def test_the_batch_size_is_small_enough_to_keep_citations_honest(self):
        # One page per call is safest and costs a call per page; the whole file
        # at once loses track of which page said what, which makes every
        # citation useless.
        assert 1 <= PAGES_PER_BATCH <= 8


def test_the_pipeline_never_emits_a_row_it_cannot_defend(clean, library_and_deadline):
    """The assertion worth more than the rest, across every proposer behaviour."""
    library, deadline = library_and_deadline
    quotes = [
        "Preuve d'une assurance pour les risques professionnels",
        "Pièces relatives au pouvoir des personnes habilitées à engager le candidat",
        "une certification HDS délivrée par un organisme accrédité",   # invented
    ]
    offers = [
        [],
        [Suggestion(document=ASSURANCE, page=2)],
        [Suggestion(document=ASSURANCE)],                     # no page
        [Suggestion(document="Attestation inventée", page=1)],  # not in library
        [Suggestion(document=ASSURANCE, page=2), Suggestion(document=URSSAF, page=1)],
    ]
    for offer in offers:
        result = analyse(
            clean, library, deadline, today=TODAY,
            propose_obligations=lambda s: [Proposal(text=q, page=5) for q in quotes],
            propose_evidence=lambda o, lib: offer,
        )
        # analyse() raises rather than returning an indefensible matrix, so
        # simply getting here is the assertion. The counts must still add up.
        assert result.counted.total == len(result.rows)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
