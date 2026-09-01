# Devpost submission text

Paste each section into the matching field on the submission form. Every figure
here was measured, not estimated — `docs/video.md` tells the same story out loud.

---

## Tagline

Public bids are rejected on paperwork before anyone reads them. This agent finds
the gaps first.

---

## Inspiration

French public buyers spend around a hundred billion euros a year. A bid can be
thrown out before a single page of it is read — not on price, not on technique,
but because an attestation expired three days before the deadline or a form was
missing. The tender says so itself:

> « Les candidatures incomplètes ou demeurées incomplètes à la suite d'une
> demande de compléments sont éliminées. »
> — Règlement de la consultation, ANTAI, article IV.9

The buyer has that checklist. The bidder does not. A small firm without a bid
office is assembling forty documents across several open tenders, from a folder
nobody has re-read since the last one.

What made this worth building was a specific failure: **an insurance certificate
that is valid today and expired on the day bids are due.** Nobody catches that by
reading. It is a subtraction.

## What it does

You give it the buyer's consultation file (a PDF) and a description of the papers
your company holds. It returns a compliance matrix: every requirement, quoted
from the tender with its page, and what answers it — or what does not.

Four verdicts, because they call for four different actions: **covered**,
**missing**, **expires too soon**, **needs review**. And two counts rather than
one, because the piles are not alike — an incomplete *candidature* is eliminated
(ANTAI IV.9), while an irregular *offre* may be invited to correct itself (DGAC
6.2). The same missing paper ends the bid in one and is recoverable in the other.

On a live run against the real 34-page Ministry of the Interior file: **66
requirements found, 51 fatal to the candidature, 7 correctable** — 8 covered, 33
missing, 1 expired before the deadline, 24 sent for review.

Those counts are from the run of 2026-09-01 and they move: the same file, same
flags, gave 60 requirements a week earlier. The model is not deterministic, and
this is the honest version of that. What does not move is what the counts are
made of — every row is quoted from the tender with its page, and every verdict
is computed.

It also answers the requirements no document can. Article IV.7 of that tender
demands turnover of at least **138 000 000 €**. No paper proves a revenue figure —
it is a number against a threshold, so it is arithmetic:

    2,39 M€ against 138,00 M€ required — short by 135,61 M€

And where the buyer grades rather than merely admits — « si x est strictement
supérieur à 3 124 998 d'euros HT : **2/2** » — the report says what a threshold
earns, or what missing it costs. A bidder can be perfectly admissible and still
lose on points.

## How I built it

Two Strands agents, and a rule that shapes everything else:

**The model observes. The code decides.**

The model proposes twice — the obligations in the text, then which document might
answer each one. It decides nothing. Every proposal is checked before it may
continue:

- a quoted requirement must actually be **on the page it cites**, or it is
  rejected with a reason;
- a proposed document must be **in the evidence library, verbatim**, or it is not
  a match;
- dates and thresholds are **arithmetic** and never reach the model at all.

Both agents are built with the Strands Agents SDK, and the checks above are also
given to them **as Strands tools**: read a page, ask whether a wording really
appears on it, list the evidence library, ask whether a name is in it. They are
the same functions the pipeline applies afterwards, so the agent can correct a
citation before it commits to one.

What the tools deliberately are not is the enforcement. A tool the model never
calls, or calls and ignores, changes nothing: every proposal is still verified
afterwards, and a quotation that fails is still rejected. **No tool returns a
verdict, a date comparison or a score** — a test asserts that over the module's
own source, because the next tool anyone adds will be added in a hurry.

That is also why **332 tests run with no model, no key and no network** — the
part that must never be wrong is pure.

The matrix validates itself before printing. A row marked covered that cites no
evidence is not a formatting problem; it is the tool asserting what it cannot
show, so the run raises instead of returning.

## Challenges I ran into

**Four live runs each broke the design**, and that is the part I would keep.

