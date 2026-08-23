"""One-shot: add the consultation-file findings to README.md.

Kept in the repository for the same reason as record_real_sources.py — the
history of what changed the design is part of what the design is.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

ANCHOR = """**An obligation can be two words.** « DC1, DC2 » is a complete requirement. An
extractor built on sentences walks straight past it.
"""

ADDITION = """**An obligation can be two words.** « DC1, DC2 » is a complete requirement. An
extractor built on sentences walks straight past it.

## What reading the consultation files changed again

Notices are not where the requirements live. Since eForms became mandatory they
point at the *règlement de la consultation*, and that is the document a bidder
actually works from. Two were downloaded and committed under `samples/real_dce/`:

| File | Buyer | Deadline |
|---|---|---|
| `rc_ANTAI_2026.pdf` | Ministry of the Interior — ANTAI, IT outsourcing and user support | 28/10/2026 |
| `rc_2026SDCRH05.pdf` | Ministry of Transport — DGAC | 11/09/2026 |

### One of them cannot be read, and says nothing about it

Open page 13 of the ANTAI file in any viewer:

> « 2° **Une déclaration sur l'honneur** pour justifier qu'il n'entre dans aucun
> des cas mentionnés aux articles L. 2141-1 à L. 2141-5 […] »

Ask pypdf, pdfplumber or PyMuPDF for the same page and all three return:

```
2°
articles L. 2141-1 à L. 2141-5 et L. 2141-7 à L. 2141-
```

A mandatory document — no bid survives IV.9 without it — is perfectly legible
to a human and invisible to every extractor. Runs of text were rasterised into
image strips and pasted back in place: ten on that page, 261 across the file.

This is the worst possible failure for a tool of this kind. Not a wrong answer,
which someone would question, but a **confident and incomplete** one: the
checklist silently omits an obligation and reports nothing amiss.

So `extraction.py` asks a different question — *is any of this page a picture of
words* — and the answer is exact:

```
DGAC    0 image strips over 14 pages   (its one image is a letterhead)
ANTAI   261 strips over 34 pages       (10 of them on page 13)
```

Where text was hidden, the tool names the pages and **refuses to conclude that
anything is absent**. "The tender does not ask for X" and "we could not read the
part that asks for X" are different statements, and only one is safe to act on.

The first detector tried here counted glyphs drawn against characters returned.
It separated the two files cleanly, so it looked right — and it was wrong: the
glyph trace does not contain the missing words either. It was measuring section
headings and agreeing with the truth by coincidence. That is worse than failing,
because it would have held up in a demo and broken on the next file. The version
that shipped is the one whose mechanism was checked, not the one whose output
looked correct.

### And a threshold two orders of magnitude larger

> « ne retiendra que les candidats […] dont le chiffre d'affaires du dernier
> exercice disponible est supérieur ou égal à **138 000 000 euros hors taxe** »

One year rather than three, *supérieur ou égal* rather than *strictement
supérieur*. `capacity.py` needed no change — which is the point of having built
it against the first two notices before meeting this one.

### Four more gaps, recorded before writing the code that must handle them

- **Candidature and offre are two piles with different penalties.** An incomplete
  candidature is eliminated; an irregular offer may be regularised. The same
  missing paper is fatal in one and fixable in the other.
- **An obligation can be conditional** — « en cas de non-assujettissement à la
  TVA », « le cas échéant le DC4 ». Reporting those as missing for a bidder they
  do not concern is noise, and noise is how a report stops being read.
- **The buyer may already hold the proof.** Both files waive justificatifs
  obtainable free of charge from an official system.
- **A group multiplies the checklist but not the thresholds.** Every member of a
  groupement supplies the full document set, while capacity is assessed on the
  group as a whole.

All eleven gaps, with the sentence that revealed each, are in
`samples/real_requirements.json`.
"""

STATUS_OLD = """| `capacity.py` — quantified thresholds against company facts | implemented, tested |
| `tender.py` — reading a tender pack | not started |"""

STATUS_NEW = """| `capacity.py` — quantified thresholds against company facts | implemented, tested |
| `extraction.py` — reading a PDF, and knowing when it could not be read | implemented, tested |
| `tender.py` — reading a tender pack | not started |"""


def main() -> None:
    text = README.read_text(encoding="utf-8")

    replacements = [(ANCHOR, ADDITION), (STATUS_OLD, STATUS_NEW)]
    for old, _ in replacements:
        if old not in text:
            raise SystemExit(f"anchor not found:\n{old[:70]}")

    # Every anchor checked before anything is written: a half-applied edit is
    # harder to notice than one that refused outright.
    for old, new in replacements:
        text = text.replace(old, new, 1)

    README.write_text(text, encoding="utf-8")
    print("README.md updated")


if __name__ == "__main__":
    main()
