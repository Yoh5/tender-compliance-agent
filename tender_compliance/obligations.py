"""Pulling obligations out of a consultation file, and refusing the ones that
cannot be found in it.

This is the one place a language model is genuinely the right tool. The
obligations are prose, scattered over thirty pages, and every buyer words the
same requirement differently — no pattern matching survives contact with that.
It is also the one place where a model failure is invisible: a fabricated
requirement reads exactly like a real one.

So the model proposes and the code checks. Every proposal carries a quote and a
page; `anchor()` goes and looks for that quote on that page. A proposal that
cannot be found is not reported as an obligation, no matter how plausible it
sounds. This is not a review step bolted on afterwards — it is the only path
from a proposal to an `Obligation`.

WHAT THE CODE DOES INSTEAD OF THE MODEL

Anything a regular expression can decide, a regular expression decides:

    "de moins de six (6) mois"    -> max_age_months = 6
    "en cas de non-assujettissement à la TVA"  -> conditional
    "ou équivalent" / "Ou PARTIE IV C 1b) du DUME"  -> has alternatives

Asking the model for those is asking it to do arithmetic and classification it
has no advantage at, in a place where being wrong is undetectable.

THE INTERACTION WITH UNREADABLE PAGES, WHICH IS THE INTERESTING PART

`extraction.py` found that page 13 of the ANTAI file stores part of its text as
images. A model shown the rendered page can read "Une déclaration sur
l'honneur"; the text layer cannot. Anchoring that quote against the text layer
therefore fails — and rejecting it would delete a mandatory obligation on the
grounds that we could not read the page it is on.

That is exactly backwards. So a quote that fails to anchor on a page known to be
LOSSY is kept and marked NEEDS_REVIEW, with a note saying why. Unanchored on a
page we read in full stays rejected: there, absence really is evidence.

INVARIANTS, WRITTEN BEFORE THE CODE

1. Every obligation cites a page. One that cannot be located is not returned.
2. Bid stage and performance are separated at extraction, while the surrounding
   text is still available. When context does not settle it, BID wins: a
   performance obligation wrongly marked blocking costs a pointless check, the
   other way round costs the tender.
3. The model never merges or deduplicates. Two obligations that look like one
   are two rows, each with its page.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from tender_compliance.coverage import Citation, Stage
from tender_compliance.extraction import Fidelity, Source

ANCHOR_OVERLAP = 0.6
"""Share of a quote's **consecutive word pairs** that must appear on the page.

Pairs, not words, and that distinction was not a preference — the first version
counted individual words and was fooled by the very document that motivates this
module. Measured on `samples/real_dce/`:

    case                         by word   by pair
    verbatim quote, right page      1.00      1.00
    same quote reflowed             1.00      1.00
    right quote, wrong page         0.15      0.00
    invented requirement            0.50      0.09
    quote of RASTERISED text        0.72      0.26

That fifth row is the one that matters. "Une déclaration sur l'honneur […] aux
articles L. 2141-1 à L. 2141-5" is not in page 13's text layer, yet 72% of its
words are — *une*, *sur*, *des*, *cas*, *aux*, *articles*, *2141* — because
these documents reuse the same forty words throughout. By word it cleared any
usable threshold. By pair it scores 0.26, and every true case scores 1.00.

Word pairs ask the right question: not "does this page use these words" but
"does this page contain this sequence". Not 1.0, because PDF text layers break
words across lines and glue apostrophes to neighbours; the gap between 0.26 and
1.00 is wide enough that the exact value inside it barely matters.
"""

SHORT_QUOTE_WORDS = 4
"""At or below this length, every word must be present rather than a share.