*A tender whose text is a picture of words.* Page 13 of the ANTAI file reads
« 2° **Une déclaration sur l'honneur** pour justifier qu'il n'entre dans aucun
des cas mentionnés aux articles L. 2141-1… ». pypdf, pdfplumber and PyMuPDF all
return `2°` followed by a fragment. Runs of text were rasterised into image
strips — **261 across 34 pages, 10 on page 13 alone**. A mandatory document, without
which the bid is eliminated, is legible to a human and invisible to every
extractor tested. So the tool refuses to conclude that anything is *absent* from
a file it could not read in full, and names the 27 pages to open by hand.

*My first detector for that was wrong and looked right.* It counted glyphs drawn
against characters returned, separated the two files cleanly, and was measuring
section headings — agreeing with the truth by coincidence. It would have held up
in a demo and broken on the next file.

*Anchoring by vocabulary fooled itself.* « Une déclaration sur l'honneur […] aux
articles L. 2141-1 » is absent from that page's text, yet 72% of its words are
present, because these documents reuse the same forty words throughout. Matching
on consecutive **word pairs** scores it 0.26 while every true quotation scores
1.00.

*The model said no and reported yes.* Told to return nothing when the library has
no answer, it returned the closest document and explained, in its own words, that
it did not answer — « Le Kbis n'est pas un DUME distinct », attached to a row
marked covered. The judgement is now a field it must fill in, and only an
explicit yes counts.

*Nine rows said MISSING for a company with nothing to look for.* A déclaration
sur l'honneur, a DC1, a DUME are **written for the tender**, not held in a folder.
An evidence library cannot contain them, and reporting them missing is the noise
that makes a reader stop trusting the gaps that are real.

## Accomplishments that I'm proud of

**It refuses to be confidently wrong.** Everything it cannot show, it says: pages
it could not read, proposals the document did not support, near misses named
rather than hidden.

**The prompt-injection surface is treated as real.** A consultation file is
written by someone else and handed to a language model — white six-point text in
a margin reaches the model and never reaches the reader. Injection cannot make
this tool *assert* anything false (every claim is verified), but it can make it
*miss* something, and an omission leaves no artefact to check. So such text is
reported, never stripped: sanitising would hide that someone tried. **Zero false
positives across 111 000 characters of genuine French tender prose.**

**It is honest about cost.** The pipeline made 49 calls carrying 148 000
characters; the brief and the whole catalogue were re-sent for every obligation,
forty times. Measured, then batched: **17 calls, evidence phase down 74%.**

## What I learned

Reading real documents is not a nice-to-have — it is the only thing that found
the actual problems. Nine design gaps came out of two published tenders, and not
one was visible from the specification, because the specification had been
written by someone imagining how buyers write.

And a test that cannot fail is worse than no test. Three of mine could not:
one grepped for a string that its own docstring contained, one checked for leaked
values among variables that were missing by definition, one stripped the very UI
line it was meant to inspect. All three were caught by deliberately reintroducing
the defect — which is now how every rule here gets verified.

## What's next for Tender Compliance Agent

Four gaps are recorded in `samples/real_requirements.json`, each with the sentence
that revealed it, and deliberately not built:

- one obligation with several satisfaction paths (« ou, à défaut… Ou PARTIE IV C
  1b) du DUME ») — matching the alternatives, not just flagging them;
- requirements the buyer can obtain itself from an official system, which are
  legitimately absent from a folder;
- a *groupement*, where the document checklist multiplies per member while the
  capacity thresholds are assessed on the group as a whole;
- a single requirement demanding two figures — global turnover *and* the share
  relating to the subject of the contract.

## What it deliberately does not do

It does not write your bid, and it does not tell you that you are compliant. It
finds the gaps and shows you where to look. The evidence library in this
repository is **fabricated and says so** — publishing which of a real company's
certificates have lapsed is not something a demonstration gets to do. The two
consultation files are real, public, and committed so the claims can be checked.

---

## Built with

`python` · `strands-agents` · `openai` · `anthropic` · `pymupdf` · `pytest`

## Try it out

    git clone https://github.com/Yoh5/tender-compliance-agent
    python -m pip install -r requirements.txt
    python -m pytest tests/ -q          # 307 tests, no key, no network

    cp .env.example .env                # add ONE model key
    python -m tender_compliance samples/real_dce/rc_ANTAI_2026.pdf \
      --deadline 2026-10-28 --html out/antai.html
