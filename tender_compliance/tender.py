"""Reading a tender pack into pages. NOT IMPLEMENTED YET.

Unglamorous and load-bearing: every citation in the report is a page number
produced here, so an off-by-one in this module makes the whole matrix look
checkable while pointing one page beside the truth.

INVARIANT — PAGES ARE 1-BASED, AS PRINTED

PDF libraries index from zero. Buyers, bidders and the documents themselves
count from one. The conversion happens here, once, at the boundary, and
`coverage.check()` refuses any row citing page 0 — the signature of a 0-based
index that leaked.

INVARIANT — A PAGE THAT YIELDS NO TEXT IS REPORTED, NOT SKIPPED

Tender packs are full of scanned annexes. A silently empty page becomes an
obligation nobody extracted, in a report that claims to have read everything.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Page:
    number: int
    """1-based, as printed."""

    text: str


@dataclass(frozen=True)
class Pack:
    """The documents that make up one consultation."""

    name: str
    pages: list[Page]
    unreadable: list[int]
    """Pages that produced no text — scans, most often. Carried explicitly so
    the report can say what it could not read."""


def read(path: str) -> Pack:
    raise NotImplementedError("tender pack reading is not built yet")
