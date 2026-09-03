"""The analysis as a single HTML file, meant to be printed and carried.

WHO IT IS FOR

A bid manager two days before a deadline, with a folder of attestations and no
time. The page has one job: make what blocks the bid impossible to miss, and
make each blocker actionable without opening anything else.

THE DESIGN, AND WHY IT IS THIS ONE

Type carries the argument. The tender's own words are set in a serif, because
they are quotations from an official document and should look like it; our words
are set in a sans, because they are software talking; citations and day counts
are monospaced, because they are coordinates and figures, not prose. A reader
can tell at a glance which sentences the buyer wrote and which the tool did —
that distinction is the whole basis of trusting the report.

The palette is the cold blue-grey of French administrative paper rather than the
warm cream a report defaults to, with one accent: the madder red of an official
stamp, spent only on rows that block the bid. Nothing else in the page is
allowed that colour.

The signature is a number. "Valid today, expired on the submission date" is the
finding this product exists for, and a sentence buries it — so the day count
against the deadline is set large and monospaced next to the evidence: -9 j. It
is the one thing a reader should remember, and it is information rather than
decoration.

SELF-CONTAINED BY NECESSITY

No external stylesheet, font or script. This file is written next to a tender
folder and opened from disk, often on a machine with no network and always by
someone who will not wait for a CDN. It also has to survive being emailed.
"""

from __future__ import annotations

import html
from datetime import date

from tender_compliance.coverage import Row, Stage, Status

_LABEL = {
    Status.MISSING: "missing",
    Status.EXPIRED: "expires too soon",
    Status.NEEDS_REVIEW: "to review",
    Status.COVERED: "covered",
}

_CLASS = {
    Status.MISSING: "blocks",
    Status.EXPIRED: "blocks",
    Status.NEEDS_REVIEW: "review",
    Status.COVERED: "covered",
}

