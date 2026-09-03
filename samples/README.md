# Samples

## What is real here, and what is not

**The tender packs are real.** They are public documents, published by public
buyers on BOAMP and TED, and downloadable by anyone. Reading them is the point:
a tool that only works on documents written for it proves nothing.

### `real_dce/` — four consultation files, committed on purpose

The repository otherwise refuses to hold PDFs (`.gitignore`), because tender
packs and evidence libraries belong to real firms. These four are the exception
and the exception is narrow: they are *buyers'* own consultation rules, published
by public authorities and downloadable by anyone without registration.

They are committed because the tests make claims about them that a reader should
be able to check for themselves — that page 13 of `rc_ANTAI_2026.pdf` names a
mandatory document which no text extractor returns, and that the language
counter never reads one language for the other. A test asserting that against a
file nobody can open is just an assertion.

| File | Buyer | Role |
|---|---|---|
| `rc_ANTAI_2026.pdf` | ANTAI (FR) | the finding: 261 runs of text stored as images |
| `rc_2026SDCRH05.pdf` | DGAC (FR) | the negative control: 14 pages, nothing hidden |
| `itt_EP_COMM_2026.pdf` | European Parliament | English prose at length: 16 pages, a EUR 175 000 turnover floor, SME thresholds |
| `itt_EFSA_2023.pdf` | EFSA | the short English pack: 5 pages, and the one line the counter gets wrong |

The negative controls matter as much as the findings. Without a file that must
*not* be flagged, the image-detector's thresholds would be numbers chosen by
taste — and without a file already written in English, nothing would catch the
day the tool starts printing every requirement twice, once as itself and once as
its own translation.

`itt_EFSA_2023.pdf` earns its place on a single flaw. Its last page carries a
digital signature — `C = IT O = EFSA OU = ASSESS` — which the language counter
reads as French, on « ou » and « de ». It is the only sentence over 80
characters in either English pack that it gets wrong, the test says so by
number, and it is left wrong on purpose: no requirement is written as a
distinguished name, and the cost of the error is one redundant line.

**Neither English pack is only English.** The first live run of
`itt_EFSA_2023.pdf` returned four requirements: three in English, which carried
no translation, and one stating « La Déclaration sur l'honneur relative à
l'exclusion (section A) et aux critères de sélection (section B) » — French,
inside a pack whose every other page is English, which carried one. That is why
the language is decided per requirement and not per file. The case was not
constructed for the test; it was found on the first run of a real document.

**Provenance and reuse.** The two French files are published by the French State
on BOAMP/TED. The two English files come from the EU Funding & Tenders portal:
`EP-COMM/2026/OP/0016` (European Parliament, DG Communication — *Monitoring and
analysis services of the Spanish media*) and `OC/EFSA/PREV/2023/03` (European
Food Safety Authority — *Estimates of food consumption in bees*). Both are
© European Union; reuse is authorised under Commission Decision 2011/833/EU,
which requires the source to be acknowledged — this paragraph is that
acknowledgement.

**The evidence library is fabricated.** `evidence_library.json` describes
*Exemple Numérique SAS*, a company that does not exist, holding certificates
that do not exist. No real firm's attestations, insurance policies or
certifications appear anywhere in this repository.

This is stated plainly because the alternative is worse. A demonstration built
on a real company's compliance file would publish, in a public repository,
which of that company's certificates have lapsed — and a reader who later
discovered an undisclosed fabrication would be right to doubt everything else
in the report.

## Why fabricating it is also the better engineering choice

The interesting cases are rare in any single real library, and they are exactly
the ones the tool must be shown catching. Authoring the library means the
demonstration is **deterministic**: the certificate that expires nine days
before the deadline expires nine days before the deadline every time it is run,
on any machine, in front of anyone.

`tests/test_library.py` asserts that each verdict actually fires against this
file. The fixture *is* the demonstration, so it is tested like code — change a
date and the test names which case you broke.

## The dates are relative to one deadline

`reference_deadline` in the file is the submission date every date was chosen
against. It currently sits at **2026-10-09**.

When a real tender is picked, its actual deadline replaces this one and the
library is regenerated around it. Nothing here is meant to survive that
untouched — the file is a fixture, not a record.

## What each document is there to prove

| Document | Verdict it produces | Why it matters |
|---|---|---|
| Attestation d'assurance RC professionnelle | **expires before the deadline** | Valid today, expired on submission day. The case no human reader catches. |
| Attestation de vigilance URSSAF | **too old** | Perfectly valid, and refused anyway — the buyer wants one under 6 months. |
| Certificat ISO/IEC 27001 | **expired** | Lapsed last month, in a folder nobody re-reads. |
| Label ExpertCyber | **unknown** | Carries an expiry that could not be read. Not a pass. |
| The rest | **valid** | A matrix of nothing but problems is as useless as one with none. |
| `_deliberately_absent` | **missing** | Requirements this company simply cannot answer. |
