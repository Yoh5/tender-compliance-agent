# Samples

## What is real here, and what is not

**The tender packs are real.** They are public documents, published by public
buyers on BOAMP and TED, and downloadable by anyone. Reading them is the point:
a tool that only works on documents written for it proves nothing.

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