_STYLE = """\
:root {
  color-scheme: light dark;
  --paper:  #f6f8fb;   /* cool administrative stock, not cream */
  --card:   #ffffff;
  --ink:    #14203a;   /* the navy of French official print */
  --muted:  #5b6880;
  --rule:   #ccd6e4;
  --stamp:  #a8243b;   /* madder red; blockers only, nothing else */
  --review: #7d5c12;
  --good:   #2c5f4e;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #0e1524; --card: #141d30; --ink: #e6ecf6; --muted: #93a1ba;
    --rule: #2a3852; --stamp: #ef8093; --review: #d9b25c; --good: #6dc4a5;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 2.5rem 1.25rem 5rem;
  background: var(--paper); color: var(--ink);
  font: 400 15px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
}
main { max-width: 60rem; margin: 0 auto; }

.eyebrow {
  margin: 0 0 .35rem; font-size: .72rem; letter-spacing: .14em;
  text-transform: uppercase; color: var(--muted);
}
h1 {
  margin: 0; font-size: clamp(1.5rem, 4vw, 2.1rem); font-weight: 600;
  letter-spacing: -.015em; overflow-wrap: anywhere;
}
.facts {
  display: flex; flex-wrap: wrap; gap: 1.5rem 2.5rem;
  margin: 1.4rem 0 0; padding: 0 0 1.4rem; border-bottom: 2px solid var(--ink);
}
.facts div { min-width: 0; }
.facts dt {
  font-size: .68rem; letter-spacing: .12em; text-transform: uppercase;
  color: var(--muted);
}
.facts dd {
  margin: .2rem 0 0; font-family: ui-monospace, "Cascadia Mono", Consolas, monospace;
  font-size: .95rem;
}

.verdict { margin: 1.6rem 0 0; font-size: 1.15rem; font-weight: 500; }
.verdict .blocking { color: var(--stamp); }

.caution {
  margin: 1.4rem 0 0; padding: .85rem 1rem;
  border: 1px solid var(--rule); border-left: 3px solid var(--review);
  background: var(--card); font-size: .9rem; color: var(--muted);
}

.matrix { margin: 2rem 0 0; display: grid; gap: .6rem; }

.row {
  background: var(--card); border: 1px solid var(--rule);
  border-left: 3px solid var(--rule);
  padding: 1rem 1.1rem;
  display: grid; grid-template-columns: 8.5rem 1fr; gap: .3rem 1.1rem;
  break-inside: avoid;
}
.row.blocks  { border-left-color: var(--stamp); }
.row.review  { border-left-color: var(--review); }
.row.covered { border-left-color: var(--good); }

.stamp {
  grid-row: 1 / span 3; align-self: start;
  font-size: .68rem; letter-spacing: .1em; text-transform: uppercase;
  font-weight: 600;
}
.blocks  .stamp { color: var(--stamp); }
.review  .stamp { color: var(--review); }
.covered .stamp { color: var(--good); }

.requirement {
  margin: 0; font-family: ui-serif, "Iowan Old Style", "Palatino Linotype",
  Palatino, Georgia, serif;
  font-size: 1.02rem; line-height: 1.5; overflow-wrap: anywhere;
}
/* The translation. Sans-serif against the quotation's serif, muted, and marked
   EN — three signals that this is a rendering of the line above and not a
   second requirement. The document is what counts; this only helps read it. */
.gloss {
  grid-column: 2; margin: .3rem 0 0;
  font-size: .86rem; line-height: 1.45; color: var(--muted);
  padding-left: .6rem; border-left: 2px solid var(--rule);
}
.gloss::before {
  content: "EN"; margin-right: .45rem;
  font-size: .62rem; letter-spacing: .1em; font-weight: 600;
  color: var(--rule); vertical-align: .1em;
}

.where, .note {
  grid-column: 2;
  font-size: .82rem; color: var(--muted); margin: 0;
}
.where { font-family: ui-monospace, "Cascadia Mono", Consolas, monospace; }
.where b { font-weight: 600; color: var(--ink); }

/* The one number worth remembering. */
.slack {
  font-family: ui-monospace, "Cascadia Mono", Consolas, monospace;
  font-size: 1.05rem; font-weight: 600; font-variant-numeric: tabular-nums;
}
.slack.late { color: var(--stamp); }

.grade {
  font-family: ui-monospace, "Cascadia Mono", Consolas, monospace;
  font-size: .78rem; font-weight: 600; color: var(--good);
}
.grade.lost { color: var(--stamp); }

.pile {
  font-size: .7rem; letter-spacing: .04em; text-transform: uppercase;
  padding: .1rem .4rem; border: 1px solid var(--rule); border-radius: 3px;
  color: var(--muted);
}

.dropped { margin: 2.6rem 0 0; }
.dropped h2 {
  font-size: .72rem; letter-spacing: .14em; text-transform: uppercase;
  color: var(--muted); font-weight: 600; margin: 0 0 .7rem;
  padding-bottom: .5rem; border-bottom: 1px solid var(--rule);
}
.dropped li { margin: 0 0 .55rem; font-size: .85rem; color: var(--muted); }
.dropped q { font-family: ui-serif, Georgia, serif; color: var(--ink); }

footer {
  margin: 3rem 0 0; padding-top: 1rem; border-top: 1px solid var(--rule);
  font-size: .78rem; color: var(--muted);
}

@media print {
  body { background: #fff; color: #000; padding: 0; font-size: 11pt; }
  .row { border-color: #999; background: #fff; }
  .caution { background: #fff; }
}
"""


def _escape(text: str) -> str:
    """Everything from a PDF or a model goes through here.

    The requirement text is quoted from a document nobody in this project wrote,
    and the note can carry a model's words. Neither is trusted markup.
    """
    return html.escape(" ".join(str(text).split()))


def _slack(row: Row) -> str:
    if row.slack is None:
        return ""
    late = row.slack < 0
    sign = "" if late else "+"
    return (f'<span class="slack{" late" if late else ""}">'
            f'{sign}{row.slack} d</span>')


