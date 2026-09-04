"""Several consultation files in one command, without letting them ruin each other.

A bid office does not hold one open tender. It holds four, with four deadlines,
and the question on a Monday morning is not "is this one document in order" but
"which of these four is going to cost me the bid". That is a different command,
not a different tool: each file is still analysed on its own, against its own
deadline, and nothing is pooled. Four tenders do not have a combined obligation
count, and this module never computes one.

THREE THINGS THAT ONLY GO WRONG WHEN THERE IS MORE THAN ONE FILE

`samples/real_dce/*.pdf` reaches python as four arguments under bash and as the
literal string `*.pdf` under PowerShell, which expands wildcards for its own
cmdlets and not for native commands. A demonstration recorded on Windows would
fail on the first command. So the expansion happens here — a folder or a pattern
means the same thing on both shells.

An API call fails sometimes: an ANTAI run died mid-flight on 2026-09-01 and the
retry worked. Documents three and four had nothing to do with that fault, and a
loop that lets an exception out loses them too. Each document is contained, and
what failed is named at the end rather than swallowed.

And the closing summary quotes each analysis's own headline. `coverage.py` gives
the reason: two places building the same sentence eventually build it
differently, and the number in this repository has already gone stale five
times. A summary that recounted would be the sixth.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

SUFFIXES = (".pdf",)
"""What a consultation file looks like from the outside. Matched without regard
to case: `.PDF` is common in packs assembled on Windows."""


@dataclass(frozen=True)
class Outcome:
    """What became of one document. Exactly one of `analysis` and `error` is set."""

    path: Path
    analysis: object | None = None
    error: str = ""

    @property
    def analysed(self) -> bool:
        return self.analysis is not None


def targets(arguments: Sequence[str]) -> list[Path]:
    """The documents to analyse, in the order the caller asked for them.

    Each argument may be a file, a folder, or a wildcard pattern. Folders and
    patterns expand in sorted order so that two runs of the same command
    analyse the same files in the same order; the arguments themselves keep the
    order they were typed, because a rehearsed demonstration should stay
    rehearsed.

    Raises ValueError rather than skipping quietly. A typo that removes one file
    from a batch of four removes the one you were worried about, and a run that
    says nothing about it looks exactly like a clean result.
    """
    trouves: list[Path] = []
    for argument in arguments:
        chemin = Path(argument)
        if any(caractere in argument for caractere in "*?["):
            correspond = _documents(
                Path(chemin.anchor or ".").glob(_motif_relatif(chemin)))
            if not correspond:
                raise ValueError(f"nothing matches {argument}")
            trouves += correspond
        elif chemin.is_dir():
            dedans = _documents(chemin.iterdir())
            if not dedans:
                raise ValueError(f"no consultation file in {argument}")
            trouves += dedans
        elif chemin.is_file():
            trouves.append(chemin)
        else:
            raise ValueError(f"no such file or folder: {argument}")

    if not trouves:
        raise ValueError("no document to analyse")

    # Paying twice for the same file is the one mistake the caller cannot see in
    # the output, because the second report looks exactly like the first.
    vus: dict[Path, None] = {}
    for chemin in trouves:
        vus.setdefault(chemin, None)
    return list(vus)


def _motif_relatif(chemin: Path) -> str:
    """`Path.glob` refuses an absolute pattern, so the anchor is stripped and
    given back as the folder the search starts from."""
    texte = str(chemin)
    return texte[len(chemin.anchor):] if chemin.anchor else texte


def _est_un_document(chemin: Path) -> bool:
    return chemin.is_file() and chemin.suffix.lower() in SUFFIXES


def _documents(entrees: Iterable[Path]) -> list[Path]:
    """The consultation files among these entries, in a stable order.

    Sorted here rather than left to the filesystem. NTFS happens to hand back
    directory entries in name order and ext4 hands them back in hash order, so
    a run on a laptop and the same run in a container would otherwise analyse
    the same folder in two different orders — and write the reports in two
    different orders too, which reads as two different results.
    """
    return sorted(chemin for chemin in entrees if _est_un_document(chemin))


def each(
    paths: Iterable[Path],
    run: Callable[[Path], object],
    *,
    announce: Callable[[int, int, Path], None] | None = None,
) -> list[Outcome]:
    """Analyse each document, and let none of them end the others.

    `KeyboardInterrupt` is deliberately not caught: containment is for the API
    failing, not for the person at the keyboard asking it to stop. A batch that
    swallowed Ctrl-C would answer it by starting the next paid call.
    """
    documents = list(paths)
    issues: list[Outcome] = []
    for rang, chemin in enumerate(documents, start=1):
        if announce:
            announce(rang, len(documents), chemin)
        try:
            issues.append(Outcome(path=chemin, analysis=run(chemin)))
        except Exception as error:  # noqa: BLE001 — reported, never swallowed
            issues.append(Outcome(
                path=chemin, error=f"{type(error).__name__}: {error}"))
    return issues


def destinations(paths: Sequence[Path], directory: Path) -> dict[Path, Path]:
    """Where each report goes, one file per document, no two the same.

    Two buyers can publish `rc.pdf`, and writing both reports to `rc.html` would
    lose the second in a folder that then looks complete. The first keeps the
    plain name; the ones after it are numbered.
    """
    sorties: dict[Path, Path] = {}
    pris: set[str] = set()
    for chemin in paths:
        racine, rang = chemin.stem, 1
        nom = f"{racine}.html"
        while nom in pris:
            rang += 1
            nom = f"{racine}-{rang}.html"
        pris.add(nom)
        sorties[chemin] = directory / nom
    return sorties


def summary(outcomes: Sequence[Outcome]) -> str:
    """One line per document, and not one number this module worked out itself.

    The per-document line is the analysis's own headline. The only figure added
    here is how many documents were analysed out of how many were asked for,
    which is a length rather than a finding.
    """
    if not outcomes:
        return "no document analysed"

    largeur = max(len(o.path.name) for o in outcomes)
    lignes = ["", "─" * 12 + " summary " + "─" * 12]
    for issue in outcomes:
        nom = f"{issue.path.name:<{largeur}}"
        if issue.analysed:
            lignes.append(f"  {nom}  {issue.analysis.headline}")
        else:
            lignes.append(f"  {nom}  FAILED — {issue.error}")

    faits = sum(1 for o in outcomes if o.analysed)
    lignes.append(f"  {faits} of {len(outcomes)} documents analysed.")
    return "\n".join(lignes)
