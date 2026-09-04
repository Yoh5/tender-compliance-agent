"""An English gloss beside the French quotation — and the wall around it.

The rows this tool prints quote a French tender word for word, and `anchor`
checks that each quotation really is on the page it cites. That check is the
product. A reader who does not read French can see the verdict and not the
requirement, so a translation is worth having — but it is worth having only if
it can never become the thing that is checked.

So the gloss is decoration with a hard rule around it: it is produced AFTER
every verdict exists, it never reaches `anchor` or `resolve`, and if the
translation fails the report is exactly the report we would have printed
anyway. These tests are that rule, written down.
"""

from dataclasses import replace

import pytest

from tender_compliance.coverage import Citation, Row, Stage, Status
from tender_compliance.english import attach, looks_english, translator

EXIGENCE = "Preuve d'une assurance pour les risques professionnels ;"
GLOSE = "Proof of professional indemnity insurance"


def une_ligne(**kwargs) -> Row:
    base = dict(
        requirement=EXIGENCE,
        source=Citation(document="rc.pdf", page=5),
        status=Status.MISSING,
    )
    return Row(**{**base, **kwargs})


class TestTheGlossIsAttached:

    def test_each_row_gets_the_translation_that_belongs_to_it(self):
        # Une vraie traduction, pas un echo en majuscules : une glose qui redit
        # l'exigence est jetee, et le faux traducteur ne prouverait plus rien.
        mots = {"un": "one", "deux": "two"}
        rows = [une_ligne(requirement="un"), une_ligne(requirement="deux")]
        sortie = attach(rows, lambda textes: [mots[t] for t in textes])
        assert [r.gloss for r in sortie] == ["one", "two"]

    def test_the_translator_is_shown_the_requirements_and_nothing_else(self):
        recu = []

        def enregistre(textes):
            recu.append(list(textes))
            return list(textes)

        attach([une_ligne(note="a note", points="2/2")], enregistre)
        assert recu == [[EXIGENCE]]

    def test_no_rows_means_no_call_at_all(self):
        appels = []

        def compte(textes):
            appels.append(textes)
            return []

        assert attach([], compte) == []
        assert appels == []


class TestAGlossThatOnlyRepeatsTheRequirementIsDropped:
    """Observed on the European Parliament pack, 2026-09-04.

    Three rows came back glossed with themselves, renumbered:

        MISSING  p16  employ fewer than 250 persons
                  EN 2. employ fewer than 250 persons

    The counter had judged those fragments non-English — they are English, but
    too short to carry the two function words it requires, and that bar is not
    negotiable downwards: a French fragment like "Assurance responsabilite
    civile" carries none either, and lowering the bar would silently stop
    glossing the French rows this feature exists for.

    So the counter keeps its bar and the output is checked instead. A gloss that
    says the requirement again is not a translation, and on camera it reads as
    the tool malfunctioning — which, for the reader, is the same thing.
    """

    def test_the_case_that_was_actually_observed(self):
        exigence = "employ fewer than 250 persons"
        [ligne] = attach([une_ligne(requirement=exigence)],
                         lambda t: ["2. employ fewer than 250 persons"])
        assert ligne.gloss == ""

    def test_a_gloss_identical_to_the_requirement_is_dropped(self):
        [ligne] = attach([une_ligne(requirement="Annexe VI")], lambda t: ["Annexe VI"])
        assert ligne.gloss == ""

    def test_case_and_punctuation_do_not_rescue_an_echo(self):
        [ligne] = attach([une_ligne(requirement="Annexe VI, dument signee.")],
                         lambda t: ["ANNEXE VI — dument signee"])
        assert ligne.gloss == ""

    def test_an_empty_translation_is_not_a_translation(self):
        [ligne] = attach([une_ligne()], lambda t: ["   "])
        assert ligne.gloss == ""

    def test_a_gloss_with_no_word_in_it_is_not_a_translation(self):
        """`strip()` is not the test. A gloss of "—" survives it and says
        nothing."""
        [ligne] = attach([une_ligne()], lambda t: ["—"])
        assert ligne.gloss == ""

    def test_the_article_the_translator_dropped_does_not_rescue_the_echo(self):
        """The real second case, European Parliament p16, on the run after the
        first fix. Not an echo — one article short of one — and just as useless.

        Which is why the rule is not "the strings match" but "the gloss brings a
        word the requirement did not have".
        """
        exigence = "an annual balance sheet total not exceeding EUR 43 million."
        [ligne] = attach(
            [une_ligne(requirement=exigence)],
            lambda t: ["4. Annual balance sheet total not exceeding EUR 43 million."])
        assert ligne.gloss == ""

    def test_a_gloss_that_only_reshuffles_the_requirement_is_dropped(self):
        """Same words, another order, nothing gained. A French line and its
        English gloss do not share a vocabulary — the two languages barely spell
        a word the same way — so this can only happen to a line that was already
        readable."""
        [ligne] = attach([une_ligne(requirement="Annexe VI signed and dated")],
                         lambda t: ["Annexe VI dated and signed"])
        assert ligne.gloss == ""

    def test_a_real_translation_is_kept(self):
        [ligne] = attach([une_ligne()], lambda t: [GLOSE])
        assert ligne.gloss == GLOSE

    def test_a_translation_that_adds_one_word_is_kept(self):
        """The rule is "says the same thing", not "looks similar". Anything
        short of an exact echo is the translator's judgement, not ours."""
        [ligne] = attach([une_ligne(requirement="Annexe VI")],
                         lambda t: ["Annexe VI, completed"])
        assert ligne.gloss == "Annexe VI, completed"

    def test_dropping_one_echo_leaves_the_other_rows_glossed(self):
        rows = [une_ligne(requirement="Annexe VI"),
                une_ligne(requirement=EXIGENCE)]
        sortie = attach(rows, lambda t: ["Annexe VI", GLOSE])
        assert [r.gloss for r in sortie] == ["", GLOSE]

    def test_the_requirement_itself_is_never_touched(self):
        [ligne] = attach([une_ligne(requirement="Annexe VI")], lambda t: ["Annexe VI"])
        assert ligne.requirement == "Annexe VI"


