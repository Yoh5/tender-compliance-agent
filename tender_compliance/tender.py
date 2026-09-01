"""The pipeline: a consultation file in, a checked compliance matrix out.

Reading PDFs used to live here. It moved to `extraction.py` when that module
grew the ability to say what it could *not* read, and a second page reader would
now be a second place for an off-by-one to hide. What remains is the part that
was always the point — putting the pieces in order and refusing to emit a report
the pieces do not support.

WHERE THE MODEL SITS

Twice, and only twice:

    pages ──▶ [model proposes obligations] ──▶ obligations.verify ──▶ obligations
    obligation ──▶ [model proposes evidence] ──▶ evidence.resolve ──▶ match
    match ──▶ validity.assess (arithmetic) ──▶ row

Everything after each arrow is deterministic. The model never sees a date
calculation, never decides a status, and never has its output reach the matrix
without passing a verification step that can reject it.

WHY THE PROPOSERS ARE PARAMETERS

`analyse` takes them as arguments rather than building them. That is what lets
the entire pipeline be tested end to end with no model, no key and no network —
and it is the same reason the two modules underneath do it. A pipeline that can
only be exercised by paying an API call is a pipeline whose behaviour nobody
checks on the cases that matter.

THE REPORT VALIDATES ITSELF, AND REFUSES TO PRINT IF IT CANNOT

`coverage.check` looks for rows that claim something they cannot show — covered
without a citation, missing with one, a page below 1. Those are not formatting
problems. They are the tool asserting what it cannot demonstrate, which is the
one thing it promises never to do, so `analyse` raises instead of returning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from tender_compliance.coverage import Measurement, Row, check, measure, ordered
from tender_compliance.evidence import Propose as ProposeEvidence
from tender_compliance.evidence import build as build_rows
from tender_compliance.extraction import Source
from tender_compliance.obligations import Extraction, Obligation, Proposal
from tender_compliance.obligations import Propose as ProposeObligations
from tender_compliance.obligations import extract
from tender_compliance.validity import Document

PAGES_PER_BATCH = 4
"""How many pages go to the model at once.

One page per call keeps page numbers unambiguous and costs thirty-four calls on
a thirty-four-page file. The whole file in one call is one call and loses track
of which page said what — the failure that makes every citation useless. Four is
small enough that the page markers stay attached to their text and large enough
that a requirement split across a page break is still visible in one window.
"""


class ReportError(RuntimeError):
    """The matrix contains a claim it cannot show. Refuse rather than print."""


@dataclass(frozen=True)
class Analysis:
    """Everything one run concluded, and everything it could not."""

    document: str
    deadline: date
    rows: list[Row] = field(default_factory=list)
    """Already ordered: blockers first. Sorted once, here, so no caller has to
    remember to — and so two callers cannot sort differently."""

    counted: Measurement | None = None
    rejected: list[tuple[Proposal, str]] = field(default_factory=list)
    """Proposals the document did not support. Reported, never dropped."""

    unreadable: str = ""
    """The warning from `extraction`, when pages held text stored as images."""

    model: str = ""
    """Which model produced the proposals, for provenance. Never a key."""

    @property
    def headline(self) -> str:
        return self.counted.headline if self.counted else "nothing analysed"

    @property
    def trustworthy(self) -> bool:
        """False when something is known to be missing from the analysis.

        A reader deciding whether to act on this report needs one place to look,
        not three. Unreadable pages and rejected proposals both mean the same
        thing: this matrix is not the whole story.
        """
        return not self.unreadable and not self.rejected


def analyse(
    source: Source,
    library: list[Document],
    deadline: date,
    *,
    today: date,
    propose_obligations: ProposeObligations,
    propose_evidence: ProposeEvidence,
    model: str = "",
    company=None,
) -> Analysis:
    """Run one consultation file against one evidence library.

    `company` carries the figures — turnover, headcount, references — that
    answer the requirements no document can. Without it those requirements fall
    back to the document matcher, which will not find a paper proving a turnover
    of 138 million because none exists.
    """
    found: Extraction = extract(source, propose_obligations)

    rows = build_rows(
        found.obligations, library, deadline, today=today,
        propose=propose_evidence, company=company,
    )

    problems = check(rows)
    if problems:
        raise ReportError(
            "the matrix makes claims it cannot show, so it will not be printed:\n  "
            + "\n  ".join(problems)
        )

    return Analysis(
        document=source.path.name,
        deadline=deadline,
        rows=ordered(rows),
        counted=measure(rows),
        rejected=found.rejected,
        unreadable=found.warning,
        model=model,
    )


# --------------------------------------------------------------------------
# The live half. Everything above runs without a model; everything below is
# what a model is for.
# --------------------------------------------------------------------------

_OBLIGATION_BRIEF = """\
You are reading a French public-procurement consultation file (règlement de la
consultation). List the pieces a CANDIDATE must supply to apply.