def _row(row: Row) -> str:
    parts = [
        f'<article class="row {_CLASS[row.status]}">',
        f'<span class="stamp">{_LABEL[row.status]}</span>',
        f'<blockquote class="requirement">{_escape(row.requirement)}</blockquote>',
    ]
    if row.gloss:
        # Sous la citation et en retrait : le document fait foi, la traduction
        # aide a le lire. L'ordre inverse ferait croire que l'outil a compris le
        # marche plutot qu'il ne l'a cite.
        parts.append(f'<p class="gloss">{_escape(row.gloss)}</p>')

    where = [f'<b>{_escape(row.source.document)}</b> p{row.source.page}']
    if row.stage is Stage.OFFER:
        where.append('<span class="pile">offer — correctable</span>')
    if row.points:
        # Un candidat peut être recevable et perdre le marché aux points. Le
        # verdict seul ne le dit pas ; la note, si.
        gagne = row.status is Status.COVERED
        where.append(
            f'<span class="grade{"" if gagne else " lost"}">'
            f'{"earns" if gagne else "forgoes"} {_escape(row.points)}</span>'
        )
    if row.evidence:
        where.append(f'→ {_escape(row.evidence.document)} p{row.evidence.page}')
    slack = _slack(row)
    if slack:
        where.append(slack)
    parts.append(f'<p class="where">{" &nbsp;·&nbsp; ".join(where)}</p>')

    if row.note:
        parts.append(f'<p class="note">{_escape(row.note)}</p>')
    parts.append("</article>")
    return "\n".join(parts)


def render(analysis, *, today: date | None = None) -> str:
    """One self-contained HTML document. Never touches the filesystem."""
    today = today or date.today()
    days_left = (analysis.deadline - today).days
    blocking = analysis.counted.blocking if analysis.counted else 0
    # Deux nombres, parce qu'ils appellent deux réactions à deux moments.
    # « Les candidatures incomplètes […] sont éliminées » (ANTAI IV.9) contre
    # « l'acheteur PEUT autoriser […] à régulariser les offres irrégulières »
    # (DGAC 6.2) : le même papier manquant clôt le dossier d'un côté et invite
    # une correction de l'autre. Un seul chiffre disait au lecteur de les
    # traiter pareil, ce qui est faux dans les deux sens.
    fatal = analysis.counted.fatal if analysis.counted else 0
    regularisable = analysis.counted.regularisable if analysis.counted else 0

    head = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>Compliance check — {_escape(analysis.document)}</title>",
        f"<style>{_STYLE}</style>",
        "</head><body><main>",
        '<p class="eyebrow">Bid file · compliance check</p>',
        f"<h1>{_escape(analysis.document)}</h1>",
        '<dl class="facts">',
        f"<div><dt>Bids due</dt><dd>{analysis.deadline.isoformat()}</dd></div>",
        f"<div><dt>Days left</dt><dd>{days_left}</dd></div>",
        f"<div><dt>Ends the bid</dt><dd>{fatal}</dd></div>",
        f"<div><dt>Correctable</dt><dd>{regularisable}</dd></div>",
        f"<div><dt>Read by</dt><dd>{_escape(analysis.model or 'not recorded')}</dd></div>",
        "</dl>",
    ]

    verdict = _escape(analysis.headline)
    if blocking:
        verdict = f'<span class="blocking">{verdict}</span>'
    head.append(f'<p class="verdict">{verdict}</p>')

    if analysis.unreadable:
        head.append(f'<div class="caution">{_escape(analysis.unreadable)}</div>')

    body = ['<section class="matrix">']
    body += [_row(row) for row in analysis.rows]
    body.append("</section>")

    if analysis.rejected:
        body.append('<section class="dropped">')
        body.append(f"<h2>{len(analysis.rejected)} proposals the document "
                    f"did not support</h2><ul>")
        for proposal, reason in analysis.rejected:
            body.append(f"<li><q>{_escape(proposal.text)}</q> — "
                        f"p{proposal.page}: {_escape(reason)}</li>")
        body.append("</ul></section>")

    tail = [
        "<footer>",
        "Every requirement above is quoted from the consultation file and was "
        "located on the page cited. Dates are computed, not inferred. "
        "Proposals the document did not support are listed rather than dropped.",
        "</footer></main></body></html>",
    ]
    return "\n".join(head + body + tail)
