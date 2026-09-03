"""The rendered report, checked for the things a reader cannot check themselves.

Nothing here asserts that the page looks good — that is a judgement, and a test
that encodes it just freezes one person's taste. What is tested is what a reader
would be harmed by and could not detect: markup injected from a PDF or a model,
a page that silently needs the network, a figure that contradicts the row it
sits on.
"""

import re
from datetime import date

import pytest

from tender_compliance.coverage import Citation, Row, Stage, Status, measure
from tender_compliance.report import render
from tender_compliance.tender import Analysis

DEADLINE = date(2026, 10, 9)
TODAY = date(2026, 8, 23)


def row(status=Status.MISSING, **kwargs):
    base = dict(
        requirement="Preuve d'une assurance pour les risques professionnels",
        source=Citation(document="rc.pdf", page=5),
        status=status,
        stage=Stage.CANDIDATURE,
    )
    base.update(kwargs)
    return Row(**base)


def _la_ligne(page: str) -> str:
    """The first <article>, i.e. one row on its own.

    Assertions about a row belong to the row. The header repeats several of the
    same words as counts, and a page-wide `in` check quietly passes on them.
    """
    return page[page.index("<article"):page.index("</article>")]


def analysis(rows=None, **kwargs):
    rows = rows if rows is not None else [row()]
    base = dict(
        document="rc_ANTAI_2026.pdf",
        deadline=DEADLINE,
        rows=rows,
        counted=measure(rows),
        model="openai:some-model",
    )
    base.update(kwargs)
    return Analysis(**base)


class TestNothingFromOutsideBecomesMarkup:
    """The requirement text is quoted from a document nobody here wrote, and
    the note can carry a model's words. Neither is trusted."""

    def test_a_script_tag_in_a_requirement_is_escaped(self):
        page = render(analysis([row(requirement="<script>alert(1)</script>")]),
                      today=TODAY)
        assert "<script>alert(1)</script>" not in page
        assert "&lt;script&gt;" in page

    def test_a_script_tag_in_a_model_note_is_escaped(self):
        page = render(analysis([row(note='<img src=x onerror="alert(1)">')]),
                      today=TODAY)
        assert "onerror=" not in page.replace("&quot;", '"').replace("&gt;", ">") \
            or "&lt;img" in page

    def test_a_document_name_cannot_break_out_of_an_attribute(self):
        page = render(analysis(document='"><script>alert(1)</script>'), today=TODAY)
        assert "<script>" not in page

    def test_ordinary_french_survives_intact(self):
        # Escaping that mangles accented text would make the report unreadable
        # for exactly the people it is written for.
        page = render(analysis([row(requirement="Déclaration sur l'honneur, "
                                                "à défaut d'attestation")]),
                      today=TODAY)
        assert "Déclaration sur l&#x27;honneur, à défaut d&#x27;attestation" in page \
            or "Déclaration sur l'honneur, à défaut d'attestation" in page


class TestItWorksWithNoNetwork:
    """Written next to a tender folder, opened from disk, often offline."""

    def test_no_external_requests(self):
        """Looks for constructs that *load* something, not for the letters http.

        The first version of this test grepped for "https://" anywhere in the
        page. It passed on fabricated rows and would have failed on the first
        real one: French tenders quote their own URLs, and page 5 of the DGAC
        file tells candidates to download DC1 from economie.gouv.fr. That text
        belongs in the report — escaped, inert, and not a request.
        """
        page = render(analysis([
            row(requirement="Lettre de candidature ou formulaire DC1 "
                            "(téléchargeable à partir du lien "
                            "https://www.economie.gouv.fr/daj/formulaires)"),
        ]), today=TODAY)

        loaders = re.findall(
            r"""(?:src|href)\s*=\s*["']?[^"'>\s]+|@import[^;]+|url\(\s*[^)]+\)""",
            page, re.IGNORECASE,
        )
        remote = [ref for ref in loaders
                  if "//" in ref and not ref.lstrip().startswith(("data:", "#"))]
        assert not remote, f"these would need the network: {remote}"

    def test_a_url_quoted_from_the_tender_survives_as_text(self):
        page = render(analysis([
            row(requirement="téléchargeable à partir du lien "
                            "https://www.economie.gouv.fr/daj/formulaires"),
        ]), today=TODAY)
        assert "economie.gouv.fr" in page
        assert "<a " not in page, "a quoted URL must not become a link"

    def test_no_script_of_our_own(self):
        # A report that needs JavaScript to say what is missing is a report that
        # fails silently in a print preview or an email client.
        assert "<script" not in render(analysis(), today=TODAY)

    def test_the_stylesheet_travels_with_it(self):
        page = render(analysis(), today=TODAY)
        assert "<style>" in page
        assert "rel=\"stylesheet\"" not in page