HOW THESE DOCUMENTS ARE WRITTEN, WHICH DECIDES HOW TO SPLIT

The required pieces are set out as a list: bullets (•, ➢, -, ·) or numbered
paragraphs (1°, 2°, 3°). ONE LIST ITEM IS ONE ENTRY. Quote the whole item,
including its qualifiers, its parenthesised links and its conditions.

Right — one entry:
  "Lettre de candidature ou formulaire DC1 (téléchargeable à partir du lien
   https://www.economie.gouv.fr/daj/formulaires-declaration-du-candidat) ou
   équivalent, dûment rempli, et daté"

Wrong — the same item cut into pieces:
  "Lettre de candidature ou formulaire DC1"
  "ou équivalent"
  "dûment rempli, et daté"

Wrong — a sentence that only describes the item above it:
  "Ces attestations indiquent le montant, la date et le lieu d'exécution"
  "lors de la transmission de l'acte de candidature"
Those continue the previous item. They belong inside it, not beside it.

THE REST OF THE RULES

- Quote from the page, in French, as written. Never translate or summarise.
- Give the page number exactly as marked in the text below.
- An item can be two words ("DC1, DC2"). Include it.
- Include items that apply only in some cases ("en cas de", "le cas échéant");
  do not decide whether they apply to this bidder.
