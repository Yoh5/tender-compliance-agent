"""Reading quality, tested against two real consultation files.

Both are published French tender documents, committed under `samples/real_dce/`
so these tests need no network — and so anyone can check the central claim by
opening page 13 of the ANTAI file and comparing it with what a copy-paste gives.

They are here because one file is silently unreadable and the other is not.
Without both polarities the thresholds would be numbers chosen by taste.
"""

from pathlib import Path

import pytest

from tender_compliance.extraction import (
    MIN_STRIP_WIDTH,
    Fidelity,
    Page,
    Source,
    read,
)

DCE = Path(__file__).resolve().parent.parent / "samples" / "real_dce"
CLEAN = DCE / "rc_2026SDCRH05.pdf"   # DGAC, deadline 11/09/2026
LOSSY = DCE / "rc_ANTAI_2026.pdf"    # ANTAI, deadline 28/10/2026


@pytest.fixture(scope="module")
def clean():
    return read(CLEAN)


@pytest.fixture(scope="module")
def lossy():
    return read(LOSSY)


class TestTheCleanFile:
    """A well-made PDF must not be flagged, or the warning means nothing."""

    def test_every_page_is_read_in_full(self, clean):
        assert clean.complete
        assert clean.unreadable == []

    def test_its_logo_is_not_mistaken_for_hidden_text(self, clean):
        # Page 1 carries exactly one image. Almost every official document does,
        # and a detector that flags letterheads would be switched off on day one.
        assert clean.pages[0].fidelity is Fidelity.COMPLETE

    def test_a_file_read_in_full_says_nothing(self, clean):
        assert clean.warning() == ""


class TestTheFileThatLiesQuietly:
    """The finding that produced this module."""

    def test_the_candidature_page_is_part_picture(self, lossy):
        # Page 13 states the obligations: déclaration sur l'honneur, chiffre
        # d'affaires, assurance, références, effectifs.
        page = lossy.pages[12]
        assert page.number == 13
        assert page.fidelity is Fidelity.LOSSY
        assert page.unreadable_runs == 10

    def test_a_mandatory_document_is_legible_on_screen_and_absent_from_the_text(self, lossy):
        # Rendered, page 13 reads "2° Une déclaration sur l'honneur pour
        # justifier qu'il n'entre dans aucun des cas mentionnés aux articles
        # L. 2141-1 ...". A bid without that declaration is eliminated at IV.9.
        text = lossy.pages[12].text
        assert "L. 2141-1" in text, "the surviving fragment should still be there"
        assert "déclaration sur l'honneur" not in text.lower(), (
            "if this ever passes, an extractor improved and the fixture must be "
            "re-examined — do not relax the assertion"
        )

    def test_the_loss_is_widespread_not_one_bad_page(self, lossy):
        assert len(lossy.unreadable) > 20

    def test_worst_pages_come_first(self, lossy):
        runs = [page.unreadable_runs for page in lossy.unreadable]
        assert runs == sorted(runs, reverse=True)


class TestWhatTheWarningHasToSay:
    def test_it_names_pages_a_human_can_open(self, lossy):
        # "6% of glyphs unresolved" tells a reader nothing they can act on.
        warning = lossy.warning()
        assert "page" in warning
        assert "13" in warning
        assert "rc_ANTAI_2026.pdf" in warning

    def test_it_says_what_the_reader_must_not_conclude(self, lossy):
        # The danger is not the missing text. It is the confident report built
        # on top of it.
        assert "absent" in lossy.warning()

    def test_pages_are_listed_in_reading_order(self, lossy):
        numbers = [
            int(token) for token in lossy.warning().replace(",", " ").split()
            if token.isdigit()
        ]
        assert numbers == sorted(numbers)


class TestTheRuleThisEnforces:
    """`complete` is what callers must check before reporting an absence."""

    def test_an_unread_file_can_never_support_a_negative_finding(self, lossy):
        assert lossy.complete is False

    def test_a_page_with_nothing_on_it_is_not_reported(self):
        # A blank page hides nothing. Sending someone to look at an empty sheet
        # is how a warning stops being read.
        blank = Page(number=1, text="")
        assert blank.fidelity is Fidelity.COMPLETE
        assert Source(path=Path("blank.pdf"), pages=[blank]).complete

    def test_a_scanned_page_is_lossy_even_with_no_strips(self):
        # The extreme case: no text layer at all. It carries no rasterised
        # strips by definition, so it must be caught by its own rule.
        scan = Page(number=1, text="", scanned=True)
        assert scan.fidelity is Fidelity.LOSSY
        assert scan.unreadable_runs == 0

    def test_one_hidden_run_is_enough_to_condemn_a_page(self):
        # There is no safe amount of unreadable text: the one strip missed could
        # be the one naming a mandatory document, which is what page 13 shows.
        page = Page(number=1, text="plenty of readable text", rasterised=((0, 0, 200, 12),))
        assert page.fidelity is Fidelity.LOSSY


def test_the_width_floor_lets_icons_through_and_not_phrases():
    """Bullets and rules are images too, and flagging them would drown the
    signal — but the floor has to stay far below the width of a phrase."""
    assert 0 < MIN_STRIP_WIDTH < 100


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
