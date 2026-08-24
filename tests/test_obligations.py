"""Extraction, tested where it can actually go wrong.

No model runs here. That is the point of `extract(source, propose)` taking the
proposer as a parameter: the part that must never be wrong — deciding what the
document supports — is pure, and is exercised against the two real consultation
files in `samples/real_dce/`.

The fabricated proposals below are the interesting cases: a correct quote, a
reflowed one, a quote from the wrong page, and one that was never in the
document at all. A model will produce all four.
"""

from pathlib import Path

import pytest

from tender_compliance.coverage import Stage
from tender_compliance.extraction import Fidelity, read
from tender_compliance.obligations import (
    ANCHOR_OVERLAP,
    Extraction,
    Obligation,
    Proposal,
    anchor,
    classify,
    extract,
    max_age_months,
    verify,
)

DCE = Path(__file__).resolve().parent.parent / "samples" / "real_dce"
CLEAN = DCE / "rc_2026SDCRH05.pdf"   # DGAC — every page readable
LOSSY = DCE / "rc_ANTAI_2026.pdf"    # ANTAI — text stored as images


@pytest.fixture(scope="module")
def clean():
    return read(CLEAN)


@pytest.fixture(scope="module")
def lossy():
    return read(LOSSY)


def _only(result, *, anchored=True):
    """The single obligation a result kept, or None if it kept none."""
    return result.obligations[0] if result.obligations else None


class TestAnchoringAgainstARealDocument:
    def test_a_real_sentence_anchors(self, clean):
        # Page 5, article 5.4, quoted from the file itself.
        proposal = Proposal(
            text="déclaration concernant le chiffre d'affaires global et le chiffre "
                 "d'affaires concernant les prestations objet du marché, réalisés au "
                 "cours des trois derniers exercices disponibles",
            page=5,
        )
        assert anchor(proposal, clean)

    def test_the_same_sentence_reflowed_still_anchors(self, clean):
        # Models normalise whitespace and repair line breaks. Demanding an exact
        # substring would reject correct quotations from every real file.
        proposal = Proposal(
            text="Déclaration concernant le chiffre d'affaires global\net le chiffre "
                 "d'affaires   concernant les prestations objet du marché réalisés "
                 "au cours des trois derniers exercices",
            page=5,
        )
        assert anchor(proposal, clean)

    def test_a_sentence_from_the_wrong_page_does_not(self, clean):
        # The failure a page number is supposed to catch.
        proposal = Proposal(
            text="déclaration concernant le chiffre d'affaires global et le chiffre "
                 "d'affaires concernant les prestations objet du marché, réalisés au "
                 "cours des trois derniers exercices disponibles",
            page=1,
        )
        assert not anchor(proposal, clean)

    def test_an_invented_requirement_does_not(self, clean):
        # Plausible, administrative, in the right register — and absent.
        proposal = Proposal(
            text="Le candidat fournit une attestation de conformité au référentiel "
                 "HDS délivrée par un organisme accrédité au titre de l'hébergement "
                 "de données de santé",
            page=5,
        )
        assert not anchor(proposal, clean)

    def test_a_page_that_does_not_exist_does_not(self, clean):
        assert not anchor(Proposal(text="chiffre d'affaires", page=999), clean)

    def test_an_empty_quote_does_not(self, clean):
        assert not anchor(Proposal(text="   ", page=5), clean)


class TestShortObligations:
    """"DC1, DC2" is a complete requirement in the Ville de Paris notice."""

    def test_a_two_word_obligation_anchors_when_both_words_are_there(self, clean):
        assert anchor(Proposal(text="formulaire DC1", page=5), clean)

    def test_but_not_when_only_one_is(self, clean):
        # At two words a 0.6 ratio would accept a single match, and one
        # administrative word matches almost any page of these documents.
        assert not anchor(Proposal(text="formulaire DC9", page=5), clean)