class TestNothingElseOnTheRowMoves:

    def test_the_french_quotation_is_untouched(self):
        [ligne] = attach([une_ligne()], lambda t: [GLOSE])
        assert ligne.requirement == EXIGENCE

    def test_verdict_evidence_and_arithmetic_survive_unchanged(self):
        avant = une_ligne(
            status=Status.EXPIRED,
            stage=Stage.OFFER,
            evidence=Citation(document="Attestation", page=1),
            note="valid today, expired on the submission date",
            points="2/2",
            slack=-9,
        )
        [apres] = attach([avant], lambda t: [GLOSE])
        assert replace(apres, gloss="") == avant


class TestItFailsIntoTheReportWeWouldHavePrinted:
    """Fail-open, deliberately. A translation that did not arrive is a missing
    convenience; a report that did not arrive is a lost bid."""

    def test_a_translator_that_raises_leaves_the_rows_alone(self):
        def casse(textes):
            raise RuntimeError("no network")

        rows = [une_ligne()]
        assert attach(rows, casse) == rows

    def test_a_translator_that_loses_count_is_refused_wholesale(self):
        rows = [une_ligne(requirement="un"), une_ligne(requirement="deux")]
        assert attach(rows, lambda t: ["only one"]) == rows

    def test_a_blank_translation_leaves_the_row_without_a_gloss(self):
        [ligne] = attach([une_ligne()], lambda t: ["   "])
        assert ligne.gloss == ""

    def test_a_translator_returning_none_is_refused(self):
        rows = [une_ligne()]
        assert attach(rows, lambda t: None) == rows


class TestTheGlossCannotBecomeEvidence:
    """The one rule that matters: this module may not touch a verdict."""

    def test_it_reaches_for_no_module_that_decides_anything(self):
        import ast
        import pathlib

        source = pathlib.Path("tender_compliance/english.py").read_text(encoding="utf-8")
        arbre = ast.parse(source)
        importes = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.ImportFrom) and noeud.module:
                importes.add(noeud.module)
            elif isinstance(noeud, ast.Import):
                importes.update(a.name for a in noeud.names)

        for interdit in ("tender_compliance.obligations",
                         "tender_compliance.evidence",
                         "tender_compliance.validity",
                         "tender_compliance.capacity"):
            assert interdit not in importes, (
                f"{interdit} decides something; a translation module that can "
                f"reach it can eventually be asked to")

    def test_it_names_neither_anchor_nor_resolve(self):
        import pathlib

        source = pathlib.Path("tender_compliance/english.py").read_text(encoding="utf-8")
        code = "\n".join(l for l in source.splitlines() if not l.strip().startswith("#"))
        for nom in ("anchor(", "resolve(", "verify("):
            assert nom not in code, f"{nom} appears in the translation module"


