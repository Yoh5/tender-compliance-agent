"""The Strands tools the agents may call — readers and checkers, never judges.

WHY THESE EXIST, AND WHY THEY ARE THE ONLY ONES

The rule this project is built on is that the model observes and the code
decides. That rule is easy to state and easy to break, and the way it breaks is
by handing the model a tool that answers a question the code should have
answered. A tool called `is_this_document_still_valid` would put a language
model in charge of a date subtraction, which is exactly the failure the whole
pipeline exists to prevent.

So the line is drawn at the tool boundary, not inside the prompt:

    a tool may READ the tender, READ the library, and CHECK wording.
    a tool may never return a verdict, a date comparison, or a score.

`tests/test_tools.py` enforces that as a rule over this module's source, because
the next tool anyone adds will be added in a hurry.

WHAT THE TOOLS ACTUALLY BUY

They are the SAME deterministic functions the pipeline already applies after the
model has answered — `obligations.anchor` and the library membership test inside
`evidence.resolve`. Exposing them changes nothing about what is enforced; it
changes only WHEN the model finds out.

Before, a quotation that was not on the page it cited was proposed, rejected,
and reported as a rejection. The reader saw a model that had guessed. Now the
agent can check the page first and quote what is actually there. The rejection
path is untouched and still runs — a tool the model chooses not to call, or
calls and ignores, changes nothing about what the report is allowed to assert.
That is the point: the tools are an aid to the proposal, never a substitute for
the verification.
"""
from __future__ import annotations

from strands import tool

from tender_compliance.extraction import Source
from tender_compliance.obligations import Proposal, anchor
from tender_compliance.validity import Document

# A page of a French consultation file runs 2,000–4,000 characters. The cap is
# generous enough that no real page is truncated, and low enough that a bad
# `page` argument cannot pour a whole file back into the conversation.
MAX_PAGE_CHARS = 6000

# Enough to show the model it is on the wrong page, not enough to let it quote
# from the tool result without ever reading the page.
NEIGHBOURHOOD_CHARS = 240


def reading_tools(source: Source) -> list:
    """Tools for the obligation phase: read a page, check a quotation.

    Bound to one `Source` by closure rather than taking a file argument. A tool
    that accepted a path would let the model read something that is not the
    tender under analysis.
    """

    @tool
    def page_text(page: int) -> str:
        """Return the exact text of one page of the consultation file.

        Use this when you are about to quote a requirement and want the wording
        as it actually appears, rather than as you remember it.

        Args:
            page: the page number as printed in the document.
        """
        for candidate in source.pages:
            if candidate.number == page:
                body = candidate.text or ""
                if len(body) > MAX_PAGE_CHARS:
                    return body[:MAX_PAGE_CHARS] + "\n[…page truncated…]"
                return body or f"page {page} carries no extractable text"
        known = [p.number for p in source.pages]
        return (f"no page {page} in this file. It has pages "
                f"{min(known)}–{max(known)}." if known else "this file has no pages")

    @tool
    def quote_is_on_page(page: int, quote: str) -> str:
        """Check whether a wording really appears on the page you intend to cite.

        This is the same check the pipeline applies to your answer afterwards. A
        quotation that fails here will be rejected from the report, so it is
        worth calling before you commit to one. Reflowed line breaks and
        different spacing are tolerated; invented wording is not.

        Args:
            page: the page you intend to cite.
            quote: the wording you intend to quote, in the document's language.
        """
        text = (quote or "").strip()
        if not text:
            return "no: an empty quotation cannot be anchored"

        if anchor(Proposal(text=text, page=page), source):
            return "yes: this wording is on that page"

        for candidate in source.pages:
            if candidate.number == page:
                extract = " ".join((candidate.text or "").split())[:NEIGHBOURHOOD_CHARS]
                return ("no: that wording is not on page "
                        f"{page}. The page begins: {extract!r}")
        return f"no: there is no page {page} in this file"

    return [page_text, quote_is_on_page]


def library_tools(library: list[Document]) -> list:
    """Tools for the evidence phase: the catalogue, and whether a name is in it.

    No tool here reveals an issue or expiry date. `Document` carries them, and
    the temptation to pass them along is precisely what must be resisted: a
    model that can see `expires_on` will eventually be asked whether something
    has expired, and will answer.
    """

    @tool
    def list_documents() -> str:
        """List every document the company holds, by exact name.

        These names are the only ones you may use. A name that is not on this
        list does not exist as far as the report is concerned.
        """
        if not library:
            return "the evidence library is empty"
        return "\n".join(f"- {document.name}" for document in library)

    @tool
    def document_is_in_library(name: str) -> str:
        """Check whether a document name exists, exactly as you intend to write it.

        Matching is exact, because the report resolves your answer against the
        library the same way. A name that is close but not identical counts as
        an invented document and is dropped.

        Args:
            name: the document name you intend to use, copied from the list.
        """
        wanted = (name or "").strip()
        if not wanted:
            return "no: an empty name matches nothing"
        for document in library:
            if document.name == wanted:
                return "yes: that name is in the library, exactly as written"

        lowered = wanted.casefold()
        near = [d.name for d in library if d.name.casefold() == lowered]
        if near:
            return (f"no: the library spells it {near[0]!r}. Copy that spelling "
                    "exactly.")
        return ("no: no document by that name. Call list_documents to see the "
                "names available.")

    return [list_documents, document_is_in_library]