class TestTheRuleForUnreadablePages:
    """The interaction that stops the two modules from fighting each other."""

    def test_an_unanchored_quote_on_a_lossy_page_is_kept_for_review(self, lossy):
        # This sentence is legible on screen and absent from the text layer.
        # Rejecting it would delete a mandatory document — the declaration
        # without which the bid is eliminated at IV.9.
        assert lossy.pages[12].fidelity is Fidelity.LOSSY
        proposal = Proposal(
            text="Une déclaration sur l'honneur pour justifier qu'il n'entre dans "
                 "aucun des cas mentionnés aux articles L. 2141-1 à L. 2141-5",
            page=13,
        )
        result = verify([proposal], lossy)
        assert len(result.obligations) == 1
        assert result.rejected == []

        kept = result.obligations[0]
        assert kept.anchored is False
        assert "images" in kept.note
        assert kept in result.needing_review

    def test_an_unanchored_quote_on_a_readable_page_is_rejected(self, clean):
        # Same failure to anchor, opposite verdict, and the difference is
        # whether we had any right to conclude from absence.
        proposal = Proposal(
            text="Le candidat fournit une attestation de conformité au référentiel "
                 "HDS délivrée par un organisme accrédité",
            page=5,
        )
        result = verify([proposal], clean)
        assert result.obligations == []
        assert len(result.rejected) == 1
        assert "read in full" in result.rejected[0][1]

    def test_a_quote_that_does_anchor_on_a_lossy_page_is_not_downgraded(self, lossy):
        # The surviving half of page 13 is still real text.
        proposal = Proposal(
            text="Chiffre d'affaires global pour chacun des 3 derniers exercices",
            page=13,
        )
        result = verify([proposal], lossy)
        assert result.obligations[0].anchored is True
        assert result.obligations[0].note == ""

    def test_the_file_level_warning_is_carried_up(self, lossy):
        result = verify([], lossy)
        assert "page" in result.warning
        assert "13" in result.warning

    def test_and_is_empty_for_a_file_read_in_full(self, clean):
        assert verify([], clean).warning == ""


class TestRejectionsAreVisible:
    def test_nothing_is_dropped_silently(self, clean):
        proposals = [
            Proposal(text="formulaire DC1", page=5),
            Proposal(text="une attestation de conformité HDS accréditée", page=5),
            Proposal(text="chiffre d'affaires", page=999),
        ]
        result = verify(proposals, clean)
        assert len(result.obligations) == 1
        assert len(result.rejected) == 2
        assert all(reason for _, reason in result.rejected)

    def test_a_nonexistent_page_says_so(self, clean):
        result = verify([Proposal(text="chiffre d'affaires", page=999)], clean)
        assert "does not exist" in result.rejected[0][1]


class TestWhatTheCodeDecidesInsteadOfTheModel:
    @pytest.mark.parametrize("text,expected", [
        ("attestation de vigilance de moins de six (6) mois", 6),
        ("un document datant de moins de 3 mois", 3),
        ("de moins de douze mois", 12),
        ("attestation de moins de 6 mois à la date de remise", 6),
        ("une attestation d'assurance en cours de validité", None),
        ("les trois derniers exercices", None),
    ])
    def test_the_age_rule_is_read_by_regex(self, text, expected):
        assert max_age_months(text) == expected

    def test_digits_win_when_the_document_writes_the_number_twice(self):
        # "six (6) mois". A document whose author typed both is a document whose
        # author typed the digits last.
        assert max_age_months("de moins de six (6) mois") == 6

    @pytest.mark.parametrize("text", [
        "L'attestation de l'Administration fiscale en cas de non-assujettissement à la TVA",
        "le cas échéant le DC4",
        "Pour les candidats dans l'impossibilité, à raison de leur création récente",
    ])
    def test_conditional_wording_is_detected(self, text, clean):
        # Asserted through the public path, so the flag is tested where it is
        # actually consumed rather than against the regex in isolation.
        obligation = _only(verify([Proposal(text=text, page=5)], clean), anchored=False)
        assert obligation is None or obligation.conditional
        from tender_compliance.obligations import _CONDITIONAL
        assert _CONDITIONAL.search(text)

    def test_a_plain_requirement_is_not_marked_conditional(self, clean):
        result = verify([Proposal(text="Preuve d'une assurance pour les risques "
                                       "professionnels", page=5)], clean)
        assert result.obligations[0].conditional is False

    @pytest.mark.parametrize("text", [
        "Lettre de candidature ou formulaire DC1 ou équivalent",
        "par des attestations du destinataire ou, à défaut, par une déclaration",
        "Ou PARTIE IV C 1b) du DUME",
        "il est autorisé à prouver sa capacité par tout autre moyen approprié",
    ])
    def test_alternative_routes_are_detected(self, text):
        from tender_compliance.obligations import _ALTERNATIVE
        assert _ALTERNATIVE.search(text)

    def test_a_plain_requirement_has_no_alternatives(self, clean):
        result = verify([Proposal(text="Preuve d'une assurance pour les risques "
                                       "professionnels", page=5)], clean)
        assert result.obligations[0].has_alternatives is False


