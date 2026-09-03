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
from tender_compliance.english import attach, translator

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
