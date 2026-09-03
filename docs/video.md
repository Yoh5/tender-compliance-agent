# The five-minute video

The rules ask for at most five minutes demonstrating the working project and
pitching the problem, the audience, and why it matters. Presentation is scored
in its own right, so this is a deliverable and not an afterthought.

Run `python demo/walkthrough.py` and press Enter between shots. Every command is
the real one, run live — nothing is replayed.

## Before recording

- [ ] `python -m pytest tests/ -q` → **332 passed, none failed**. The count is a
      floor, not an equality: it grows every time a test is added, and this line
      has been stale twice already — 272 written while the suite ran 307, then
      307 while it ran 332. What matters is that nothing fails, and that the
      count has not *dropped*: a fall means collection broke, which looks exactly
      like a leaner suite.
- [ ] `.env` has a working key. Shot 2 and 4 make real API calls.
- [ ] The English gloss under each requirement costs one extra call per 20 rows
      and about 2 s on the DGAC file. `--no-gloss` turns it off if a take needs
      to be shorter — but it is what makes the rows legible to the judges, so
      leave it on.
- [ ] Terminal at a size where a full row fits on one line without wrapping.
- [ ] Close anything that might notify. A Slack popup on take six is take seven.
- [ ] Both reports deleted from `out/` so they are produced on camera.

Total live runtime of the two commands is about **a minute**. The rest is
talking over static screens, which is where the time budget actually goes.

- [ ] **Time your own dry run before the take.** DGAC: 15 s on 2026-09-01,
      17 s on 2026-09-03. ANTAI: 52 s on 2026-09-03 (not timed on 09-01; the
      "85 seconds" once written in `devpost.md` was never reproduced). The
      figure depends on the model, the file and the connection — budget the
      silence from your own dry run, not from this file.
- [ ] **Be ready to re-run the ANTAI command.** On 2026-09-01 the first attempt
      failed mid-flight on an API error and the second succeeded. Two chances in
      two runs is not a reliability claim; it is a reason to have the command
      ready to fire again rather than to freeze on camera.

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
> 332 — twice wrong, twice for the same reason. Read what the terminal shows;
> a figure spoken on camera cannot be corrected afterwards.)

**Shot 2** — the DGAC tender, live. 15 s on 2026-09-01.

**Shot 3** — open `out/dgac.html`. Stop talking. Let them read:

```
expires too soon   Preuve d'une assurance pour les risques professionnels ;
                   rc_2026SDCRH05.pdf p5 · → Attestation d'assurance responsabilité
                   civile professionnelle p1 · -9 j
                   valid today, expired on the submission date
```

(Copied from the run of 2026-09-01. The document name here is the library's full
one — this block said "Attestation d'assurance RC pro", which is not what the
report prints.)

> Valid today. Expired on the day bids are due. Nine days.
> Nobody catches that by reading. It is a subtraction, and it costs the tender.

## 2:05 – 3:05 · Scenario 2 — at full size

**Shot 4** — the real ANTAI file, live. Talk over it; time it in your dry
run rather than trusting a number written here.

> Ministry of the Interior. IT outsourcing and user support. Thirty-four pages.
> Bids due the 28th of October. **[read the banner]** requirements found, on
> camera. **[read the banner]** of them end the bid.
>
> **Do not memorise these two numbers. They move on every run.**
>
> Four recorded runs of this same file, same flags: 39 (wrong, and matching no
> file at all), then 60 — 5 covered, 27 missing, 28 to review, 49 fatal, 6
> correctable — then 66 on 2026-09-01 — 8 covered, 33 missing, 1 expired, 24 to
> review, 51 fatal, 7 correctable — then **59 on 2026-09-03 — 6 covered, 35
> missing, 1 expired, 17 to review, 46 fatal, 7 correctable**. It goes down as
> readily as up. The model is not deterministic, so the count is a property of
> the take, not of the file. Read the banner that is on screen in the take you
> keep.
>
> The small file moves too: DGAC gave 9 obligations on 2026-09-01 and 18 on
> 2026-09-03. What did not move across every run is the row the video is built
> on — the insurance certificate, `-9 j`.

**Shot 5** — open `out/antai.html`. Three things, in this order:

1. The turnover floor. **Check it is in the report before you plan on it.**
   > The tender requires turnover of at least a hundred and thirty-eight
   > million. This company has 2.39. Short by 135.61 million. No document
   > proves that — it is a number against a threshold, so it is arithmetic.

   The requirement is real and it is article IV.7, page 13: « ne retiendra que
   les candidats […] dont le chiffre d'affaires du dernier exercice disponible
   est supérieur ou égal à 138 000 000 euros hors taxe ». But **the run of
   2026-09-03 did not surface it** — it proposed the weaker line on the same
   page, « Chiffre d'affaires global pour chacun des 3 derniers exercices »,
   which carries no number and so triggers no arithmetic. Page 13 is one of the
   pages whose text is partly stored as images, and IV.7's sentence reaches the
   model with its subject missing.

   So: after the live run, search the page for `138`. If the row is there, this
   is the strongest beat in the video and it leads. If it is not, drop it and
   run the other two — they are in every recorded run — rather than describing
   something that is not on screen.

2. The banner.
   > Twenty-seven of these pages store part of their text as images. A mandatory
   > declaration is legible on screen and invisible to every PDF extractor
   > tested. The tool refuses to say anything is absent from a file it could not
   > read in full, and it names the pages.

3. A "to review" row, and the reason it carries.
   > This one is not a document to go and find — it is a form to fill in for
   > this tender. An evidence library cannot answer it, and reporting it missing
   > would be noise. So it says review, and it says why.

   **This beat replaced "the rejected proposal at the bottom", and the reason
   matters.** All three runs of 2026-09-01 and 2026-09-03 produced **zero**
   rejections — the report
   still knows how to show them (`report.py`), there were simply none. That is
   consistent with the agent's new `quote_is_on_page` tool doing its job:
   checking a wording against the page before committing to it, rather than
   being corrected afterwards.

   Two runs are not proof of that, and the honest version is that we cannot
   attribute it yet. What is certain is that **you cannot point at a section
   that is not on screen.** If the take you keep does show a rejection, use the
   old beat — it is the stronger one.

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

One sentence about the English lines under each requirement — it is worth
saying out loud, because it is the same argument as everything else:

> Every row quotes the tender in French, because the tender is French and the
> code checks that the quotation is really on the page it cites. You cannot
> check a translation against a French document. So the English line sits
> *beside* the quotation and never instead of it — it is written after every
> verdict already exists, by a call with no tools, and if it fails to arrive
> the report is exactly the same report. It is the one thing on the page the
> model wrote and nothing verified, so it is the one thing that decides
> nothing.

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

**Do not speed up the live runs in post.** A judge who sees a real run at its
real speed believes the rest. A jump cut in the middle of a demo invites the opposite.

**Do not claim it is finished.** Say what is measured and what is not: the
scoring grids and group cardinality are recorded in
`samples/real_requirements.json` and not built.
