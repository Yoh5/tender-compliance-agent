"""Four documents in one command, and what that has to survive.

Running the tool over a folder is not a loop with a print statement in it. Three
things go wrong the moment there is more than one file, and all three are worse
in front of a camera than they are at a desk:

  · THE SHELL DOES NOT HELP. `samples/real_dce/*.pdf` is expanded by bash and
    handed to python as four arguments; PowerShell hands the literal string
    `*.pdf` straight through. A tool demonstrated on Windows that only works on
    a Unix shell is a tool that does not work. So the expansion happens here,
    where both shells get the same answer.

  · ONE FAILURE MUST NOT END THE BATCH. An ANTAI run died mid-flight on an API
    error on 2026-09-01 and succeeded on the retry. If document two takes
    documents three and four down with it, a demonstration is over and a working
    day's analysis is lost — for a fault that had nothing to do with them.

  · THE SUMMARY MUST NOT RECOUNT. `coverage.py` says it plainly: two places
    building the same sentence eventually build it differently. The per-document
    line in the summary is the analysis's own headline, or it is a fifth place
    for a number to go stale.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tender_compliance.batch import (
    Outcome,
    _documents,
    destinations,
    each,
    summary,
    targets,
)

RACINE = Path(__file__).resolve().parent.parent
DCE = RACINE / "samples" / "real_dce"


class _Compte:
    """Just enough of a Measurement to carry a headline."""

    def __init__(self, headline: str):
        self.headline = headline


class _Analyse:
    """Just enough of an Analysis for the summary. Deliberately not the real
    one: the summary must work off `headline`, and a stub that cannot count
    proves the summary is not counting either."""

    def __init__(self, document: str, headline: str = "3 obligations · 1 missing"):
        self.document = document
        self.counted = _Compte(headline)
        self.headline = headline


def _dossier(tmp: str, *noms: str) -> Path:
    dossier = Path(tmp)
    for nom in noms:
        (dossier / nom).parent.mkdir(parents=True, exist_ok=True)
        (dossier / nom).write_bytes(b"%PDF-1.4 not a real pdf")
    return dossier


class TestWhichFilesGetAnalysed(unittest.TestCase):

    def test_a_single_file_is_itself(self):
        chemin = DCE / "rc_2026SDCRH05.pdf"
        self.assertEqual(targets([str(chemin)]), [chemin])

    def test_a_directory_gives_the_pdfs_inside_it(self):
        with TemporaryDirectory() as tmp:
            dossier = _dossier(tmp, "b.pdf", "a.pdf")
            self.assertEqual([p.name for p in targets([str(dossier)])],
                             ["a.pdf", "b.pdf"])

    def test_a_listing_is_put_in_order_here_and_not_by_the_filesystem(self):
        """Asserting that `targets` returns a sorted list proves nothing on
        Windows: NTFS hands back directory entries in name order already, so a
        version that sorted nothing would pass. ext4 hands them back in hash
        order, and the same folder would be analysed — and its reports written —
        in a different order on a laptop and in a container.

        So the order is pinned on the function that does the sorting, with an
        input whose order is chosen here rather than by the filesystem.
        """
        with TemporaryDirectory() as tmp:
            dossier = _dossier(tmp, "a.pdf", "m.pdf", "z.pdf")
            melange = [dossier / "z.pdf", dossier / "a.pdf", dossier / "m.pdf"]
            self.assertEqual([p.name for p in _documents(melange)],
                             ["a.pdf", "m.pdf", "z.pdf"])

    def test_a_directory_ignores_what_is_not_a_pdf(self):
        with TemporaryDirectory() as tmp:
            dossier = _dossier(tmp, "a.pdf")
            (dossier / "README.md").write_text("not a tender", encoding="utf-8")
            (dossier / "notes.txt").write_text("nor this", encoding="utf-8")
            self.assertEqual([p.name for p in targets([str(dossier)])], ["a.pdf"])

    def test_an_uppercase_extension_still_counts(self):
        with TemporaryDirectory() as tmp:
            dossier = _dossier(tmp, "A.PDF")
            self.assertEqual([p.name for p in targets([str(dossier)])], ["A.PDF"])

    def test_a_directory_does_not_reach_into_its_subfolders(self):
        """A buyer's folder often holds an `archive/` of last year's pack. Paying
        to analyse it because it sits one level down is not a surprise anyone
        wants on their bill."""
        with TemporaryDirectory() as tmp:
            dossier = _dossier(tmp, "a.pdf", "archive/old.pdf")
            self.assertEqual([p.name for p in targets([str(dossier)])], ["a.pdf"])

    def test_a_wildcard_is_expanded_here_because_powershell_will_not(self):
        with TemporaryDirectory() as tmp:
            dossier = _dossier(tmp, "rc_one.pdf", "rc_two.pdf", "itt_three.pdf")
            trouves = [p.name for p in targets([str(dossier / "rc_*.pdf")])]
            self.assertEqual(trouves, ["rc_one.pdf", "rc_two.pdf"])

    def test_the_order_of_the_arguments_is_kept(self):
        """Not sorted globally: the order typed is the order shown, so a
        rehearsed demonstration stays rehearsed."""
        with TemporaryDirectory() as tmp:
            dossier = _dossier(tmp, "a.pdf", "b.pdf")
            demande = [str(dossier / "b.pdf"), str(dossier / "a.pdf")]
            self.assertEqual([p.name for p in targets(demande)], ["b.pdf", "a.pdf"])

    def test_a_file_named_twice_is_paid_for_once(self):
        with TemporaryDirectory() as tmp:
            dossier = _dossier(tmp, "a.pdf")
            demande = [str(dossier / "a.pdf"), str(dossier), str(dossier / "a.pdf")]
            self.assertEqual(len(targets(demande)), 1)

    def test_a_path_that_does_not_exist_stops_everything(self):
        """Silently analysing three of the four files a typo asked for is the
        expensive kind of quiet: the missing one is the one you needed."""
        with TemporaryDirectory() as tmp:
            dossier = _dossier(tmp, "a.pdf")
            with self.assertRaises(ValueError) as leve:
                targets([str(dossier / "a.pdf"), str(dossier / "absent.pdf")])
            self.assertIn("absent.pdf", str(leve.exception))

    def test_a_folder_with_no_pdf_in_it_is_an_error(self):
        """Named alongside a folder that does hold one, so the failure has to
        come from this argument rather than from the run ending up empty. A
        folder you pointed at and that gave nothing is a mistake worth stopping
        for, even when the other three arguments worked."""
        with TemporaryDirectory() as tmp:
            vide = Path(tmp) / "vide"
            vide.mkdir()
            (vide / "README.md").write_text("no tender here", encoding="utf-8")
            plein = _dossier(str(Path(tmp) / "plein"), "a.pdf")
            with self.assertRaises(ValueError) as leve:
                targets([str(plein), str(vide)])
            self.assertIn("vide", str(leve.exception))

    def test_a_wildcard_matching_nothing_is_an_error(self):
        with TemporaryDirectory() as tmp:
            dossier = _dossier(tmp, "a.pdf")
            with self.assertRaises(ValueError) as leve:
                targets([str(dossier / "a.pdf"), str(dossier / "zz_*.pdf")])
            self.assertIn("zz_", str(leve.exception))

    def test_nothing_asked_for_is_an_error_rather_than_an_empty_run(self):
        with self.assertRaises(ValueError):
            targets([])


class _Explosion(RuntimeError):
    pass


class TestOneFailureDoesNotEndTheBatch(unittest.TestCase):

    def _trois(self):
        return [Path("un.pdf"), Path("deux.pdf"), Path("trois.pdf")]

    def test_the_documents_after_the_failure_are_still_analysed(self):
        def run(chemin: Path):
            if chemin.name == "deux.pdf":
                raise _Explosion("the API said no")
            return _Analyse(chemin.name)

        issues = each(self._trois(), run)
        self.assertEqual([o.analysed for o in issues], [True, False, True])

    def test_the_failure_keeps_what_went_wrong(self):
        def run(chemin: Path):
            raise _Explosion("the API said no")

        issues = each([Path("un.pdf")], run)
        self.assertIn("the API said no", issues[0].error)
        self.assertIn("_Explosion", issues[0].error)

    def test_a_failure_carries_no_analysis(self):
        def run(chemin: Path):
            raise _Explosion("boom")

        self.assertIsNone(each([Path("un.pdf")], run)[0].analysis)

    def test_the_outcomes_come_back_in_the_order_asked_for(self):
        issues = each(self._trois(), lambda chemin: _Analyse(chemin.name))
        self.assertEqual([o.path.name for o in issues],
                         ["un.pdf", "deux.pdf", "trois.pdf"])

    def test_ctrl_c_stops_the_batch(self):
        """Containment is for the API failing, not for the person at the
        keyboard asking it to stop. A batch that swallows Ctrl-C and starts the
        next paid call is a batch nobody can interrupt."""
        def run(chemin: Path):
            raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            each(self._trois(), run)

    def test_each_document_is_announced_before_it_is_run(self):
        """Before, not after: the announcement is a heading over a wait that
        lasts most of a minute. Printed afterwards it labels a report the reader
        has already finished scrolling past."""
        vus = []

        def announce(rang, total, chemin):
            vus.append(f"announce {rang}/{total} {chemin.name}")

        def run(chemin):
            vus.append(f"run {chemin.name}")
            return _Analyse(chemin.name)

        each(self._trois(), run, announce=announce)
        self.assertEqual(vus, ["announce 1/3 un.pdf", "run un.pdf",
                               "announce 2/3 deux.pdf", "run deux.pdf",
                               "announce 3/3 trois.pdf", "run trois.pdf"])

    def test_a_document_that_failed_was_still_announced(self):
        vus = []

        def run(chemin: Path):
            raise _Explosion("boom")

        each(self._trois(), run, announce=lambda r, t, c: vus.append(c.name))
        self.assertEqual(len(vus), 3)


class TestTheSummaryRecountsNothing(unittest.TestCase):

    def test_each_line_is_the_analysis_own_headline(self):
        issues = [Outcome(Path("un.pdf"), _Analyse("un.pdf", "7 obligations · 2 missing"))]
        self.assertIn("7 obligations · 2 missing", summary(issues))

    def test_the_summary_invents_no_total_of_its_own(self):
        """It may say how many documents there were — that is a length, not a
        finding. It may not add up obligations across documents: four tenders
        with different deadlines do not have a combined obligation count."""
        issues = [Outcome(Path("un.pdf"), _Analyse("un.pdf", "3 obligations · 1 missing")),
                  Outcome(Path("deux.pdf"), _Analyse("deux.pdf", "4 obligations · 2 missing"))]
        self.assertNotIn("7 obligations", summary(issues))

    def test_a_document_that_failed_says_so(self):
        issues = [Outcome(Path("un.pdf"), _Analyse("un.pdf")),
                  Outcome(Path("deux.pdf"), error="_Explosion: the API said no")]
        texte = summary(issues)
        self.assertIn("deux.pdf", texte)
        self.assertIn("the API said no", texte)

    def test_the_summary_says_how_many_of_how_many(self):
        issues = [Outcome(Path("un.pdf"), _Analyse("un.pdf")),
                  Outcome(Path("deux.pdf"), error="boom"),
                  Outcome(Path("trois.pdf"), _Analyse("trois.pdf"))]
        self.assertIn("2 of 3", summary(issues))

    def test_every_document_appears(self):
        issues = [Outcome(Path("un.pdf"), _Analyse("un.pdf")),
                  Outcome(Path("deux.pdf"), _Analyse("deux.pdf")),
                  Outcome(Path("trois.pdf"), error="boom")]
        texte = summary(issues)
        for nom in ("un.pdf", "deux.pdf", "trois.pdf"):
            self.assertIn(nom, texte)

    def test_a_run_that_analysed_nothing_still_produces_a_summary(self):
        self.assertIsInstance(summary([]), str)


class TestEachReportGetsItsOwnFile(unittest.TestCase):

    def test_one_html_per_document_named_after_it(self):
        chemins = [Path("a/rc_one.pdf"), Path("b/itt_two.pdf")]
        sorties = destinations(chemins, Path("out"))
        self.assertEqual(sorties[chemins[0]], Path("out") / "rc_one.html")
        self.assertEqual(sorties[chemins[1]], Path("out") / "itt_two.html")

    def test_two_documents_with_the_same_name_do_not_overwrite_each_other(self):
        """Two buyers, two folders, one file name. Losing the second report to
        the first would be silent, and the folder would look complete."""
        chemins = [Path("buyer_a/rc.pdf"), Path("buyer_b/rc.pdf")]
        sorties = destinations(chemins, Path("out"))
        self.assertEqual(len(set(sorties.values())), 2)

    def test_the_first_of_a_pair_keeps_the_plain_name(self):
        chemins = [Path("a/rc.pdf"), Path("b/rc.pdf")]
        sorties = destinations(chemins, Path("out"))
        self.assertEqual(sorties[chemins[0]], Path("out") / "rc.html")

    def test_everything_lands_in_the_directory_asked_for(self):
        chemins = [Path("far/away/rc_one.pdf")]
        sorties = destinations(chemins, Path("some") / "where")
        self.assertEqual(sorties[chemins[0]].parent, Path("some") / "where")


class TestTheBatchIsWiredIntoTheCommandLine(unittest.TestCase):
    """The module can be perfect and unreachable. These read `__main__` itself."""

    def _source(self) -> str:
        return (RACINE / "tender_compliance" / "__main__.py").read_text(encoding="utf-8")

    def test_the_command_line_takes_more_than_one_document(self):
        arbre = ast.parse(self._source())
        nargs = [mot_cle.value.value
                 for noeud in ast.walk(arbre)
                 if isinstance(noeud, ast.Call)
                 and getattr(noeud.func, "attr", "") == "add_argument"
                 for mot_cle in noeud.keywords
                 if mot_cle.arg == "nargs" and isinstance(mot_cle.value, ast.Constant)]
        self.assertIn("+", nargs, "the CLI still accepts exactly one document")

    def test_the_batch_module_is_actually_used(self):
        self.assertIn("tender_compliance.batch", self._source())

    def test_a_single_html_path_is_refused_for_several_documents(self):
        """--html names one file. Handing it four analyses would leave three of
        them on the floor, and the one file left behind would look like the
        whole run."""
        from tender_compliance.__main__ import main

        code = main([str(DCE / "rc_2026SDCRH05.pdf"), str(DCE / "itt_EFSA_2023.pdf"),
                     "--html", "out/whatever.html"])
        self.assertEqual(code, 2)

    def test_the_refusal_happens_before_any_model_is_built(self):
        """If it did not, this test would need an API key to pass — and would
        spend money proving an argument was malformed."""
        arbre = ast.parse(self._source())
        corps = next(n for n in ast.walk(arbre)
                     if isinstance(n, ast.FunctionDef) and n.name == "main")
        texte = ast.unparse(corps)
        self.assertLess(texte.index("--html-dir"), texte.index("choose()"),
                        "the html check must come before the model is chosen")


if __name__ == "__main__":
    unittest.main()