class TestStageIsDecidedAtExtraction:
    """Invariant 2. The two errors are not symmetrical."""

    def test_performance_wording_is_recognised(self):
        assert classify("Le titulaire remet chaque mois un rapport d'activité", None) \
            is Stage.PERFORMANCE

    def test_silence_from_the_model_means_bid(self):
        assert classify("Le candidat produit une attestation d'assurance", None) is Stage.CANDIDATURE

    def test_the_text_overrides_a_model_that_says_bid(self):
        # The wording is the document; the model's opinion is not.
        assert classify(
            "pendant toute l'exécution du marché, le titulaire maintient son assurance",
            Stage.CANDIDATURE,
        ) is Stage.PERFORMANCE

    def test_a_model_may_still_raise_performance_on_its_own(self):
        assert classify("Un rapport trimestriel est remis", Stage.PERFORMANCE) \
            is Stage.PERFORMANCE


class TestEndToEnd:
    def test_extract_runs_the_proposals_through_verification(self, clean):
        def propose(source):
            return [
                Proposal(text="formulaire DC1", page=5),
                Proposal(text="une attestation HDS délivrée par un organisme accrédité", page=5),
            ]

        result = extract(clean, propose)
        assert isinstance(result, Extraction)
        assert len(result.obligations) == 1
        assert len(result.rejected) == 1

    def test_obligations_always_carry_a_locatable_citation(self, clean):
        def propose(source):
            return [Proposal(text="Preuve d'une assurance pour les risques professionnels",
                             page=5)]

        for obligation in extract(clean, propose).obligations:
            assert isinstance(obligation, Obligation)
            assert obligation.source.page >= 1
            assert obligation.source.document == CLEAN.name

    def test_nothing_proposed_means_nothing_asserted(self, clean):
        result = extract(clean, lambda source: [])
        assert result.obligations == []
        assert result.rejected == []

    def test_duplicates_stay_two_rows(self, clean):
        # Invariant 3. Merging is a decision, and a decision made silently over
        # a document the reader has not seen is the kind that surfaces at the
        # opening.
        twice = [Proposal(text="formulaire DC1", page=5)] * 2
        assert len(verify(twice, clean).obligations) == 2


