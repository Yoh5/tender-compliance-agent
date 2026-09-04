"""Drive the demonstration one shot at a time, so recording is pressing Enter.

    python demo/walkthrough.py

Nothing here is faked or replayed: every command is the real one, run live. What
this removes is the other kind of risk — mistyping a flag on take four, or
pausing to remember which file shows which finding while the microphone is on.

This covers beats 5 to 8 of `docs/video.md`, the part that is a screen
recording. Beats 1 to 4 and 9 to 11 are slides and are not driven from here.

The two runs were chosen because they answer different objections. DGAC is
small, French, and carries the finding the product exists for: an insurance
certificate valid today and expired on the day bids are due. The European
Parliament pack is English, sixteen pages, and shows the same tool on a document
in the judges' own language — with no translation lines anywhere, because it
worked out that none were needed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _utf8_or_die_quietly() -> str:
    """A Windows console defaults to cp1252, and this script printed a box rule.

    `python demo/walkthrough.py` raised UnicodeEncodeError on its very first
    line — before shot one, on camera, on any machine whose code page is not
    65001. The rule is decoration; the demo is not. So: ask stdout for UTF-8,
    and if it refuses, fall back to a character cp1252 can draw rather than
    letting a horizontal line end the take.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        return "─"
    except (AttributeError, LookupError, ValueError):
        return "-"


RULE = _utf8_or_die_quietly()

CHILD_ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
"""One of the reports is French. Accents reaching a cp1252 pipe come out as `?`,
and a demo that cannot spell « responsabilité » undermines the one about reading
tenders carefully."""

SHOTS = [
    (
        "Beat 5 — the documents",
        "Show samples/real_dce/ on screen. Say: four real consultation files, "
        "published by public buyers, downloadable by anyone. Two French, two "
        "English. The evidence library is fabricated and the repository says "
        "so — publishing which of a real company's certificates have lapsed is "
        "not something a demonstration gets to do.",
        None,
    ),
    (
        "Beat 6, run 1 — DGAC, French, live",
        "Say over it: a small training tender, five and six of the "
        "consultation rules. Then stop talking and let them read '-9 d'.",
        [sys.executable, "-X", "utf8", "-m", "tender_compliance",
         "samples/real_dce/rc_2026SDCRH05.pdf",
         "--pages", "5-6", "--today", "2026-08-23", "--html", "out/dgac.html"],
    ),
    (
        "Beat 6 — open out/dgac.html",
        "Say: valid today, expired on the day bids are due, nine days. Nobody "
        "catches that by reading; it is a subtraction. Then one sentence on the "
        "EN line: the requirement stays French because the tender is French and "
        "the code checks the quotation against the page it cites — the English "
        "sits beside it, never instead of it.",
        None,
    ),
    (
        "Beat 6, run 2 — European Parliament, English, live",
        "Say over it: same tool, a tender written in English. Read the banner "
        "off the screen — do not recite a number. Then point at what is NOT "
        "there: no translation lines anywhere. The tool worked out that this "
        "document does not need any.",
        [sys.executable, "-X", "utf8", "-m", "tender_compliance",
         "samples/real_dce/itt_EP_COMM_2026.pdf", "--today", "2026-08-23"],
    ),
    (
        "Beat 7 — what it found",
        "Cut to the summary block of the four-document run you did BEFORE "
        "recording — `python -m tender_compliance samples/real_dce "
        "--html-dir out` — and read it off the screen. Say: one command, four "
        "files, four separate matrices, nothing pooled. Then say the EFSA "
        "point, which only a real document could have produced: "
        "that pack is supposedly English, and its first run returned four "
        "requirements — three English, and one beginning « La Déclaration sur "
        "l'honneur relative à l'exclusion ». French, inside an English pack. "
        "That is why the language is decided per requirement and not per file. "
        "If ANTAI is in your take, add the twenty-seven pages stored as images.",
        None,
    ),
    (
        "Beat 8 — how it works",
        "Show docs/architecture.svg full screen. Say: the model proposes twice "
        "and decides nothing. A quote not on the page it cites is rejected; a "
        "document not in the library is not a match; dates are arithmetic and "
        "never reach the model. Then Strands: both agents get tools — read a "
        "page, check a wording, list the library — and they are the same checks "
        "that run afterwards, so a tool the agent never calls changes nothing.",
        None,
    ),
]


def main() -> int:
    for number, (title, note, command) in enumerate(SHOTS, start=1):
        print(f"\n{RULE * 72}\n  SHOT {number}/{len(SHOTS)}  {title}\n{RULE * 72}")
        print(f"  {note}\n")
        if command:
            print(f"  $ {' '.join(command)}\n")
        try:
            input("  [Enter] to run this shot, Ctrl-C to stop ")
        except (KeyboardInterrupt, EOFError):
            print("\nstopped")
            return 0
        if command:
            print()
            subprocess.run(command, cwd=ROOT, env=CHILD_ENV)
    print("\n  Done. out/dgac.html is the one report to open on camera.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
