# The five-minute video

The rules ask for at most five minutes demonstrating the working project and
pitching the problem, the audience, and why it matters. Presentation is scored
in its own right, so this is a deliverable and not an afterthought.

Run `python demo/walkthrough.py` and press Enter between shots. Every command is
the real one, run live — nothing is replayed.

## Before recording

- [ ] `python -m pytest tests/ -q` → **329 passed, none failed**. The count is a
      floor, not an equality: it grows every time a test is added, and this line
      has been stale twice already — 272 written while the suite ran 307, then
      307 while it ran 329. What matters is that nothing fails, and that the
      count has not *dropped*: a fall means collection broke, which looks exactly
      like a leaner suite.
- [ ] `.env` has a working key. Shot 2 and 4 make real API calls.
- [ ] Terminal at a size where a full row fits on one line without wrapping.
- [ ] Close anything that might notify. A Slack popup on take six is take seven.
- [ ] Both reports deleted from `out/` so they are produced on camera.

Total live runtime of the two commands is about **55 seconds**. The rest is
talking over static screens, which is where the time budget actually goes.

---

## 0:00 – 0:40 · The problem

No screen recording yet. One sentence of context, then the number.

> Public contracts in France are worth about a hundred billion euros a year. A
> bid can be thrown out before anyone reads it — not on price, not on
> technique, but because an attestation expired three days before the deadline,
> or a form was missing.

Quote the tender itself, on screen:

> « Les candidatures incomplètes ou demeurées incomplètes à la suite d'une
> demande de compléments sont éliminées. »
> — Règlement de la consultation, ANTAI, article IV.9

> The bid manager checking this has forty documents, several tenders open at
> once, and a folder nobody has re-read since the last one.

## 0:40 – 1:05 · What it does, in one breath

> You give it the buyer's consultation file and the list of papers your company
> holds. It gives you back what is missing, what expires too soon, and what a
> human needs to look at — each one quoted from the tender, with the page.

Then the sentence the whole project is built on, said slowly:

> The model reads and proposes. It never decides. Every date, every threshold,
> every verdict is computed by code.

## 1:05 – 2:05 · Scenario 1 — the finding

**Shot 1** — the test suite. Let it run to green.

> Before anything else: every verdict comes from code that runs with no model,
> no key and no network. **[read the count off the screen]** tests.
>
> (Do not memorise this number. It was written « two hundred and seventy-two »
> here while the suite ran 307, and « three hundred and seven » while it ran
> 329 — twice wrong, twice for the same reason. Read what the terminal shows;
> a figure spoken on camera cannot be corrected afterwards.)

**Shot 2** — the DGAC tender, live, about 16 seconds.

**Shot 3** — open `out/dgac.html`. Stop talking. Let them read:

```
expires too soon   Preuve d'une assurance pour les risques professionnels
                   rc_2026SDCRH05.pdf p5 → Attestation d'assurance RC pro p1 · -9 j
                   valid today, expired on the submission date
```

> Valid today. Expired on the day bids are due. Nine days.
> Nobody catches that by reading. It is a subtraction, and it costs the tender.

## 2:05 – 3:05 · Scenario 2 — at full size

**Shot 4** — the real ANTAI file, live, about 40 seconds. Talk over it.

> Ministry of the Interior. IT outsourcing and user support. Thirty-four pages.
> Bids due the 28th of October. Sixty requirements found, on camera. Forty-nine
> of them end the bid.
>
> (Say what the banner shows. The last recorded run of this file gave
> 60 obligations — 5 covered, 27 missing, 28 to review, 49 fatal to the
> candidature, 6 correctable. This line said "thirty-nine" until 2026-08-30,
> a figure that matched neither file: the DGAC run finds ten. A count spoken
> on camera cannot be corrected afterwards.)

**Shot 5** — open `out/antai.html`. Three things, in this order:

1. The turnover floor.
   > The tender requires turnover of at least a hundred and thirty-eight
   > million. This company has 2.39. Short by 135.61 million. No document
   > proves that — it is a number against a threshold, so it is arithmetic.

2. The banner.
   > Twenty-seven of these pages store part of their text as images. A mandatory
   > declaration is legible on screen and invisible to every PDF extractor
   > tested. The tool refuses to say anything is absent from a file it could not
   > read in full, and it names the pages.

3. The rejected proposal at the bottom.
   > The model proposed a requirement that is not on the page it cited. It was
   > rejected, and the report says so.

## 3:05 – 4:00 · Why it can be trusted

**Shot 6** — `docs/architecture.svg`, full screen.

> Two bands. The model proposes on top, twice. Everything else is deterministic,
> and nothing crosses from left to right without dropping into the lower band.
>
> A quote that is not on the page it cites is rejected. A document that is not
> in the library is not a match. Dates never reach the model at all.
>
> The dashed arrows are what does not get through. That is the product: not that
> it is clever, but that it cannot quietly be wrong.

One line on Strands, because criterion 1 asks how thoroughly it is used:

> Both agents are built with the Strands Agents SDK, and they have tools: read a
> page, ask whether a wording is really on it, list the library, ask whether a
> name is in it. Those are the same checks that run afterwards — so the agent
> can correct itself before it commits. But it cannot skip them: a tool it never
> calls changes nothing, because the verification runs either way.

> (This line said "the deterministic modules are the tools they call" until
> 2026-09-01, when no `@tool` existed anywhere in the repository. A judge reads
> the code. Say what the code does.)

## 4:00 – 4:40 · Who it is for, and what it changes

> This is for the person assembling the bid: a small firm without a bid office,
> a subcontractor, a first-time bidder. The buyer already has this checklist.
> The bidder does not.
>
> Getting it wrong costs a contract that was winnable on the merits. That is why
> the tool would rather say "check this" than say "covered".

Say plainly what it does not do:

> It does not write your bid, and it does not tell you that you are compliant.
> It finds the gaps and shows you where to look.

## 4:40 – 5:00 · Close

> Public bids are rejected on paperwork before anyone reads them.
> This agent finds the gaps first.

Repo URL on screen. Stop.

---

## Things not to do

**Do not read the matrix aloud row by row.** Two rows carry the argument; the
rest is texture.

**Do not apologise for the "to review" rows.** They are the point. A tool that
only says covered or missing is a tool that spends its uncertainty on covered.

**Do not speed up the live runs in post.** A judge who sees a real 40-second run
believes the rest. A jump cut in the middle of a demo invites the opposite.

**Do not claim it is finished.** Say what is measured and what is not: the
scoring grids and group cardinality are recorded in
`samples/real_requirements.json` and not built.