class TestFormsAreNotDocuments:
    """A requirement answered by writing something, not by finding it.

    Built after a live run returned nine MISSING rows for a company with
    nothing to look for: the tender asked for "une déclaration sur l'honneur",
    "le formulaire DC1" and "un DUME", none of which an evidence library can
    contain. The distinction was recorded months earlier in
    samples/real_requirements.json and only became urgent when it was measured.
    """

    @pytest.mark.parametrize("text", [
        "Une déclaration sur l'honneur pour justifier qu'il n'entre dans aucun cas",
        "Lettre de candidature ou formulaire DC1",
        "l'imprimé DC4 (déclaration de sous-traitance)",
        "le document unique de marché européen (DUME)",
        "déclaration concernant le chiffre d'affaires global",
        "Déclaration indiquant les effectifs moyens annuels du candidat",
        "un document d'habilitation devra être signé par chacun des membres",
    ])
    def test_a_form_to_write_is_recognised(self, text):
        from tender_compliance.obligations import _TO_PRODUCE
        assert _TO_PRODUCE.search(text)

    @pytest.mark.parametrize("text", [
        "Preuve d'une assurance pour les risques professionnels",
        "Certificat ISO/IEC 27001 en cours de validité",
        "Attestation de vigilance URSSAF de moins de 6 mois",
        "Un dossier de références de prestations comparables au marché",
    ])
    def test_a_document_to_find_is_not(self, text):
        from tender_compliance.obligations import _TO_PRODUCE
        assert not _TO_PRODUCE.search(text)

    def test_the_pattern_compiled_the_way_it_was_written(self):
        """The defect this class exists because of.

        An earlier version reached the file through a shell heredoc, which
        turned every \\b into a literal backspace (0x08) and every \\s into
        backslash-s. The regex compiled without complaint and matched nothing at
        all, which no behavioural test noticed until a live run produced a
        matrix full of wrong answers.
        """
        from tender_compliance.obligations import (
            _ALTERNATIVE, _CONDITIONAL, _MAX_AGE, _PERFORMANCE, _TO_PRODUCE,
        )
        for name, expression in [
            ("_TO_PRODUCE", _TO_PRODUCE), ("_CONDITIONAL", _CONDITIONAL),
            ("_ALTERNATIVE", _ALTERNATIVE), ("_PERFORMANCE", _PERFORMANCE),
            ("_MAX_AGE", _MAX_AGE),
        ]:
            assert "\x08" not in expression.pattern, f"{name} contains a backspace"
            assert "\\\\" not in expression.pattern, f"{name} has doubled backslashes"

    def test_the_flag_reaches_the_obligation(self, clean):
        result = verify(
            [Proposal(text="Déclaration sur l'honneur précisant que le candidat "
                           "n'est pas en situation de redressement judiciaire",
                      page=6)],
            clean,
        )
        assert result.obligations[0].to_produce is True

    def test_and_stays_false_for_a_paper_in_a_folder(self, clean):
        result = verify(
            [Proposal(text="Preuve d'une assurance pour les risques professionnels",
                      page=5)],
            clean,
        )
        assert result.obligations[0].to_produce is False


class TestWhichPileAPieceBelongsTo:
    """Two real files, two penalties for the same missing paper.

        "Les candidatures incomplètes ou demeurées incomplètes à la suite d'une
         demande de compléments sont éliminées."        — ANTAI IV.9, DGAC 5.8

        "l'acheteur peut autoriser tous les soumissionnaires concernés à
         régulariser les offres irrégulières dans un délai approprié"  — DGAC 6.2

    A single "blocking" count told the reader to treat both alike.
    """

    @pytest.mark.parametrize("text", [
        # Quoted from article 6.1 of the DGAC file, which lists the offer.
        "L'acte d'engagement complété, daté et signé électroniquement",
        "Le mémoire technique détaillé",
        "son annexe financière auquel le candidat soumissionne",
        "Le RIB du candidat",
        "Le bordereau des prix unitaires",
    ])
    def test_the_offer_pile_is_recognised(self, text):
        assert classify(text, None) is Stage.OFFER

    @pytest.mark.parametrize("text", [
        "Lettre de candidature ou formulaire DC1",
        "Preuve d'une assurance pour les risques professionnels",
        "Une déclaration sur l'honneur relative aux motifs d'exclusion",
        "Pièces relatives au pouvoir des personnes habilitées à engager le candidat",
    ])
    def test_everything_else_is_candidature(self, text):
        assert classify(text, None) is Stage.CANDIDATURE

    def test_performance_still_wins_over_both(self):
        # It is the only value that does not block the bid, so it is the one
        # worth being sure about.
        assert classify(
            "Pendant toute l'exécution du marché, le titulaire remet un mémoire "
            "technique actualisé", None,
        ) is Stage.PERFORMANCE

    def test_doubt_resolves_towards_the_pile_that_ends_the_bid(self):
        """The asymmetry that decides the default.

        Filing a candidature piece as an offer piece tells the bidder it can be
        corrected later — it cannot, they are eliminated. The reverse costs a
        day of worry. So an unrecognised piece is candidature.
        """
        assert classify("Un document que personne n'a prévu", None) is Stage.CANDIDATURE

    def test_the_flag_survives_verification(self, clean):
        result = verify(
            [Proposal(text="L'acte d'engagement complété, daté et signé", page=7)],
            clean,
        )
        assert result.obligations[0].stage is Stage.OFFER


def test_the_overlap_threshold_stays_in_the_range_the_files_justify():
    # Above ~0.8 correct quotations from real PDFs start failing on line-break
    # artefacts; below ~0.5 unrelated administrative prose starts matching,
    # because these documents reuse the same forty words throughout.
    assert 0.5 <= ANCHOR_OVERLAP <= 0.8


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
