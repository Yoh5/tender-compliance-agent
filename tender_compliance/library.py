"""Loading an evidence library — the documents a company can actually produce.

The library is data, not code, and it is deliberately trivial to write by hand:
a bidder should be able to describe what is in their folder without a developer.

ONE RULE WORTH THE FILE'S EXISTENCE

`has_expiry` defaults to **True** when the field is absent.

A missing field means the person filling in the library did not think about it.
Defaulting to "this document never expires" would turn every oversight into a
silent pass — the tool would report VALID on a document nobody has checked. So
an oversight becomes UNKNOWN instead: a line to go and look at, which is what an
oversight deserves.

The cost of that choice is a needless glance. The cost of the other one is the
tender.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from tender_compliance.validity import Document


class LibraryError(ValueError):
    """The library file cannot be trusted — say why, and stop.

    Loading is not the place to be forgiving. A library read with a shrug
    produces a matrix that looks complete and is not.
    """


def _parse_date(value, field: str, name: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise LibraryError(
            f"{name!r}: {field} is {value!r}, which is not a date in YYYY-MM-DD form"
        ) from error


def load(path: str | Path) -> tuple[list[Document], date]:
    """Return the documents and the deadline their dates were chosen against.

    The deadline comes back with them on purpose. A library is only meaningful
    against a submission date, and returning the documents alone would let a
    caller assess them against the wrong one without noticing.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    deadline = _parse_date(raw.get("reference_deadline"), "reference_deadline", "library")
    if deadline is None:
        raise LibraryError(
            "the library has no reference_deadline — dates mean nothing without "
            "the submission date they were chosen against"
        )

    documents = []
    for entry in raw.get("documents", []):
        name = entry.get("name")
        if not name:
            raise LibraryError("a document has no name")
        documents.append(
            Document(
                name=name,
                issued_on=_parse_date(entry.get("issued_on"), "issued_on", name),
                expires_on=_parse_date(entry.get("expires_on"), "expires_on", name),
                # Absent means "not thought about", which is not the same as
                # "never expires". See the module docstring.
                has_expiry=entry.get("has_expiry", True),
                # Where the proof sits inside that document. One page is the
                # overwhelming majority of compliance paperwork.
                page=int(entry.get("page", 1)),
            )
        )

    if not documents:
        raise LibraryError("the library holds no documents")

    return documents, deadline


def missing_by_design(path: str | Path) -> list[str]:
    """Requirements this company knowingly cannot answer.

    Carried in the file rather than inferred, so a demonstration can show
    MISSING rows without waiting for a tender that happens to ask for something
    the library lacks.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return list(raw.get("_deliberately_absent", []))


def profile(path: str | Path):
    """The company's own figures, for the requirements answered by numbers.

    ORDER IS REVERSED HERE, ON PURPOSE

    A library is written by a human, and a human lists financial years the way
    they appear on a balance sheet: oldest first. `capacity.Profile` slices a
    window off the front, so it wants the most recent year first. Reversing at
    the boundary means the file stays natural to write and the arithmetic stays
    correct — and it happens once, here, rather than in whichever caller
    remembers.

    Getting this backwards is silent: it produces a plausible average from the
    wrong three years, and no verdict looks obviously wrong.
    """
    from tender_compliance.capacity import Profile

    raw = json.loads(Path(path).read_text(encoding="utf-8")).get("profile") or {}

    def newest_first(values):
        return list(reversed(values)) if values else None

    turnover = newest_first(raw.get("turnover_last_three_years_eur"))
    headcount = raw.get("headcount")

    return Profile(
        turnover_by_year=turnover,
        references_by_year=newest_first(raw.get("references_by_year")),
        # A single current figure repeated across the window is the honest
        # reading of "headcount: 24" — it is what the company has now, and the
        # file says nothing about earlier years.
        headcount_by_year=[headcount] * 3 if headcount else None,
        specialists_by_year=newest_first(raw.get("specialists_by_year")),
    )