class TestTheBatchedTranslator:
    """`translator` groups requirements into one call, the way the evidence
    phase does, and refuses an answer it cannot align."""

    class FauxAgent:
        def __init__(self, reponses):
            self._reponses = reponses

        def structured_output(self, schema, prompt):
            return schema(lines=self._reponses)

    def test_it_returns_one_string_per_requirement(self):
        traduire = translator(lambda tools=None: self.FauxAgent(["one", "two"]))
        assert traduire(["un", "deux"]) == ["one", "two"]

    def test_an_answer_of_the_wrong_length_is_refused(self):
        traduire = translator(lambda tools=None: self.FauxAgent(["one"]))
        with pytest.raises(ValueError):
            traduire(["un", "deux"])

    def test_the_agent_is_given_no_tools(self):
        recu = []

        def fabrique(tools=None):
            recu.append(tools)
            return self.FauxAgent(["one"])

        translator(fabrique)(["un"])
        assert recu == [None] or recu == [[]], (
            "a translator with tools could read the tender and start deciding")


class TestTheGlossActuallyReachesTheRun:
    """Wiring, tested on purpose.

    The tools in `tools.py` were written, tested and reached no agent at all;
    329 tests stayed green while the feature did nothing. A module nobody calls
    passes every test it has.
    """

    @staticmethod
    def _code(nom: str) -> str:
        import ast
        import pathlib

        arbre = ast.parse(pathlib.Path(nom).read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, (ast.Module, ast.FunctionDef, ast.ClassDef,
                                  ast.AsyncFunctionDef)):
                corps = noeud.body
                if (corps and isinstance(corps[0], ast.Expr)
                        and isinstance(corps[0].value, ast.Constant)
                        and isinstance(corps[0].value.value, str)):
                    corps[0].value.value = ""
        return ast.unparse(arbre)

    def test_the_cli_attaches_a_gloss_to_the_rows_it_prints(self):
        code = self._code("tender_compliance/__main__.py")
        assert "attach(" in code, "nothing in the CLI calls attach"
        assert "translator(" in code, "the CLI attaches nothing model-backed"
        assert "rows=attach(" in code, (
            "attach is called but its result is not put back on the analysis")

    def test_it_can_be_switched_off(self):
        code = self._code("tender_compliance/__main__.py")
        assert "no_gloss" in code, (
            "the translation costs a call; a run must be able to skip it")

    def test_the_terminal_output_prints_it(self):
        from tender_compliance.__main__ import render as render_text
        from tender_compliance.tender import Analysis
        from tender_compliance.coverage import measure
        from datetime import date

        lignes = [une_ligne(gloss="Proof of professional indemnity insurance")]
        texte = render_text(Analysis(document="rc.pdf", deadline=date(2026, 10, 9),
                                     rows=lignes, counted=measure(lignes)))
        assert "Proof of professional indemnity insurance" in texte
        assert EXIGENCE[:40] in texte, "the quotation must still be the line above"

    def test_the_terminal_output_omits_it_when_absent(self):
        from tender_compliance.__main__ import render as render_text
        from tender_compliance.tender import Analysis
        from tender_compliance.coverage import measure
        from datetime import date

        lignes = [une_ligne()]
        texte = render_text(Analysis(document="rc.pdf", deadline=date(2026, 10, 9),
                                     rows=lignes, counted=measure(lignes)))
        assert " EN " not in texte


ANGLAIS = ("The tenderer shall provide proof of professional indemnity "
           "insurance valid on the date of submission.")