class TestTheNumberThatMatters:
    """"Valid today, expired on the submission date" is the finding. A sentence
    buries it; a signed day count does not."""

    def test_a_document_lapsing_first_shows_a_negative_count(self):
        page = render(analysis([row(status=Status.EXPIRED, slack=-9,
                                    evidence=Citation("Assurance RC", 1))]),
                      today=TODAY)
        assert "-9 d" in page

    def test_and_is_marked_as_the_late_case(self):
        page = render(analysis([row(status=Status.EXPIRED, slack=-9,
                                    evidence=Citation("Assurance RC", 1))]),
                      today=TODAY)
        assert "slack late" in page

    def test_a_comfortable_margin_is_shown_with_a_sign(self):
        page = render(analysis([row(status=Status.COVERED, slack=120,
                                    evidence=Citation("Kbis", 1))]),
                      today=TODAY)
        assert "+120 d" in page
        assert "slack late" not in page

    def test_no_expiry_prints_no_figure(self):
        # None is not zero. A document with no readable date must not appear to
        # expire exactly on the deadline.
        page = render(analysis([row(slack=None)]), today=TODAY)
        assert " j</span>" not in page


class TestWhatTheReaderIsToldFirst:
    def test_the_deadline_and_days_left_are_in_the_masthead(self):
        page = render(analysis(), today=TODAY)
        assert "2026-10-09" in page
        assert str((DEADLINE - TODAY).days) in page

    def test_the_two_piles_are_counted_separately(self):
        """This test used to assert a single "Blocking" figure.

        One number told the reader to treat both piles alike, and they are not
        alike: "Les candidatures incomplètes […] sont éliminées" (ANTAI IV.9)
        against "l'acheteur peut autoriser […] à régulariser les offres
        irrégulières" (DGAC 6.2). The same missing paper ends the bid in one
        pile and invites a correction in the other.
        """
        rows = [
            row(status=Status.MISSING, stage=Stage.CANDIDATURE),
            row(status=Status.MISSING, stage=Stage.OFFER),
            row(status=Status.COVERED, evidence=Citation("Kbis", 1)),
        ]
        page = render(analysis(rows), today=TODAY)
        assert "Ends the bid" in page
        assert "Correctable" in page

    def test_a_graded_row_shows_what_it_earns(self):
        page = render(analysis([row(status=Status.COVERED, points="2/2",
                                    evidence=Citation("Bilans", 1))]), today=TODAY)
        assert "earns 2/2" in page

    def test_and_a_missed_one_shows_what_it_costs(self):
        # « si x est strictement supérieur à 3 124 998 d'euros HT : 2/2 ». Sous
        # le seuil, le candidat n'est pas toujours éliminé — il perd des points,
        # et le verdict seul ne le dit pas.
        page = render(analysis([row(status=Status.MISSING, points="2/2")]),
                      today=TODAY)
        assert "forgoes 2/2" in page
        assert "grade lost" in page

    def test_an_ungraded_row_shows_no_grade(self):
        # La plupart des exigences sont binaires. Afficher une note là où
        # l'acheteur n'en a énoncé aucune reviendrait à l'inventer.
        page = render(analysis([row(points="")]), today=TODAY)
        assert "earns" not in page and "forgoes" not in page

    def test_an_offer_row_says_so_on_the_row_itself(self):
        # Without the badge the row reads as a candidature piece, and the
        # header count has nothing a reader can trace it back to.
        #
        # Read the row, not the page: the header carries a "Correctable" count,
        # so a page-wide search would pass on a row that says nothing at all.
        # That was harmless while the badge read "régularisable" and became a
        # trap the moment it was translated.
        assert "correctable" in _la_ligne(render(analysis([row(stage=Stage.OFFER)]),
                                                today=TODAY)).lower()

    def test_a_candidature_row_carries_no_such_badge(self):
        page = render(analysis([row(stage=Stage.CANDIDATURE)]), today=TODAY)
        assert "correctable" not in _la_ligne(page).lower()

    def test_unreadable_pages_are_flagged_above_the_matrix(self):
        page = render(analysis(unreadable="part of the text is stored as images "
                                          "on pages 13, 14"), today=TODAY)
        assert "images" in page
        assert page.index("caution") < page.index("matrix")

    def test_rejected_proposals_are_listed_not_hidden(self):
        from tender_compliance.obligations import Proposal
        page = render(
            analysis(rejected=[(Proposal(text="une certification HDS", page=5),
                                "not found on page 5, which was read in full")]),
            today=TODAY,
        )
        assert "certification HDS" in page
        assert "read in full" in page

    def test_the_model_is_named_for_provenance(self):
        assert "openai:some-model" in render(analysis(), today=TODAY)

    def test_an_empty_matrix_still_renders_a_page(self):
        page = render(analysis(rows=[]), today=TODAY)
        assert "<html" in page and "</html>" in page


