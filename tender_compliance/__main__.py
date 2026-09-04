"""Run consultation files against one evidence library, from the shell.

    python -m tender_compliance samples/real_dce/rc_ANTAI_2026.pdf
    python -m tender_compliance samples/real_dce --html-dir out

A folder or a wildcard analyses every consultation file it holds, one at a time
and each against its own matrix. Nothing is pooled: four tenders have four
deadlines and four sets of obligations, and a combined count would mean nothing.

This is the only place that reads `.env`, builds a model and spends money. Every
module underneath takes its model as a parameter, so this file is the whole
surface where a run stops being reproducible — which is why it prints what it
used before it prints what it found.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env(path: Path = ROOT / ".env") -> None:
    """Read `.env` into the environment without overriding what is already set.

    Deliberately tiny and dependency-free. Values are never echoed: this file
    is the one place a key is in memory, and printing it would defeat every
    other precaution in the project.
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def render(analysis) -> str:
    """The matrix as text. One line per obligation, blockers first."""
    from tender_compliance.coverage import Status

    mark = {
        Status.MISSING: "MISSING ",
        Status.EXPIRED: "EXPIRED ",
        Status.NEEDS_REVIEW: "REVIEW  ",
        Status.COVERED: "ok      ",
    }

    lines = [
        f"{analysis.document}  ·  deadline {analysis.deadline}  ·  {analysis.model}",
        "",
        analysis.headline,
        "",
    ]
    if analysis.unreadable:
        lines += [f"!! {analysis.unreadable}", ""]

    for row in analysis.rows:
        requirement = " ".join(row.requirement.split())
        lines.append(f"{mark[row.status]} p{row.source.page:<3} {requirement[:96]}")
        if row.gloss:
            # Sous la citation : le marche fait foi, la traduction aide a le lire.
            lines.append(f"{'':>9} EN {row.gloss[:96]}")
        if row.evidence:
            lines.append(f"{'':>9} └─ {row.evidence.document} p{row.evidence.page}")
        if row.note:
            lines.append(f"{'':>9}    {row.note[:96]}")

    if analysis.rejected:
        lines += ["", f"{len(analysis.rejected)} proposal(s) the document did not support:"]
        for proposal, reason in analysis.rejected[:10]:
            quote = " ".join(proposal.text.split())[:70]
            lines.append(f"  · p{proposal.page} {quote!r}: {reason}")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tender_compliance", description=__doc__)
    parser.add_argument("pdf", nargs="+",
                        help="the consultation file(s) to read — a file, a folder "
                             "whose PDFs are all analysed, or a wildcard")
    parser.add_argument("--library", default=str(ROOT / "samples" / "evidence_library.json"))
    parser.add_argument("--deadline", default=None,
                        help="ISO date bids are due; defaults to the library's own. "
                             "One deadline for the whole run: analysing several "
                             "tenders with different deadlines needs several runs")
    parser.add_argument("--today", default=None, help="ISO date to assess against")
    parser.add_argument("--pages", default=None,
                        help="limit to a page range, e.g. 11-15 (for a quick look). "
                             "Applies to every document in the run")
    parser.add_argument("--html", default=None,
                        help="also write a self-contained HTML report to this path "
                             "(one document only)")
    parser.add_argument("--html-dir", default=None,
                        help="write one HTML report per document into this folder, "
                             "named after the document")
    parser.add_argument("--no-gloss", action="store_true",
                        help="skip the English translation of each requirement "
                             "(one extra model call per 20 rows)")
    args = parser.parse_args(argv)

    from tender_compliance.batch import destinations, each, summary, targets

    try:
        documents = targets(args.pdf)
    except ValueError as error:
        print(f"cannot start: {error}", file=sys.stderr)
        return 2

    if args.html and len(documents) > 1:
        # Quatre analyses dans un seul fichier : trois disparaissent, et le
        # fichier restant a l'air d'etre tout le resultat.
        print(f"--html names one file and this run has {len(documents)} documents; "
              f"use --html-dir instead", file=sys.stderr)
        return 2

    load_env()

    from tender_compliance.extraction import Source, read
    from tender_compliance.library import load, profile
    from tender_compliance.model import ConfigurationError, build, choose
    from tender_compliance.tender import (
        analyse,
        evidence_proposer,
        obligation_proposer,
    )

    try:
        choice = choose()
    except ConfigurationError as error:
        print(f"cannot start: {error}", file=sys.stderr)
        return 2

    library, library_deadline = load(args.library)
    company = profile(args.library)
    deadline = date.fromisoformat(args.deadline) if args.deadline else library_deadline
    today = date.fromisoformat(args.today) if args.today else date.today()

    from strands import Agent

    model = build(choice)

    def agent_factory(tools=None):
        # A fresh agent per call: carrying conversation history between batches
        # would let one page be answered partly from another, while the citation
        # still points at the first.
        #
        # `tools` is bound per phase, not per process: the obligation phase gets
        # readers for THIS tender, the evidence phase gets readers for THIS
        # library. A tool that could reach either would let one phase answer
        # with the other's ground truth.
        return Agent(model=model, tools=list(tools or []), callback_handler=None)

    sorties = destinations(documents, Path(args.html_dir)) if args.html_dir else {}
    if args.html_dir:
        Path(args.html_dir).mkdir(parents=True, exist_ok=True)

    def run(pdf: Path):
        """One document, start to finish. Raising here loses this document and
        no other — `each` reports it and moves on to the next."""
        source = read(str(pdf))
        if args.pages:
            first, _, last = args.pages.partition("-")
            low, high = int(first), int(last or first)
            source = Source(path=source.path,
                            pages=[p for p in source.pages if low <= p.number <= high])

        print(f"reading {source.path.name} ({len(source.pages)} pages) with "
              f"{choice.describe()} …", file=sys.stderr)

        analysis = analyse(
            source, library, deadline, today=today,
            propose_obligations=obligation_proposer(agent_factory),
            propose_evidence=evidence_proposer(agent_factory),
            model=choice.describe(),
            company=company,
        )

        if not args.no_gloss:
            # Apres coup, et seulement apres : `analyse` a deja rendu tous ses
            # verdicts. Une traduction qui n'arrive pas laisse le rapport intact —
            # `attach` rend les lignes qu'on lui a donnees.
            from dataclasses import replace

            from tender_compliance.english import attach, translator

            analysis = replace(
                analysis, rows=attach(analysis.rows, translator(agent_factory)))

        print(render(analysis))

        destination = Path(args.html) if args.html else sorties.get(pdf)
        if destination:
            from tender_compliance.report import render as render_html

            destination.write_text(render_html(analysis, today=today), encoding="utf-8")
            # To stderr: stdout is the report, and a caller piping it should not
            # have to strip a progress line out of the middle.
            print(f"wrote {destination}", file=sys.stderr)

        return analysis

    def announce(rank: int, total: int, pdf: Path) -> None:
        if total > 1:
            print(f"\n{'═' * 72}\n[{rank}/{total}] {pdf.name}\n{'═' * 72}")

    outcomes = each(documents, run, announce=announce)

    if len(outcomes) > 1:
        print(summary(outcomes))
    for outcome in outcomes:
        if not outcome.analysed:
            print(f"{outcome.path}: {outcome.error}", file=sys.stderr)

    return 0 if all(outcome.analysed for outcome in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
