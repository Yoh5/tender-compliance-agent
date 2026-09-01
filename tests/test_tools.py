"""The tools may read and check. They may never judge.

WHY THIS FILE IS MOSTLY A RULE, NOT A LIST OF CASES

Giving an agent tools is the moment this project is most likely to lose the
property it is built on. The rule — the model observes, the code decides — lives
in the prompts and in the pipeline, and neither of those stops someone from
adding a tool called `has_this_expired`. A tool is a hole in the boundary, and
the hole is opened one convenient function at a time.

So the boundary is asserted here, over the module's own source, and the
behavioural tests exist mainly to prove the rule is not vacuous.

WHAT THE TOOLS ARE

The same deterministic checks the pipeline already applies AFTER the model
answers: `obligations.anchor`, and the library membership test that
`evidence.resolve` performs. Exposing them changes what the model can find out
before it commits; it changes nothing about what is enforced afterwards. The
last test in this file is the one that matters: the rejection path still runs
whether or not the tool was ever called.

    python -m pytest tests/test_tools.py -q
"""
import re
from datetime import date
from pathlib import Path

import pytest

from tender_compliance.extraction import Source
from tender_compliance.obligations import Proposal, anchor
from tender_compliance.tools import library_tools, reading_tools
from tender_compliance.validity import Document


# A real sentence from a French consultation file: the tools must cope with
# accents and with the line breaks a PDF extractor leaves behind.
PAGE_13 = (
    "2° Une déclaration sur l'honneur pour justifier qu'il n'entre\n"
    "dans aucun des cas mentionnés aux articles L. 2141-1 à L. 2141-5\n"
    "du code de la commande publique."
)
PAGE_14 = "Le candidat produit une attestation d'assurance responsabilité civile."


def _page(number: int, text: str):
    from tender_compliance.extraction import Page

    return Page(number=number, text=text)


@pytest.fixture
def source() -> Source:
    return Source(path=Path("rc.pdf"),
                  pages=[_page(13, PAGE_13), _page(14, PAGE_14)])


@pytest.fixture
def library() -> list[Document]:
    return [
        Document(name="Attestation d'assurance RC pro",
                 issued_on=date(2026, 1, 4), expires_on=date(2026, 10, 19)),
        Document(name="Extrait Kbis", has_expiry=False),
    ]


def _code_only(source: str) -> str:
    """The module's executable code, without comments or docstrings.

    `ast` rather than a regex: a docstring is a string expression in statement
    position, and only the parser knows which strings those are. A regex would
    also strip the tool return strings, which are exactly what must be scanned.
    """
    import ast

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef,
                                 ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", [])
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def _named(tools, name):
    for candidate in tools:
        if candidate.tool_name == name:
            return candidate
    raise AssertionError(f"no tool named {name}: {[t.tool_name for t in tools]}")


class TestTheyAreRealStrandsTools:
    """Stage One of the judging is pass/fail on whether the SDK is really used.

    More to the point for us: a plain function passed to `Agent(tools=[…])` is
    silently ignored, so this is the difference between an agent with tools and
    an agent that looks like it has some.
    """

    def test_every_tool_carries_a_strands_spec(self, source, library):
        for tool in reading_tools(source) + library_tools(library):
            assert tool.tool_name
            assert tool.tool_spec.get("name") == tool.tool_name
            assert tool.tool_spec.get("description")

    def test_each_argument_is_described_for_the_model(self, source):
        # An undescribed argument is one the model fills in by guessing.
        for tool in reading_tools(source):
            schema = tool.tool_spec["inputSchema"]["json"]
            for name, field in schema.get("properties", {}).items():
                assert field.get("description"), f"{tool.tool_name}.{name}"


class TestNoToolEverJudges:
    """The boundary, asserted over the source rather than over behaviour.

    Behaviour tests catch the tools that exist. This catches the one someone
    adds next week.
    """

    # Comments AND docstrings are stripped, for the same reason `test_llm_modeles`
    # strips them in the other repository: prose has to be able to NAME the thing
    # it forbids. This class's own explanation mentions `expires_on`, and caught
    # itself on the first run.
    CODE = _code_only(Path("tender_compliance/tools.py").read_text(encoding="utf-8"))

    def test_no_tool_returns_a_verdict(self):
        # The four words the report uses for its conclusions. A tool that can
        # say any of them has taken the decision out of the code.
        for verdict in ("covered", "missing", "expires too soon", "needs review"):
            assert verdict not in self.CODE.lower(), verdict

    def test_no_tool_computes_with_dates(self):
        # `timedelta`, `date.today`, a subtraction of dates — any of these means
        # arithmetic that belongs to `validity`, done where a model can steer it.
        for forbidden in ("timedelta", "date.today", "expires_on", "issued_on"):
            assert forbidden not in self.CODE, forbidden

    def test_the_library_tools_never_reveal_a_date(self, library):
        # `Document` carries the dates. Listing documents must not pass them on:
        # a model that can see an expiry will be asked about it eventually.
        listing = _named(library_tools(library), "list_documents")()
        assert "2026" not in listing
        assert "Attestation d'assurance RC pro" in listing

    def test_what_the_model_is_TOLD_a_tool_does_promises_no_verdict(
            self, source, library):
        """The other surface, and the one the model actually reads.

        A tool's docstring becomes its description in the spec. Code that never
        judges, described as if it did, would invite the model to ask for a
        judgement — and to treat whatever came back as one.
        """
        for tool in reading_tools(source) + library_tools(library):
            described = tool.tool_spec["description"].lower()
            for verdict in ("covered", "missing", "expired", "still valid",
                            "compliant"):
                assert verdict not in described, (tool.tool_name, verdict)

    def test_no_tool_reaches_the_filesystem(self):
        # A tool taking a path would let the model read something that is not
        # the tender under analysis. Both factories bind their data by closure.
        assert "open(" not in self.CODE
        assert "read_text" not in self.CODE