class TestARequirementAlreadyInEnglishIsLeftAlone:
    """A translation of English into English is the same line printed twice.

    The decision is made in code, from the words themselves. Asking the model
    which language it is looking at would put a model in charge of what the
    reader sees, and this is exactly the kind of call that does not need one:
    function words separate French from English sharply, and a counter can be
    read, tested and argued with.
    """

    def test_an_english_requirement_is_never_sent_to_the_translator(self):
        recu = []

        def enregistre(textes):
            recu.append(list(textes))
            return [t.upper() for t in textes]

        attach([une_ligne(requirement=ANGLAIS)], enregistre)
        assert recu == [], "an English line was sent away to be translated"

    def test_and_it_carries_no_gloss(self):
        [ligne] = attach([une_ligne(requirement=ANGLAIS)], lambda t: ["x"])
        assert ligne.gloss == ""

    def test_a_wholly_english_document_costs_no_call_at_all(self):
        appels = []

        def compte(textes):
            appels.append(textes)
            return list(textes)

        attach([une_ligne(requirement=ANGLAIS),
                une_ligne(requirement="The candidate must be registered in the "
                                      "trade register of the member state.")], compte)
        assert appels == []

    def test_a_french_requirement_still_gets_one(self):
        [ligne] = attach([une_ligne()], lambda t: [GLOSE])
        assert ligne.gloss == GLOSE


class TestABilingualFileIsHandledLineByLine:
    """Per row, not per document: a pack that quotes an English annex inside a
    French règlement is one file with two languages in it."""

    def test_only_the_foreign_rows_are_sent(self):
        recu = []

        def enregistre(textes):
            recu.append(list(textes))
            return ["TRADUIT"] * len(textes)

        attach([une_ligne(requirement=ANGLAIS),
                une_ligne(requirement=EXIGENCE)], enregistre)
        assert recu == [[EXIGENCE]]

    def test_the_gloss_lands_on_the_row_it_belongs_to(self):
        anglaise, francaise = attach(
            [une_ligne(requirement=ANGLAIS), une_ligne(requirement=EXIGENCE)],
            lambda t: [GLOSE])
        assert anglaise.gloss == ""
        assert francaise.gloss == GLOSE

    def test_a_misaligned_answer_still_refuses_the_whole_batch(self):
        rows = [une_ligne(requirement=ANGLAIS),
                une_ligne(requirement="un"),
                une_ligne(requirement="deux")]
        assert attach(rows, lambda t: ["one"]) == rows