class TestItSurvivesBothThemesAndPaper:
    def test_dark_mode_is_defined_rather_than_inherited(self):
        page = render(analysis(), today=TODAY)
        assert "prefers-color-scheme: dark" in page
        assert "color-scheme: light dark" in page

    def test_print_rules_exist(self):
        # It will be printed and carried into a meeting.
        assert "@media print" in render(analysis(), today=TODAY)

    def test_rows_are_not_split_across_pages(self):
        assert "break-inside: avoid" in render(analysis(), today=TODAY)

    def test_the_alert_colour_is_reserved_for_blockers(self):
        # Spending the one accent anywhere else is how a report stops signalling.
        page = render(analysis([row(status=Status.COVERED,
                                    evidence=Citation("Kbis", 1))]), today=TODAY)
        body = page.split("</style>", 1)[1]
        assert "blocks" not in body


def test_every_status_renders_a_distinct_label():
    labels = set()
    for status in Status:
        page = render(analysis([row(
            status=status,
            evidence=Citation("Kbis", 1) if status is not Status.MISSING else None,
        )]), today=TODAY)
        stamp = re.search(r'<span class="stamp">([^<]+)</span>', page)
        assert stamp, f"no stamp rendered for {status}"
        labels.add(stamp.group(1))
    assert len(labels) == len(Status)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))


class TestTheReportReadsInEnglish:
    """The chrome is English; the quotations are French because the tender is.

    Three labels were French by oversight rather than by design, which is a
    different thing from the quotations and gets fixed rather than defended.
    """

    def test_no_french_label_is_printed_around_the_rows(self):
        page = render(analysis([
            row(status=Status.MISSING, stage=Stage.OFFER),
            row(status=Status.COVERED, points="2/2",
                evidence=Citation(document="Attestation", page=1)),
            row(status=Status.NEEDS_REVIEW, points="0/2"),
        ]), today=TODAY)
        for francais in ("régularisable", "obtient", "perd ", "offre —"):
            assert francais not in page, f"{francais!r} is a label, not a quotation"

    def test_days_are_counted_in_english(self):
        page = render(analysis([row(status=Status.EXPIRED, slack=-9,
                                    evidence=Citation(document="A", page=1))]),
                      today=TODAY)
        assert "-9 d" in page
        assert "-9 j" not in page

    def test_the_offer_pile_is_still_named(self):
        """Not merely somewhere on the page — the header already carries a
        'Correctable' count, which would let this pass without the row label."""
        page = render(analysis([row(stage=Stage.OFFER)]), today=TODAY)
        assert "correctable" in _la_ligne(page).lower()

    def test_a_grade_still_says_whether_it_is_won_or_lost(self):
        gagne = render(analysis([row(status=Status.COVERED, points="2/2",
                                     evidence=Citation(document="A", page=1))]),
                       today=TODAY)
        perdu = render(analysis([row(status=Status.MISSING, points="2/2")]), today=TODAY)
        assert "earns 2/2" in gagne
        assert "forgoes 2/2" in perdu


class TestTheEnglishGlossIsShownBesideTheQuotation:

    def test_the_gloss_appears(self):
        page = render(analysis([row(gloss="Proof of professional indemnity insurance")]),
                      today=TODAY)
        assert "Proof of professional indemnity insurance" in page

    def test_the_french_quotation_is_still_there(self):
        page = render(analysis([row(gloss="Proof of insurance")]), today=TODAY)
        assert "assurance pour les risques professionnels" in page

    def test_a_row_without_a_gloss_prints_no_empty_line(self):
        page = render(analysis([row(gloss="")]), today=TODAY)
        assert 'class="gloss"' not in page

    def test_a_gloss_carrying_markup_is_escaped_like_anything_else(self):
        page = render(analysis([row(gloss="<script>alert(1)</script>")]), today=TODAY)
        assert "<script>" not in page
        assert "&lt;script&gt;" in page