- Include a stated minimum ("chiffre d'affaires supérieur ou égal à
  138 000 000 euros") as its own entry: it is a requirement even though no
  document answers it.
- SKIP rules about how the procedure works — who may bid, how offers are scored,
  what happens to an incomplete file, how to use the platform — unless they
  require the candidate to supply something.
- Skip anything about performing the contract after award rather than applying
  for it, unless you are unsure; when unsure, include it.
- A page that lists no required piece returns nothing.

Ten well-formed entries beat forty fragments: every entry becomes a line
somebody has to check by hand. Your quotes are verified against the page
afterwards, so quote rather than paraphrase.
"""

_EVIDENCE_BRIEF = """\
You are matching one requirement from a French tender against a company's
evidence library.

Rules:
- Choose only from the document names listed. Never invent one, and never adapt
  a name — reply with the name exactly as listed.
- Names differ from the wording of the requirement: "RC Pro" and "attestation
  d'assurance responsabilité civile professionnelle" are the same paper. That
  judgement is what you are for.
- For each document you name, set `satisfies`: true ONLY if that document, on
  its own, answers the requirement as written. Set it to false for a document
  that is merely related or the closest available. Never set it to true while
  explaining that the document does not in fact answer — say false.
- Returning nothing at all is a correct and common answer. A wrong match costs
  the bidder the tender; a missing one costs them a glance.
- The page is optional. Omit it unless you know which page proves the point.
- Never say whether a document is still valid. Dates are computed elsewhere.
"""


from tender_compliance.tools import library_tools, reading_tools


def _batches(items: list, size: int) -> list[list]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def obligation_proposer(agent_factory, pages_per_batch: int = PAGES_PER_BATCH):
    """A `Propose` for `obligations.extract`, backed by a Strands agent.

    `agent_factory` is called for each batch so every batch starts from an empty
    conversation. Carrying history across batches would let page 30 be answered
    partly from what page 4 said, and the citation would still point at page 30.
    """
    from pydantic import BaseModel, Field

    class _Item(BaseModel):
        text: str = Field(description="the requirement, quoted from the page in French")
        page: int = Field(description="page number as marked in the text")
        performance: bool = Field(
            default=False,
            description="true only if this concerns performing the contract after award",
        )

    class _Answer(BaseModel):
        obligations: list[_Item] = Field(default_factory=list)

    def propose(source: Source) -> list[Proposal]:
        from tender_compliance.coverage import Stage

        proposals: list[Proposal] = []
        for batch in _batches(source.pages, pages_per_batch):
            body = "\n\n".join(
                f"=== PAGE {page.number} ===\n{page.text}" for page in batch
            )
            answer = agent_factory(reading_tools(source)).structured_output(
                _Answer, f"{_OBLIGATION_BRIEF}\n\n{body}"
            )
            for item in answer.obligations:
                proposals.append(Proposal(
                    text=item.text,
                    page=item.page,
                    stage=Stage.PERFORMANCE if item.performance else None,
                ))
        return proposals

    return propose


OBLIGATIONS_PER_CALL = 5
"""How many requirements are matched against the library in one round trip.

One at a time is the obvious design and it re-sends the brief and the whole
catalogue for every requirement. Measured on the 34-page ANTAI file: 40 calls
carrying 65,000 characters to convey 40 short sentences. In groups of five it is
8 calls and 17,000 characters — three quarters less, and on a slow connection
the round trips cost more than the bytes.

Not larger, because each answer has to name the requirement it belongs to, and
a longer list is a longer opportunity to misalign them.
"""


class _EvidenceProposer:
    """Answers several obligations per call, one requirement at a time to the
    caller.

    The batching is invisible to `evidence.build`, which still asks about one
    obligation at a time and still routes every answer through `resolve`. If the
    grouping ever misaligns, the fallback is a single call for that obligation —
    slower, never wrong.
    """

    def __init__(self, agent_factory, group_size: int = OBLIGATIONS_PER_CALL):
        self._agent_factory = agent_factory
        self._group_size = group_size
        self._plan: list = []
        self._cursor = 0

        from pydantic import BaseModel, Field

        class Match(BaseModel):
            index: int = Field(description="the number of the requirement answered")
            document: str = Field(description="a document name copied exactly from the list")
            page: int | None = Field(default=None, description="page proving the point")
            satisfies: bool = Field(
                description="true ONLY if this document answers the requirement as "
                            "written; false if it is merely related or the closest one",
            )
            reason: str = Field(default="", description="one sentence")

        class Answer(BaseModel):
            matches: list[Match] = Field(default_factory=list)

        self._schema = Answer

    def _ask(self, obligations: list, library: list[Document]) -> dict:
        from tender_compliance.evidence import Suggestion

        catalogue = "\n".join(f"- {document.name}" for document in library)
        listing = "\n".join(
            f"{number}. {' '.join(o.text.split())}"
            for number, o in enumerate(obligations, start=1)
        )
        answer = self._agent_factory(library_tools(library)).structured_output(
            self._schema,
            f"{_EVIDENCE_BRIEF}\n\nREQUIREMENTS (answer each by its number; a "
            f"requirement with no answer is simply left out):\n{listing}\n\n"
            f"EVIDENCE LIBRARY:\n{catalogue}",
        )

        found: dict[int, list] = {}
        for match in answer.matches:
            if 1 <= match.index <= len(obligations):
                found.setdefault(match.index - 1, []).append(
                    Suggestion(document=match.document, page=match.page,
                               satisfies=match.satisfies, reason=match.reason)
                )
        return found

    def prepare(self, obligations: list, library: list[Document]) -> None:
        self._plan = []
        self._cursor = 0
        for group in _batches(list(obligations), self._group_size):
            found = self._ask(group, library)
            for position, obligation in enumerate(group):
                self._plan.append((obligation, found.get(position, [])))

    def __call__(self, obligation: Obligation, library: list[Document]):
        if self._cursor < len(self._plan):
            planned, suggestions = self._plan[self._cursor]
            if planned is obligation:
                self._cursor += 1
                return suggestions
        # Out of step with the plan, or never prepared: ask about this one alone.
        return self._ask([obligation], library).get(0, [])


def evidence_proposer(agent_factory, group_size: int = OBLIGATIONS_PER_CALL):
    """A `Propose` for `evidence.build`, backed by a Strands agent."""
    return _EvidenceProposer(agent_factory, group_size)
