"""The documents shown on camera are claims like any other, so they get tests.

Four times now this repository has spoken a number that was true when it was
written and false when it was read: 272 tests narrated while the suite ran 307,
307 while it ran 332, 39 obligations for a file that gives 60, and — the worst
of them — "272 TESTS" printed inside the architecture diagram, which is shown
full screen in the video. A count is a property of a run. A diagram is a
drawing. Putting the first inside the second guarantees it goes stale silently.

So: the diagram may not carry a count of anything that a run produces, and it
must name the tools that actually exist. Both rules are checked against the
source of truth rather than against a copy of it.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SCHEMA = RACINE / "docs" / "architecture.svg"
OUTILS = RACINE / "tender_compliance" / "tools.py"


def _ce_qui_est_a_l_ecran() -> str:
    """The drawing minus its comments: only what a viewer can actually read.

    An XML comment explaining the diagram is not a claim made on camera, and a
    test that reads it will fail on the explanation rather than on the drawing.
    """
    schema = SCHEMA.read_text(encoding="utf-8")
    return re.sub(r"<!--.*?-->", " ", schema, flags=re.DOTALL)


def _noms_des_outils() -> set[str]:
    """The @tool functions, read off the module — not a list maintained by hand."""
    source = OUTILS.read_text(encoding="utf-8")
    return set(re.findall(r"@tool\s*\n\s*def (\w+)\(", source))


class TestTheDiagramNamesTheRealTools(unittest.TestCase):

    def test_every_tool_appears_in_the_diagram(self):
        schema = _ce_qui_est_a_l_ecran()
        outils = _noms_des_outils()
        self.assertTrue(outils, "no @tool found — the reader below would pass vacuously")
        for nom in outils:
            self.assertIn(nom, schema,
                          f"the tool {nom} exists in the code and not in the diagram "
                          f"shown on camera")

    def test_the_diagram_invents_no_tool(self):
        schema = _ce_qui_est_a_l_ecran()
        outils = _noms_des_outils()
        for nom in re.findall(r"@tool\s+(\w+)", schema):
            self.assertIn(nom, outils,
                          f"the diagram announces a tool {nom} that no longer exists")


class TestTheDiagramCarriesNoRunningTotal(unittest.TestCase):
    """A drawing may say 4 pages per call — that is a constant. It may not say
    332 tests or 66 obligations — those are outcomes, and they move."""

    MOUVANTS = r"\b\d[\d\s,]*\s*(tests?|obligations?|requirements? found|exigences?)\b"

    def test_no_count_of_tests_or_findings(self):
        schema = _ce_qui_est_a_l_ecran()
        trouve = [m.group(0).strip()
                  for m in re.finditer(self.MOUVANTS, schema, re.IGNORECASE)
                  if not m.group(0).strip().lower().startswith(("5 requirement",
                                                                "4 page"))]
        self.assertEqual(trouve, [],
                         "the diagram states a number that a run produces; it will be "
                         "wrong on the next run and nobody re-reads an SVG")


class TestTheConstantsInTheDiagramAreTheRealOnes(unittest.TestCase):

    def test_batch_sizes_match_the_code(self):
        from tender_compliance import tender
        schema = _ce_qui_est_a_l_ecran()
        self.assertIn(f"{tender.PAGES_PER_BATCH} pages per call", schema)
        self.assertIn(f"{tender.OBLIGATIONS_PER_CALL} requirements per call", schema)


class TestTheTeleprompterSurvivesTheConsole(unittest.TestCase):
    """demo/walkthrough.py is what gets typed on camera. It crashed.

    The script drew a box rule with U+2500 and printed it before shot one. On a
    Windows console still on code page 1252 — the default — that is a
    UnicodeEncodeError on the first line, with the recorder running. The failure
    reproduces exactly by giving the process a non-UTF-8 stdout, which is what
    this test does.
    """

    SCRIPT = RACINE / "demo" / "walkthrough.py"

    def test_it_runs_with_a_cp1252_stdout(self):
        import os
        import subprocess
        import sys

        env = {**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
        # EOF on stdin: the first input() raises, the script says so and exits 0.
        r = subprocess.run([sys.executable, str(self.SCRIPT)], cwd=RACINE, env=env,
                           input="", capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        self.assertNotIn("UnicodeEncodeError", r.stderr)

    def test_every_shot_points_at_a_file_that_exists(self):
        import ast

        arbre = ast.parse(self.SCRIPT.read_text(encoding="utf-8"))
        chaines = [n.value for n in ast.walk(arbre)
                   if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        chemins = [c for c in chaines if c.startswith("samples/")]
        self.assertTrue(chemins, "no sample path found — the check would pass vacuously")
        for chemin in chemins:
            self.assertTrue((RACINE / chemin).exists(),
                            f"shot list points at {chemin}, which is not in the repository")


if __name__ == "__main__":
    unittest.main()
