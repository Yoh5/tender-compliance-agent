"""Reading a consultation file, and knowing when the reading is incomplete.

WHY THIS MODULE EXISTS

Everything downstream — obligation extraction, evidence matching, the matrix —
consumes text pulled out of a PDF. That step was assumed to be free. It is not.

`samples/real_dce/rc_ANTAI_2026.pdf` is the live règlement de la consultation
for a French Ministry of the Interior IT contract (deadline 28/10/2026). Open
page 13 in any viewer and it reads:

    "2° Une déclaration sur l'honneur pour justifier qu'il n'entre dans aucun
     des cas mentionnés aux articles L. 2141-1 à L. 2141-5 ..."

Ask pypdf, pdfplumber or PyMuPDF for the same page and all three return:

    "2°
     articles L. 2141-1 à L. 2141-5 et L. 2141-7 à L. 2141-"

A mandatory document — the déclaration sur l'honneur, without which the bid is
eliminated at IV.9 — is perfectly legible to a human and invisible to every
extractor tested.

A checklist built on that text is not slightly wrong. It is confidently wrong:
it omits an obligation and reports nothing amiss, which is the exact failure the
whole project exists to prevent.

WHAT IS ACTUALLY HAPPENING, WHICH IS NOT WHAT IT LOOKED LIKE

The first explanation attempted here was that the fonts had broken character
maps, and the detector counted glyphs drawn against characters returned. It
separated the two files cleanly, so it looked right. It was wrong: PyMuPDF's
glyph trace does not contain "honneur" either. That detector was measuring
section headings rendered in a second pass, and agreeing with the truth by
coincidence — worse than failing, because it would have held up in a demo and
broken on the next file.

The real mechanism is visible in the page blocks: runs of text have been
**rasterised into image strips** and pasted back in place, most likely by an
editing or repair tool somewhere in the buyer's pipeline. Page 13 carries ten
such strips, each the width of a phrase and the height of a single line. The
strips are part of what a human reads; the text layer holds only the runs that
escaped.

So the question to ask a PDF is not "did the characters survive" but "is any of
this page a picture of words". That one has a precise answer:

    DGAC  (rc_2026SDCRH05.pdf)     0 strips over 14 pages (its one image is a logo)
    ANTAI (rc_ANTAI_2026.pdf)    261 strips over 34 pages, 10 of them on page 13

THE RULE THIS BUYS

A lossy page can never support an absence. "The tender does not ask for X" and
"we could not read the part that asks for X" are different statements, and only
one of them is safe to act on. So rasterised text does not merely warn: it
forbids the conclusions that depend on having read everything.

Same discipline as `has_expiry` defaulting to True in `library.py`, and as
UNKNOWN in `validity.py`. Silence is not a verdict.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import pymupdf

MAX_STRIP_HEIGHT_RATIO = 2.5
"""How tall an image may be, in multiples of the page median text line, and
still be suspected of being a picture of a line of text.

Generous on purpose. A strip covering two lines is still a strip; a logo or a
diagram is several times taller than this and is not caught.
"""

MIN_STRIP_WIDTH = 25.0
"""Points. Narrower images are bullets, icons, rules and signature marks — too
small to hide a requirement, and common enough that flagging them would make the
warning worthless."""

SCANNED_PAGE_COVERAGE = 0.5
"""Share of a page one image must cover for the page to count as scanned. A page
with no text layer at all is the extreme case of the same problem, and the least
excusable one to miss."""


class Fidelity(str, Enum):
    COMPLETE = "complete"
    """Everything on this page that looks like text is text."""

    LOSSY = "lossy"
    """Part of this page is a picture of words. What it says is unknowable
    without a human or an OCR pass — that is what makes it dangerous."""


@dataclass(frozen=True)
class Page:
    """One page, its text, and the parts of it that are images of text."""

    number: int
    """1-based, so it can be cited to a human without arithmetic."""

    text: str
    rasterised: tuple[tuple[float, float, float, float], ...] = ()
    """Bounding boxes of image blocks shaped like lines of text."""

    scanned: bool = False
    """True when the page is essentially one large picture."""

    @property
    def fidelity(self) -> Fidelity:
        return Fidelity.LOSSY if (self.rasterised or self.scanned) else Fidelity.COMPLETE

    @property
    def unreadable_runs(self) -> int:
        """How many separate pieces of this page cannot be read.

        A count, not a ratio: it orders pages usefully, and it is something a
        human can verify by looking at the page.
        """
        return len(self.rasterised)


@dataclass(frozen=True)
class Source:
    """A consultation document, page by page, with its reading quality."""

    path: Path
    pages: list[Page] = field(default_factory=list)

    @property
    def unreadable(self) -> list[Page]:
        """Pages carrying text nobody read, worst first — a human checking by
        hand should start where the most is hidden."""
        lossy = [page for page in self.pages if page.fidelity is Fidelity.LOSSY]
        return sorted(lossy, key=lambda page: page.unreadable_runs, reverse=True)

    @property
    def complete(self) -> bool:
        """True only when every page was read in full.

        Callers must consult this before reporting that the file does not ask
        for something. An obligation absent from an incompletely read file has
        not been shown to be absent.
        """
        return not self.unreadable

    @property
    def text(self) -> str:
        return "\n".join(page.text for page in self.pages)

    def warning(self) -> str:
        """What to print above a matrix built on this file, or "" if none.

        Named pages, not a ratio: a reader told "page 13" can go and look, and a
        reader told "6% unresolved" cannot.
        """
        if self.complete:
            return ""
        pages = ", ".join(
            str(page.number)
            for page in sorted(self.unreadable, key=lambda page: page.number)
        )
        plural = "s" if len(self.unreadable) > 1 else ""
        return (
            f"{self.path.name}: part of the text is stored as images on "
            f"page{plural} {pages}, so no extractor can read it. Requirements "
            f"stated there are missing from this analysis — read those pages by "
            f"hand before treating any obligation as absent."
        )


def read(path: str | Path) -> Source:
    """Extract a PDF page by page, recording what could not be read."""
    path = Path(path)
    with pymupdf.open(path) as document:
        pages = [_read_page(page, number)
                 for number, page in enumerate(document, start=1)]
    return Source(path=path, pages=pages)


def _read_page(page, number: int) -> Page:
    blocks = page.get_text("rawdict")["blocks"]
    images = [block["bbox"] for block in blocks if block["type"] == 1]
    lines = [line["bbox"]
             for block in blocks if block["type"] == 0
             for line in block["lines"]]

    page_area = abs(page.rect.width * page.rect.height) or 1.0
    scanned = not lines and any(
        _area(box) / page_area >= SCANNED_PAGE_COVERAGE for box in images
    )

    # Without text lines there is no scale to judge a strip against, and the
    # scanned check above has already covered that case.
    line_height = statistics.median(box[3] - box[1] for box in lines) if lines else None
    rasterised = tuple(
        box for box in images
        if line_height is not None
        and (box[3] - box[1]) <= MAX_STRIP_HEIGHT_RATIO * line_height
        and (box[2] - box[0]) > MIN_STRIP_WIDTH
    )

    return Page(
        number=number,
        text=page.get_text(),
        rasterised=rasterised,
        scanned=scanned,
    )


def _area(box) -> float:
    return abs((box[2] - box[0]) * (box[3] - box[1]))
