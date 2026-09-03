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
        rows = [une_ligne(requirement="un"), une_ligne(requirement="deux")]
        sortie = attach(rows, lambda textes: [t.upper() for t in textes])
        assert [r.gloss for r in sortie] == ["UN", "DEUX"]

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
