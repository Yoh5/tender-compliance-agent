# The video

## What the rules actually require

Read once, then work from the plan below.

- **Five minutes maximum.** A ceiling, not a target.
- **"Slides, screen recordings, and voiceover are all acceptable — you do not
  need to appear on camera."** A short deck in front of the demonstration is
  explicitly allowed, not a liberty being taken.
- The video must demonstrate the working project and pitch **the problem, who it
  is for, and why it matters**.
- Public on YouTube or Vimeo.

Judging is **five equally weighted criteria**: technical implementation
(thoroughness with Strands), design, potential impact, creativity and
originality, presentation. Presentation is a fifth of the score in its own
right, which is why this file exists.

Track: **Professional Agents**.

---

## Before recording

- [ ] `python -m pytest tests/ -q` → **none failed**. No number is written here
      on purpose: this line has been stale three times — 272 while the suite ran
      307, 307 while it ran 332, 332 while it ran 380. What matters is that
      nothing fails, and that the count has not *dropped* between your dry run
      and your take: a fall means collection broke, which looks exactly like a
      leaner suite.
- [ ] `.env` has a working key. Two shots make real API calls.
- [ ] `out/` is empty, so the report is produced on camera.
- [ ] **The four-document run is done BEFORE recording**, not during it.
      It is shot 1 of `python demo/walkthrough.py`, so it is the same
      command every time and never improvised on camera; press `s` to skip
      it on a second rehearsal. Three minutes of API calls is not something
      to sit through while recording. It writes into `out/batch/`, which
      leaves `out/` empty for the live run, and its closing summary is the
      one screen that says what all four documents gave back — keep it
      somewhere you can cut to in beat 7.
- [ ] Terminal at a size where a full row fits on one line without wrapping.
- [ ] Close anything that might notify. A Slack popup on take six is take seven.
- [ ] `docs/deck.pptx` open, or exported to PDF. **Eleven slides, one per beat
      below, and nothing else.** Beat 6 is a marked placeholder — cut that slide
      in the edit; it exists so the running order survives rehearsal. Every
      spoken line is in the presenter notes of its slide, and both run commands
      are in beat 6's. Rebuild with `python scripts/make_deck.py` if a figure
      changes.

**Timings measured on 2026-09-03/04.** They depend on the model, the file and
the connection, so time your own dry run rather than trusting these:

| Command | Runtime | What it gives |
|---|---|---|
| DGAC, `--pages 5-6` | 17-19 s | the insurance certificate, `-9 d` |
| European Parliament pack | 35 s | 39 requirements, 8 covered, 31 fatal |
| ANTAI, full file | 52 s | 34 pages, 27 of them partly images |
| EFSA pack | 13 s | small, and bilingual |
| `samples/real_dce --html-dir out/batch` | ~3 min | all four, one report each |

**Be ready to re-run.** On 2026-09-01 an ANTAI run failed mid-flight on an API
error and the second attempt succeeded. Have the command ready to fire again
rather than freezing on camera.

---

# The plan

Eleven beats, about **4:40**, which leaves margin under the ceiling. The two
live runs are 52 s of that total and you talk over both, so they are not dead
time.

## 1 · Introduction — 20 s · slide

Who you are, what you built, in two sentences. No suspense: say what the thing
is before explaining why it should exist.

> This is a compliance agent for public tenders. You give it the buyer's
> consultation file and the list of papers your company holds, and it tells you
> what is missing, what expires too soon, and what a human still has to look at.

## 2 · The problem — 35 s · slide

> Public contracts in France alone are worth about a hundred billion euros a
> year. A bid can be thrown out before anyone reads it — not on price, not on
> technique, but because an attestation expired three days before the deadline
> or a form was missing.

Put the tender's own words on screen. It is the strongest slide in the deck
because it is not your claim:

> « Les candidatures incomplètes ou demeurées incomplètes à la suite d'une
> demande de compléments sont éliminées. »
> — Règlement de la consultation, ANTAI, article IV.9

> The buyer has that checklist. The bidder does not. A small firm without a bid
> office is assembling forty documents across several open tenders, from a
> folder nobody has re-read since the last one.

## 3 · What kind of agent this is — 20 s · slide

> This is a **Professional Agent**. It does one job inside somebody's working
> day: the person assembling a bid, before they submit it.
>
> It is not an assistant and it does not chat. It reads a document, checks
> claims against it, and produces a compliance matrix — the same artefact a bid
> manager would build by hand over an afternoon, if they had one.

Say the governing rule here, slowly, because everything after it is a proof of
it:

> **The model observes. The code decides.**

## 4 · What it does — 20 s · slide

Four verdicts, because they call for four different actions:

| | |
|---|---|
| **covered** | a document in your library answers it |
| **missing** | nothing does |
| **expires too soon** | it answers today and not on the submission date |
| **to review** | a human has to look |

And two counts rather than one:

> An incomplete *candidature* is eliminated. An irregular *offre* may be invited
> to correct itself. The same missing paper ends the bid in one case and is
> recoverable in the other, so the report counts them separately.

## 5 · The documents — 25 s · show the folder

Open `samples/real_dce/` on screen. Four files, and say plainly what they are:

> These are real consultation files, published by public buyers, downloadable by
> anyone. Two French — the ANTAI, thirty-four pages, and a smaller one from the
> DGAC. Two English — the European Parliament and EFSA, from the EU tendering
> portal.
>
> The evidence library is fabricated, and the repository says so. Publishing
> which of a real company's certificates have lapsed is not something a
> demonstration gets to do.

That last sentence buys more credibility than anything else in the video. Say
it.

