"""Drive the demo one shot at a time, so recording is pressing Enter.

    python demo/walkthrough.py

Nothing here is faked or replayed: every command is the real one, run live. What
this removes is the other kind of risk — mistyping a flag on take four, or
pausing to remember which file shows which finding while the microphone is on.

The two scenarios were chosen because they show different things. DGAC is small
and carries the finding the product exists for: an insurance certificate that is
valid today and expired on the day bids are due. ANTAI is a real 34-page IT
framework from the Ministry of the Interior, and shows scale, a turnover floor of
138 million, and twenty-seven pages whose text is stored as images.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SHOTS = [
    (
        "The floor: nothing here needs a model",
        "Say: every verdict this tool prints is computed by code that runs with "
        "no model, no key and no network. Here is that code being checked.",
        [sys.executable, "-m", "pytest", "tests/", "-q"],
    ),
    (
        "Scenario 1 — the finding the product exists for",
        "Say: a small training tender. Watch the third row. Then stop talking "
        "and let them read '-9 j'.",
        [sys.executable, "-X", "utf8", "-m", "tender_compliance",
         "samples/real_dce/rc_2026SDCRH05.pdf",
         "--pages", "5-6", "--today", "2026-08-23", "--html", "out/dgac.html"],
    ),
    (
        "Open out/dgac.html",
        "Say: valid today. Expired on the day bids are due. Nine days. No human "
        "reading forty attestations catches that, and it eliminates the bid "
        "before anyone reads the offer.",
        None,
    ),
    (
        "Scenario 2 — a real one, at full size",
        "Say: Ministry of the Interior, IT outsourcing, thirty-four pages, bids "
        "due the 28th of October. This is live.",
        [sys.executable, "-X", "utf8", "-m", "tender_compliance",
         "samples/real_dce/rc_ANTAI_2026.pdf",
         "--deadline", "2026-10-28", "--today", "2026-08-23",
         "--html", "out/antai.html"],
    ),
    (
        "Open out/antai.html",
        "Say three things, in this order: the turnover floor — 2.39 million "
        "against 138 million required, short by 135.61 — then the banner saying "
        "twenty-seven pages are stored as images and cannot be read, then the "
        "rejected proposal at the bottom. The tool says what it could not do.",
        None,
    ),
    (
        "Why you can trust it",
        "Say: the model proposes twice and decides nothing. Every quote is "
        "checked against the page it cites; every document against the library; "
        "every date is arithmetic. Show docs/architecture.svg.",
        None,
    ),
]


def main() -> int:
    for number, (title, note, command) in enumerate(SHOTS, start=1):
        print(f"\n{'─' * 72}\n  SHOT {number}/{len(SHOTS)}  {title}\n{'─' * 72}")
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
            subprocess.run(command, cwd=ROOT)
    print("\n  Done. Both reports are in out/.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
