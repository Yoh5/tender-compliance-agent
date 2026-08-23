"""Obligations answered by a number, not by a document.

WHY THIS MODULE EXISTS, AND WHY IT DID NOT AT FIRST

The original design ran every obligation through the same chain: find a
document, check its dates, report. Then two real notices were read (see
`samples/real_requirements.json`) and the chain turned out to miss a whole
family of requirements:

    "Le candidat donne toutes les informations permettant de justifier de son
     chiffre d'affaires annuel global moyen sur les trois derniers exercices"
    "si x est strictement supérieur à 3 124 998 d'euros HT : 2/2"
                                    — Ministère de l'éducation nationale, 22-87951

No document satisfies that. No expiry date decides it. It is a number compared
to a threshold, and the evidence matcher would have reported MISSING on a
company that meets it comfortably.

This is what reading real material buys, and nothing else does: the gap was
invisible from the specification, because the specification was written by
someone imagining how buyers write.

THE RULES ARE THE BUYER'S, THE ARITHMETIC IS OURS

A model may read "supérieur à 3 124 998 euros HT" and tell us the threshold and
whether the comparison is strict. It never performs the comparison. Same reason
as `validity.py`: a model that gets a comparison wrong produces an answer
indistinguishable from one it gets right, and this one decides admissibility.

THE YOUNG-COMPANY PATH IS NOT A FAILURE

    "Pour les candidats dans l'impossibilité, à raison de leur création
     récente, de produire la liste de références susmentionnée, il est demandé
     tout autre moyen de preuve"
                                                  — Ville de Paris, 22-88307

Buyers write this because refusing young firms outright is not what they want.
A company with two years of accounts against a three-year window has not failed
the requirement — it falls on a different path. Reporting MISSING there is wrong
in the direction that costs a bid the bidder could have won, so it reports
NEEDS_REVIEW instead, and says why.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tender_compliance.coverage import Status


class Measure(str, Enum):
    """What the buyer is counting."""

    TURNOVER = "turnover"
    """Euros, over the last N financial years."""

    REFERENCES = "references"
    """Comparable contracts delivered inside the window."""

    HEADCOUNT = "headcount"
    """Average annual staff."""

    SPECIALISTS = "specialists"
    """Staff qualified in the specific field of the contract."""


class Aggregation(str, Enum):
    AVERAGE = "average"
    """"chiffre d'affaires annuel global MOYEN sur les trois derniers exercices"."""

    EACH = "each"
    """Every year in the window must clear the threshold — some buyers write it
    this way, and it is a materially harder test than the average."""

    TOTAL = "total"


@dataclass(frozen=True)
class Threshold:
    """A quantified requirement, as the buyer stated it."""

    measure: Measure
    minimum: float
    window_years: int = 3
    aggregation: Aggregation = Aggregation.AVERAGE
    strict: bool = False
    """True for "strictement supérieur à". The difference matters exactly at the
    boundary, which is where a bidder sits when the buyer has set the threshold
    from the incumbent's figures."""

    points_if_met: str = ""
    """"2/2" and the like. Buyers grade as well as admit, and a bidder can be
    admissible while losing points. Carried through so the report can say so."""


@dataclass(frozen=True)
class Profile:
    """What the company can actually show.

    Every field is a list ordered MOST RECENT FIRST, so a window is a slice.
    Shorter than the window means the company is younger than the window — a
    different situation from falling short, and treated as one.
    """

    turnover_by_year: list[float] | None = None
    references_by_year: list[int] | None = None
    headcount_by_year: list[int] | None = None
    specialists_by_year: list[int] | None = None

    def series(self, measure: Measure) -> list[float] | None:
        return {
            Measure.TURNOVER: self.turnover_by_year,
            Measure.REFERENCES: self.references_by_year,
            Measure.HEADCOUNT: self.headcount_by_year,
            Measure.SPECIALISTS: self.specialists_by_year,
        }[measure]


@dataclass(frozen=True)
class Assessment:
    """The verdict, and the number behind it.

    The number is not decoration. "You are short" sends someone hunting through
    accounts; "average 2.13 M€ against 3.12 M€ required" tells them immediately
    whether this is a rounding argument or a lost cause — and whether adding the
    subcontractor's turnover would close it.
    """

    status: Status
    measured: float | None
    required: float
    explanation: str


def assess(threshold: Threshold, profile: Profile) -> Assessment:
    """Compare what the company can show against what the buyer demands."""
    series = profile.series(threshold.measure)

    if not series:
        return Assessment(
            Status.NEEDS_REVIEW,
            None,
            threshold.minimum,
            f"the company profile carries no {threshold.measure.value} figures — "
            f"nothing can be concluded, which is not the same as falling short",
        )

    window = series[: threshold.window_years]

    # Fewer years than the window: the young-company path, not a failure.
    if len(window) < threshold.window_years:
        return Assessment(
            Status.NEEDS_REVIEW,
            _aggregate(window, threshold.aggregation),
            threshold.minimum,
            f"only {len(window)} of the {threshold.window_years} years required are "
            f"available — buyers usually open an alternative route for recently "
            f"created firms, and it has to be taken rather than reported as missing",
        )

    measured = _aggregate(window, threshold.aggregation)
    met = measured > threshold.minimum if threshold.strict else measured >= threshold.minimum

    if met:
        detail = f"{_render(measured, threshold.measure)} against " \
                 f"{_render(threshold.minimum, threshold.measure)} required"
        if threshold.points_if_met:
            detail += f" — scores {threshold.points_if_met}"
        return Assessment(Status.COVERED, measured, threshold.minimum, detail)

    shortfall = threshold.minimum - measured
    return Assessment(
        Status.MISSING,
        measured,
        threshold.minimum,
        f"{_render(measured, threshold.measure)} against "
        f"{_render(threshold.minimum, threshold.measure)} required — short by "
        f"{_render(shortfall, threshold.measure)}",
    )


def _aggregate(window: list[float], how: Aggregation) -> float | None:
    if not window:
        return None
    if how is Aggregation.AVERAGE:
        return sum(window) / len(window)
    if how is Aggregation.TOTAL:
        return sum(window)
    # EACH: the company is only as good as its worst year in the window.
    return min(window)


def _render(value: float | None, measure: Measure) -> str:
    """Numbers as a human would write them, not as a float prints.

    A report that says "2131666.6666666665 €" is a report that looks like a bug,
    and a reader who thinks they are looking at a bug stops reading.
    """
    if value is None:
        return "unknown"
    if measure is Measure.TURNOVER:
        if value >= 1_000_000:
            return f"{value / 1_000_000:.2f} M€".replace(".", ",")
        return f"{value:,.0f} €".replace(",", " ")
    return f"{value:.0f}".rstrip("0").rstrip(".") if value % 1 else f"{value:.0f}"