## 6 · The demonstration — 65 s · live, in both languages

**Run 1 — DGAC, French.** 17 s. Talk over it, then open `out/dgac.html` and stop
talking:

```
expires too soon   Preuve d'une assurance pour les risques professionnels ;
                   EN Proof of professional liability insurance
                   -9 d → valid today, expired on the submission date
```

> Valid today. Expired on the day bids are due. Nine days. **Nobody catches that
> by reading. It is a subtraction, and it costs the tender.**

One sentence on the English line, since the judges are the ones reading it:

> The requirement stays in French because the tender is French, and the code
> checks the quotation against the page it cites. The English sits beside it,
> never instead of it.

**Run 2 — European Parliament, English.** 35 s.

> Same tool, a tender written in English. **[read the banner]** requirements.
> And notice what is *not* on the screen: no translation lines anywhere. The
> tool worked out that this document does not need any.

## 7 · What it found — 25 s

Cut to the closing summary of shot 1, the four-document run you did before
recording, and read it off the screen. **Do not memorise a number.** The counts move on
every run, and this repository has spoken a stale one five times.

One sentence on why that block exists at all:

> One command, four consultation files, four separate matrices. Nothing is
> pooled — four tenders have four deadlines, and a combined total would
> describe no tender that exists.

Then the point only a real document could have produced:

> The EFSA pack is supposedly English. Its first run returned four requirements
> — three English, and one that begins « La Déclaration sur l'honneur relative à
> l'exclusion ». French, inside an English pack. That is why the language is
> decided per requirement and not per file, and it was found on the first run of
> a real document rather than designed in advance.

If ANTAI is in your take, its finding goes here:

> Twenty-seven of its thirty-four pages store part of their text as images. A
> mandatory declaration is legible on screen and invisible to every PDF
> extractor tested. So the tool refuses to say anything is absent from a file it
> could not read in full, and it names the pages to open by hand.

## 8 · How it works — 35 s · `docs/architecture.svg` full screen

> Two bands. The model proposes on top, twice — the obligations in the text,
> then which document might answer each one. It decides nothing. Everything
> below is deterministic, and nothing crosses from left to right without
> dropping into the lower band.
>
> A quote that is not on the page it cites is rejected, with a reason. A
> document that is not in the library, verbatim, is not a match. Dates and
> thresholds are arithmetic and never reach the model at all.

Then Strands, because criterion 1 asks how thoroughly it is used:

> Both agents are built with the Strands Agents SDK, and both are given tools:
> read a page, check whether a wording really appears on it, list the library,
> ask whether a name is in it. They are the same checks that run afterwards — so
> the agent can correct a citation before it commits to one. **But it cannot
> skip them: a tool it never calls changes nothing, because the verification
> runs either way.**

And the line that shows the discipline is real rather than claimed:

> The English translation is the one thing on the page a model wrote and nothing
> verified — **so it is the one thing that decides nothing.**

## 9 · Who it is for — 20 s · slide

> The person assembling the bid: a small firm without a bid office, a
> subcontractor, a first-time bidder. The buyer already has this checklist. The
> bidder does not.
>
> Getting it wrong costs a contract that was winnable on the merits. That is why
> the tool would rather say "check this" than say "covered".

Say plainly what it does not do. It reads as confidence, not as a caveat:

> It does not write your bid, and it does not tell you that you are compliant.
> It finds the gaps and shows you where to look.

## 10 · What comes next — 15 s · slide

Name what is recorded and deliberately not built. `samples/real_requirements.json`
carries each one with the sentence that revealed it:

> One requirement with several satisfaction paths. Requirements the buyer can
> obtain itself from an official register, which are legitimately absent from a
> folder. Groups of operators, where the document checklist multiplies per
> member while the capacity thresholds are assessed on the group as a whole.

## 11 · Close and URL — 10 s

> Public bids are rejected on paperwork before anyone reads them. This agent
> finds the gaps first.

    https://github.com/Yoh5/tender-compliance-agent

On screen. Stop.

---

## If you run over

Cut in this order:

1. **Beat 10**, perspectives. It is in the Devpost text and in the repository.
2. **Beat 7's ANTAI paragraph**, keeping the EFSA bilingual one. The second is
   more surprising and it costs fewer words.
3. **Beat 4's table**, folding the four verdicts into one spoken sentence.
4. **Run 2**, keeping only the DGAC run. Do this last: it is what proves the
   tool handles the judges' own language.

Never cut: the `-9 d` row, and "the model observes, the code decides". The rest
is context.

---

## Things not to do

**Do not memorise a count.** Read every figure off the screen in the take you
keep. Requirements found have moved 39 → 60 → 66 → 59 on the same file with the
same flags, and the test count has been misstated three times. A figure spoken
on camera cannot be corrected afterwards.

**Do not promise a row before you have seen it.** The ANTAI turnover floor
(138 000 000 €) appeared on 2026-09-01 and not on 2026-09-03; the European
Parliament pack states a floor of EUR 175 000 which no run has yet been observed
to surface. Search the report for the figure before planning a beat on it, and
fall back on the banner and the image-pages notice, which every run has
produced.

**Do not read the matrix aloud row by row.** Two rows carry the argument; the
rest is texture.

**Do not apologise for the "to review" rows.** They are the point. A tool that
only says covered or missing is a tool that spends its uncertainty on covered.

**Do not speed up the live runs in post.** A judge who sees a real run at its
real speed believes the rest. A jump cut in the middle of a demo invites the
opposite.

**Do not claim it is finished.** Say what is measured and what is not.