class TestReadingTheTender:
    def test_a_page_comes_back_verbatim(self, source):
        assert _named(reading_tools(source), "page_text")(13) == PAGE_13

    def test_an_unknown_page_says_so_and_names_the_range(self, source):
        answer = _named(reading_tools(source), "page_text")(99)
        assert "no page 99" in answer
        assert "13" in answer and "14" in answer

    def test_a_long_page_is_truncated_rather_than_poured_back(self):
        from tender_compliance.tools import MAX_PAGE_CHARS

        big = Source(path=Path("x.pdf"), pages=[_page(1, "a" * (MAX_PAGE_CHARS * 2))])
        answer = _named(reading_tools(big), "page_text")(1)
        assert len(answer) < MAX_PAGE_CHARS * 2
        assert "truncated" in answer


class TestCheckingAQuotation:
    def test_a_real_quotation_is_confirmed(self, source):
        check = _named(reading_tools(source), "quote_is_on_page")
        assert check(13, "Une déclaration sur l'honneur pour justifier").startswith("yes")

    def test_an_invented_quotation_is_refused(self, source):
        check = _named(reading_tools(source), "quote_is_on_page")
        answer = check(13, "Le candidat fournit une caution bancaire de 50 000 euros")
        assert answer.startswith("no")

    def test_the_right_words_on_the_wrong_page_are_refused(self, source):
        # The whole point of citing a page. This is the failure the pipeline
        # rejects after the fact, and the tool must not be softer about it.
        check = _named(reading_tools(source), "quote_is_on_page")
        assert check(14, "déclaration sur l'honneur pour justifier qu'il n'entre").startswith("no")

    def test_an_empty_quotation_is_refused(self, source):
        check = _named(reading_tools(source), "quote_is_on_page")
        assert check(13, "   ").startswith("no")

    def test_the_tool_agrees_with_the_pipeline_exactly(self, source):
        """The tool must never be more permissive than `anchor`.

        If it were, a quotation the tool blessed would still be rejected from
        the report — and a model told to trust the tool would keep producing
        rejections it had been assured were fine.
        """
        check = _named(reading_tools(source), "quote_is_on_page")
        for page, quote in [
            (13, "Une déclaration sur l'honneur"),
            (13, "articles L. 2141-1 à L. 2141-5 du code de la commande publique"),
            (13, "une caution bancaire"),
            (14, "attestation d'assurance responsabilité civile"),
            (14, "déclaration sur l'honneur"),
            (99, "quoi que ce soit"),
        ]:
            tool_said_yes = check(page, quote).startswith("yes")
            pipeline_said_yes = anchor(Proposal(text=quote, page=page), source)
            assert tool_said_yes == pipeline_said_yes, (page, quote)


class TestTheLibrary:
    def test_the_catalogue_is_exact(self, library):
        listing = _named(library_tools(library), "list_documents")()
        assert "- Attestation d'assurance RC pro" in listing
        assert "- Extrait Kbis" in listing

    def test_an_empty_library_says_so(self):
        assert "empty" in _named(library_tools([]), "list_documents")()

    def test_an_exact_name_is_confirmed(self, library):
        check = _named(library_tools(library), "document_is_in_library")
        assert check("Extrait Kbis").startswith("yes")

    def test_a_near_miss_is_refused_and_the_spelling_given(self, library):
        # The model's favourite mistake: the right paper, adapted wording. The
        # report drops it as an invented document, so the tool hands back the
        # spelling instead of quietly accepting.
        check = _named(library_tools(library), "document_is_in_library")
        answer = check("extrait kbis")
        assert answer.startswith("no")
        assert "Extrait Kbis" in answer

    def test_an_unknown_name_is_refused(self, library):
        check = _named(library_tools(library), "document_is_in_library")
        answer = check("Caution bancaire")
        assert answer.startswith("no")
        assert "list_documents" in answer


class TestTheToolsDoNotReplaceTheVerification:
    """The one that matters.

    A tool the model never calls, or calls and ignores, must change nothing. If
    the rejection path could be bypassed by adding a tool, the tools would have
    become the enforcement — and the enforcement would then depend on a model
    choosing to use them.
    """

    def test_an_unanchored_proposal_is_still_rejected(self, source):
        from tender_compliance.obligations import verify

        invented = Proposal(text="Le candidat fournit une caution de 50 000 euros",
                            page=13)
        extraction = verify([invented], source)
        assert not extraction.obligations
        assert extraction.rejected

    def test_the_pipeline_never_imports_the_tools_to_decide(self):
        # `tender.py` builds them; `obligations.py` and `evidence.py` — the two
        # modules that decide — must not know they exist.
        for module in ("obligations.py", "evidence.py", "validity.py"):
            text = Path("tender_compliance", module).read_text(encoding="utf-8")
            assert "tools" not in re.findall(r"^from tender_compliance\.(\w+)",
                                             text, re.MULTILINE)