class TestWhatTheCounterCallsEnglish:
    looks_english = staticmethod(looks_english)

    def test_real_french_tender_prose(self):
        for phrase in (
            "Lettre de candidature ou formulaire DC1, dûment rempli et daté",
            "Les candidatures incomplètes ou demeurées incomplètes à la suite "
            "d'une demande de compléments sont éliminées.",
            "ne retiendra que les candidats dont le chiffre d'affaires du dernier "
            "exercice disponible est supérieur ou égal à 138 000 000 euros hors taxe",
        ):
            assert not self.looks_english(phrase), phrase

    def test_real_english_tender_prose(self):
        for phrase in (
            ANGLAIS,
            "Bidders are required to submit a copy of the certificate of "
            "incorporation together with the completed form of tender.",
            "The contracting authority will exclude any bidder that has not "
            "provided the information listed in section 4 of this document.",
        ):
            assert self.looks_english(phrase), phrase

    def test_the_short_lines_a_thin_word_list_got_wrong(self):
        """Both observed on the European Parliament pack, 2026-09-04, where they
        were translated into themselves. Five English words carry one or two
        function words, so a list missing the common ones does not lose accuracy
        on short lines — it gets them backwards."""
        for phrase in ("employ fewer than 250 persons",
                       "an annual balance sheet total not exceeding "
                       "EUR 43 million."):
            assert self.looks_english(phrase), phrase

    def test_a_bare_noun_phrase_is_beyond_this_counter_and_says_so(self):
        """"financial data sheet fully completed (Annex VII);" — third of the
        three, and the one no word list can reach: it contains not a single
        function word in either language. Counting them cannot decide it, and
        pretending otherwise would mean guessing.

        So it is sent to the translator, and what comes back is judged instead.
        That division of labour is the design, not a gap in it — and it is why
        `_ajoute_quelque_chose` exists rather than being a nicety.
        """
        phrase = "financial data sheet fully completed (Annex VII);"
        assert not self.looks_english(phrase)
        [ligne] = attach([une_ligne(requirement=phrase)],
                         lambda t: ["1. financial data sheet fully completed "
                                    "(Annex VII);"])
        assert ligne.gloss == ""

    def test_the_words_that_are_french_too_are_kept_out(self):
        """`a`, `on`, `or`, `but` and `car` are ordinary French words, and the
        list must not contain them. Asserted on the list itself as well as on a
        sentence: the ratio hides the mistake on any line carrying French
        markers, so a behavioural test alone would pass with them included and
        prove nothing.
        """
        from tender_compliance.english import _ANGLAIS

        for mot in ("a", "on", "or", "but", "car"):
            assert mot not in _ANGLAIS, f"{mot!r} is a French word too"

        # Zero French markers in this one, so the ratio cannot rescue it: with
        # « on » and « a » counted as English, it flips.
        assert not self.looks_english("On a joint deux pieces")

    def test_one_english_word_is_not_evidence(self):
        """Why the bar is two. These files quote English annex titles inside
        French lines, and « Annexe » and « Bordereau » are nouns, not markers —
        so there is nothing French for the ratio to weigh against. At a bar of
        one, both of these lose the gloss they exist for.
        """
        for phrase in ("Annexe « Terms and Conditions »",
                       "Bordereau « Scope of Work » à compléter"):
            assert not self.looks_english(phrase), phrase

    def test_an_undecidable_line_is_translated_rather_than_skipped(self):
        # A missing gloss makes a row unreadable; a redundant one is only
        # clutter. When the counter cannot tell, it errs toward the reader.
        for phrase in ("DC1", "", "SIRET 123 456 789", "2026-10-28"):
            assert not self.looks_english(phrase), phrase

    def test_french_wearing_english_words_is_still_french(self):
        # These files are full of URLs, form codes and borrowed nouns.
        phrase = ("Le candidat transmet son DUME via le portail e-Marchés "
                  "Publics, format PDF, en cas de non-assujettissement à la TVA")
        assert not self.looks_english(phrase)

    def test_it_ignores_case_and_punctuation(self):
        assert self.looks_english("THE TENDERER SHALL PROVIDE THE CERTIFICATE.")
        assert not self.looks_english("LES CANDIDATURES INCOMPLÈTES SONT ÉLIMINÉES.")


class TestFrenchThatQuotesEnglish:
    """The case that defeats a naive counter, and the reason for the ratio.

    These files quote English clause titles, product names and licence terms
    inside French sentences. A rule that says "two English function words means
    English" calls those lines English and drops the gloss on exactly the rows a
    reader most needs it for. Both tests below pass under the real rule and fail
    under the tempting simpler ones — which is why they are here.
    """

    def test_a_french_sentence_quoting_an_english_clause_stays_french(self):
        # Five English function words — the, shall, be, for, all — inside an
        # ordinary French requirement. Counting them alone would flip it.
        phrase = ("Le candidat joint la clause « The supplier shall be liable "
                  "for all damages » traduite en français.")
        assert not looks_english(phrase)

    def test_elisions_are_what_keeps_a_sparse_french_line_french(self):
        # Barely any French function words survive here: « d' » and « un ». The
        # elided d is half of the evidence, and without counting it this line
        # reads as English on three borrowed words.
        phrase = ("Copie d'un contrat-cadre intitulé « Master Services "
                  "Agreement for the supply of licences »")
        assert not looks_english(phrase)