"DC1, DC2" is a complete obligation in the Ville de Paris notice. Two words
cannot carry a meaningful ratio — 0.6 of two words is one word, and one word
matches almost anything.
"""

_NUMBER_WORDS = {
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
    "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11,
    "douze": 12, "dix-huit": 18, "vingt-quatre": 24,
}

_MAX_AGE = re.compile(
    r"(?:de\s+)?moins\s+de\s+"
    r"(?P<word>[a-zéèêà\-]+|\d+)"
    r"\s*(?:\(\s*(?P<digits>\d+)\s*\)\s*)?"
    r"mois",
    re.IGNORECASE,
)

_CONDITIONAL = re.compile(
    r"\b(?:en\s+cas\s+d[eu']|le\s+cas\s+échéant|si\s+le\s+candidat|"
    r"lorsque\s+le\s+candidat|pour\s+les\s+candidats\s+dans\s+l['’]impossibilité)",
    re.IGNORECASE,
)

_ALTERNATIVE = re.compile(
    r"(?:\bou\s+équivalent\b|\bou,?\s+à\s+défaut\b|\bà\s+défaut\b|"
    r"\bou\s+PARTIE\s+[IVX]+\b|\bDUME\b|\btout\s+autre\s+moyen\b)",
    re.IGNORECASE,
)

_PERFORMANCE = re.compile(
    r"\b(?:le\s+titulaire|pendant\s+(?:toute\s+)?l['’]exécution|"
    r"en\s+cours\s+d['’]exécution|durée\s+du\s+marché|chaque\s+mois|mensuel)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Proposal:
    """What the model claims the document requires. Unverified by construction.

    A separate type from `Obligation` on purpose: it makes it impossible to hand
    a model's raw output to the matrix by accident, because the matrix does not
    accept this type.
    """

    text: str
    page: int
    stage: Stage | None = None
    """None means the model would not commit. Invariant 2 resolves it to BID."""


@dataclass(frozen=True)
class Obligation:
    """One requirement, as stated by the consultation file, and located in it."""

    text: str
    """Quoted or closely paraphrased — never summarised into a category. The
    bidder has to recognise it when they open the document at that page."""

    source: Citation
    stage: Stage
    max_age_months: int | None = None
    """Set when the pack demands a recent document ("de moins de 6 mois"), so
    `validity.assess` can apply the age rule. Read from the text by regex,
    applied by code — never asked of the model."""

    conditional: bool = False
    """The obligation applies only in a stated case ("en cas de
    non-assujettissement à la TVA"). Reporting it MISSING for a bidder it does
    not concern is noise, and noise is how a report stops being read."""

    has_alternatives: bool = False
    """The requirement names more than one way to satisfy it ("ou équivalent",
    "ou, à défaut, une déclaration", "Ou PARTIE IV C 1b) du DUME")."""

    anchored: bool = True
    """False only on a page `extraction.py` flagged LOSSY. See the module
    docstring — those are kept for review rather than dropped."""

    note: str = ""


@dataclass(frozen=True)
class Extraction:
    """Everything the extractor concluded, including what it threw away.

    Rejections are returned rather than logged. A silent filter is a filter
    nobody audits, and the whole argument of this project is that the checking
    step is visible.
    """

    obligations: list[Obligation] = field(default_factory=list)
    rejected: list[tuple[Proposal, str]] = field(default_factory=list)
    warning: str = ""
    """Carried up from `extraction.py` when pages could not be read."""

    @property
    def blocking(self) -> list[Obligation]:
        return [o for o in self.obligations if o.stage is Stage.BID]

    @property
    def needing_review(self) -> list[Obligation]:
        return [o for o in self.obligations if not o.anchored]


def _words(text: str) -> list[str]:
    """Lowercase, accent-stripped word tokens.

    Accents are stripped on both sides of the comparison because PDF text layers
    are inconsistent about them, not because they do not matter.
    """
    folded = unicodedata.normalize("NFKD", text.lower())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", folded)


def _pairs(words: list[str]) -> set[tuple[str, str]]:
    return set(zip(words, words[1:]))


def anchor(proposal: Proposal, source: Source) -> bool:
    """Is the quoted text actually on the page the model cited?

    Consecutive word pairs rather than an exact substring: see ANCHOR_OVERLAP.
    A model that reflows a line break has still found the right sentence, and
    one that invents a requirement does not reproduce the document's sequences
    however plausibly it words the result.
    """
    page = _page(source, proposal.page)
    if page is None:
        return False

    quote = _words(proposal.text)
    if not quote:
        return False

    haystack = _words(page.text)

    if len(quote) <= SHORT_QUOTE_WORDS:
        # Too short to carry pairs meaningfully, so demand every word.
        return all(word in set(haystack) for word in quote)

    wanted = _pairs(quote)
    if not wanted:
        return False
    return len(wanted & _pairs(haystack)) / len(wanted) >= ANCHOR_OVERLAP


def _page(source: Source, number: int):
    for page in source.pages:
        if page.number == number:
            return page
    return None


def max_age_months(text: str) -> int | None:
    """Read "de moins de six (6) mois" as 6. Never ask a model to do this."""
    match = _MAX_AGE.search(text)
    if not match:
        return None
    # "six (6) mois" writes the number twice; the digits are authoritative
    # because a document that spells one and prints the other is a document
    # whose author typed the digits last.
    if match.group("digits"):
        return int(match.group("digits"))
    word = match.group("word")
    if word.isdigit():
        return int(word)
    return _NUMBER_WORDS.get(word.lower())


def classify(text: str, proposed: Stage | None) -> Stage:
    """Bid stage unless the wording clearly points at contract performance.

    Invariant 2: when nothing settles it, BID. The two errors are not
    symmetrical — one wastes a check, the other loses the tender.
    """
    if _PERFORMANCE.search(text):
        return Stage.PERFORMANCE
    if proposed is Stage.PERFORMANCE:
        return Stage.PERFORMANCE
    return Stage.BID


def enrich(proposal: Proposal, document: str) -> Obligation:
    """Turn a located proposal into an obligation, deciding everything in code."""
    return Obligation(
        text=proposal.text,
        source=Citation(document=document, page=proposal.page),
        stage=classify(proposal.text, proposal.stage),
        max_age_months=max_age_months(proposal.text),
        conditional=bool(_CONDITIONAL.search(proposal.text)),
        has_alternatives=bool(_ALTERNATIVE.search(proposal.text)),
    )


def verify(proposals: list[Proposal], source: Source) -> Extraction:
    """Keep what the document supports, and say what was dropped and why.

    This is the whole discipline in one function. Nothing reaches the matrix
    without passing through it.
    """
    kept: list[Obligation] = []
    rejected: list[tuple[Proposal, str]] = []
    document = source.path.name

    for proposal in proposals:
        page = _page(source, proposal.page)
        if page is None:
            rejected.append((proposal, f"cites page {proposal.page}, which does not exist"))
            continue

        if anchor(proposal, source):
            kept.append(enrich(proposal, document))
            continue

        if page.fidelity is Fidelity.LOSSY:
            # We know text is missing from this page, so failing to find the
            # quote says nothing about whether the requirement is real.
            kept.append(replace(
                enrich(proposal, document),
                anchored=False,
                note=(
                    f"not found in the text of page {proposal.page}, but part of "
                    f"that page is stored as images — check it by hand rather "
                    f"than trusting either answer"
                ),
            ))
            continue

        rejected.append((
            proposal,
            f"not found on page {proposal.page}, which was read in full",
        ))

    return Extraction(obligations=kept, rejected=rejected, warning=source.warning())


Propose = Callable[[Source], list[Proposal]]
"""How proposals are obtained. Injected so the verification logic — which is
the part that must never be wrong — is testable with no model, key or network."""


def extract(source: Source, propose: Propose) -> Extraction:
    """Read a consultation file and return what it requires of a bidder.

    `propose` is a parameter rather than a hidden import so that the model is a
    replaceable component. The guarantees of this module come from `verify`,
    not from whichever model produced the proposals.
    """
    return verify(propose(source), source)
