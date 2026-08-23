# Tender Compliance Agent

**Public bids are rejected on paperwork before anyone reads them. This agent finds the gaps first.**

Built for the [Agents for Humans](https://agentsforhumans.devpost.com) hackathon — Professional Agent track.

---

## The problem

A public tender pack runs 150 to 200 pages. Buried in it are dozens of
administrative obligations: certificates to attach, insurance minimums to meet,
turnover thresholds to prove, references to supply, forms to sign.

A bid that misses one of them is **rejected before anyone reads the offer
itself**. Not outbid — rejected. The price, the method, the team: never
evaluated. A small firm loses the tender on an insurance attestation that
expired eleven days before the submission date.

Nobody catches this by reading. The obligations are scattered across four or
five documents, they use different words for the same requirement, and the ones
that matter most — dates — are the ones a human eye is worst at checking.

## What it does

Give it a tender pack and your company's evidence library. It returns a
**compliance matrix**:

| | |
|---|---|
| **Covered** | the obligation is met, and here is the document that proves it |
| **Missing** | nothing in the library answers this |
| **Expired** | the document exists but will not be valid on the submission date |
| **Needs review** | a match was found, but it is not certain enough to assert |

Every row cites a page **on both sides** — the page of the tender pack that
states the obligation, and the page of the evidence that answers it. A claim
you cannot trace is a claim you cannot defend.

It also produces the list of documents to obtain, with the deadline each one
must beat.

## What it deliberately does not do

- **It does not decide whether to bid.** It produces evidence and gaps; the
  decision stays with a human who knows things the documents do not.
- **It does not price anything.**
- **It does not submit anything.**
- **It never asserts a capability the company cannot prove.** If a draft
  paragraph would need a claim no document backs, the claim is flagged, not
  written.

## The rule that shapes the architecture

**The model observes, the code decides.**

The language model reads documents and proposes interpretations — it is good at
that, and nothing else does it. But every consequence is computed by
deterministic code:

- **dates are never computed by the model.** Whether a certificate is valid on
  the submission date is arithmetic, and arithmetic that a model gets wrong
  looks exactly like arithmetic it gets right. See `validity.py`.
- **counts are never estimated by the model.** "31 of 47 covered" comes from
  counting, not from asking. See `coverage.py`.
- **evidence is matched with a citation or not at all.** A match that cannot
  name its page is downgraded to *needs review*, never to *covered*.

The result is a report that can be argued with. Every number can be checked by
hand, and every assertion points at the page it came from.

## Real tenders, a fabricated evidence library

**The tender packs are real** — public documents from BOAMP and TED, readable by
anyone. A tool that only works on documents written for it proves nothing.

**The evidence library is invented.** `samples/evidence_library.json` describes a
company that does not exist, holding certificates that do not exist. No real
firm's attestations appear anywhere in this repository.

Said plainly because the alternative is worse: a demonstration built on a real
company's compliance file would publish which of its certificates have lapsed,
and a reader who later discovered an undisclosed fabrication would be right to
doubt the rest of the report.

It is also the better engineering choice. The interesting cases are rare in any
one real folder and are exactly the ones the tool must be shown catching.
Authoring them makes the demonstration deterministic — the certificate that
expires nine days before the deadline does so on every machine, every time.
`tests/test_library.py` asserts each verdict still fires, so the fixture is
tested like code.

## What reading real notices changed

The design was written first, then two published notices were read — the
Ministry of Education's application-support framework and the City of Paris
datacenter contract. Both are quoted verbatim, with provenance, in
`samples/real_requirements.json`.

They broke the design in a way the specification could not have shown, because
the specification was written by someone imagining how buyers write.

**Not every obligation is answered by a document.**

> « Le candidat donne toutes les informations permettant de justifier de son
> chiffre d'affaires annuel global moyen sur les trois derniers exercices »
> — « si x est strictement supérieur à 3 124 998 d'euros HT : 2/2 »

No paper satisfies that. No expiry date decides it. It is a number against a
threshold, and the evidence matcher would have reported MISSING on a company
that meets it comfortably. Hence `capacity.py`.

**Buyers grade, they do not only admit.** `2/2` is a scoring grid: a bidder can
be admissible and still lose points. A status alone throws that away.

**One obligation, several satisfaction paths.**

> « Les prestations de services sont prouvées par des attestations du
> destinataire ou, à défaut, par une déclaration de l'opérateur économique. Ou
> PARTIE IV C 1b) du DUME. »

Three routes in one sentence. Reporting MISSING because the first is empty is
wrong, and wrong in the direction that wastes the bidder's time.

**Refusing a young company is usually not what the buyer wants.**

> « Pour les candidats dans l'impossibilité, à raison de leur création récente,
> de produire la liste de références susmentionnée, il est demandé tout autre
> moyen de preuve »

A firm with two years of accounts against a three-year window has not failed —
it falls on a different path. `capacity.py` returns *needs review* there, never
*missing*: the other error costs a bid that was winnable.

**An obligation can be two words.** « DC1, DC2 » is a complete requirement. An
extractor built on sentences walks straight past it.

## Status

Early. This repository was created for the hackathon and starts from zero.

| Module | State |
|---|---|
| `validity.py` — date arithmetic on evidence | implemented, tested |
| `coverage.py` — the compliance matrix and its counts | implemented, tested |
| `library.py` — loading a company's evidence library | implemented, tested |
| `capacity.py` — quantified thresholds against company facts | implemented, tested |
| `tender.py` — reading a tender pack | not started |
| `obligations.py` — extracting obligations | not started |
| `evidence.py` — matching evidence to obligations | not started |
| `drafting.py` — drafting from proven material only | not started |

Sector chosen for the demonstration: **French public tenders for IT services**
(CPV 72xxxxxx). Shorter packs than construction, an evidence library that can be
modelled honestly, and both date rules occur naturally — professional indemnity
insurance carries an annual expiry, while tax and social-security attestations
are demanded "less than 6 months old".

## Quickstart

```bash
python -m pip install -r requirements.txt
python -m pytest tests/ -q
```

## Licence

MIT — see [LICENSE](LICENSE).