class TestTheCounterOnTheRealFiles:
    """Every sentence of both consultation files, checked in one go.

    The unit cases above are chosen, and chosen cases flatter a detector. These
    are the two published tenders in the repository, split into sentences: any
    one of them classified English would silently lose its gloss in a run, and
    nobody would see a thing go wrong — a missing translation looks exactly like
    a translation that was not needed.
    """

    @staticmethod
    def _phrases(nom):
        import re
        import pathlib

        from tender_compliance.extraction import read

        racine = pathlib.Path(__file__).resolve().parent.parent
        source = read(racine / "samples" / "real_dce" / nom)
        for page in source.pages:
            for phrase in re.split(r"(?<=[.;])\s+", page.text or ""):
                phrase = " ".join(phrase.split())
                if 40 < len(phrase) < 300:
                    yield phrase

    @pytest.mark.parametrize("nom", ["rc_ANTAI_2026.pdf", "rc_2026SDCRH05.pdf"])
    def test_not_one_sentence_of_a_french_tender_reads_as_english(self, nom):
        phrases = list(self._phrases(nom))
        assert len(phrases) > 50, f"only {len(phrases)} sentences — check the split"
        faux = [p for p in phrases if looks_english(p)]
        assert faux == [], f"{len(faux)} of {len(phrases)} classified English: {faux[:3]}"

    # The other direction, on the two English packs. The counts are exact rather
    # than a percentage, because a percentage hides which sentence moved.
    #
    # The single exception in the EFSA file is a digital-signature block —
    # "deseze@efsa.europa.eu C = IT O = EFSA OU = ASSESS Date: ..." — which is a
    # distinguished name, not a sentence, and which the counter reads as French
    # on « ou » and « de ». It is allowed to stay wrong: no requirement is ever
    # written that way, and the cost of being wrong here is one redundant line.
    @pytest.mark.parametrize("nom, tolere", [("itt_EP_COMM_2026.pdf", 0),
                                             ("itt_EFSA_2023.pdf", 1)])
    def test_the_prose_of_an_english_tender_reads_as_english(self, nom, tolere):
        phrases = [p for p in self._phrases(nom) if len(p) > 80]
        assert len(phrases) > 50, f"only {len(phrases)} sentences — check the split"
        manques = [p for p in phrases if not looks_english(p)]
        assert len(manques) <= tolere, (
            f"{len(manques)} of {len(phrases)} sentences would carry a redundant "
            f"English gloss: {manques[:3]}")

    def test_an_english_pack_asks_for_no_translation_at_all(self):
        """End to end, on the file rather than on chosen sentences: the rows a
        run would produce from this pack reach the translator empty-handed."""
        from tender_compliance.coverage import Citation, Row, Status

        phrases = [p for p in self._phrases("itt_EP_COMM_2026.pdf") if len(p) > 80]
        rows = [Row(requirement=p, source=Citation(document="itt.pdf", page=1),
                    status=Status.MISSING) for p in phrases]
        appels = []

        def compte(textes):
            appels.append(list(textes))
            return list(textes)

        assert attach(rows, compte) == rows
        assert appels == [], f"{len(appels[0])} English lines sent to be translated"


class TestLinksAreNotProse:
    """A URL is not written in any language, and it votes.

    `.../budget/explained/management/protecting/protect_en.cfm` tokenises into a
    dozen words, one of which is « en ». That single fragment was enough to drag
    an English sentence back over the line, and these files are full of links —
    the French DC1 requirement carries `economie.gouv.fr` inside the sentence
    that states it. Addresses are stripped before anything is counted.
    """

    def test_an_english_sentence_ending_in_a_url_is_still_english(self):
        assert looks_english(
            "For more information, see the Privacy Statement on "
            "http://ec.europa.eu/budget/explained/management/protecting/protect_en.cfm")

    def test_a_french_requirement_carrying_a_url_is_still_french(self):
        assert not looks_english(
            "Lettre de candidature ou formulaire DC1 (téléchargeable à partir du "
            "lien https://www.economie.gouv.fr/daj/formulaires-declaration-candidat)")

    def test_an_email_address_does_not_vote_either(self):
        assert looks_english(
            "The tenderer shall send the signed form to the address "
            "procurement.de.la@example.eu before the deadline stated above.")

    def test_a_short_english_line_a_french_link_would_flip(self):
        """The two cases above stopped being decisive on 2026-09-04, when the
        English word list grew: both sentences now carry enough English to win
        the ratio even with the link counted, so they pass either way.

        A short line has no such margin. Four words of English against a path
        that spells out « le », « du » and « en » loses — and this is the shape
        a requirement actually takes: an instruction and a link.
        """
        assert looks_english(
            "See the guide at "
            "https://www.economie.gouv.fr/daj/le-guide-du-candidat-en-ligne")
        assert looks_english(
            "Send the form to marche.du.candidat@example.fr")
