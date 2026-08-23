"""Run the test suite after any edit to the library or its tests.

The suite takes under a second, so there is no reason to defer it. The value is
not that tests exist — it is that a regression surfaces on the edit that caused
it, rather than three steps later when the cause is no longer obvious.

Silent on success. A hook that reports good news every time stops being read.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WATCHED = ("tender_compliance", "tests")


def watched(file_path: str) -> bool:
    if not file_path.endswith(".py"):
        return False
    try:
        relative = Path(file_path).resolve().relative_to(ROOT)
    except (ValueError, OSError):
        return False
    return relative.parts and relative.parts[0] in WATCHED


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool_input = event.get("tool_input") or {}
    tool_response = event.get("tool_response") or {}
    path = tool_input.get("file_path") or tool_response.get("filePath") or ""

    if not path or not watched(path):
        return 0

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--no-header", "-x"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode == 0:
        return 0

    # Tail only: the failing assertion and the summary are what matter, and a
    # full traceback dump would cost more context than the failure is worth.
    output = (result.stdout or "") + (result.stderr or "")
    tail = "\n".join(output.strip().splitlines()[-30:])

    print(json.dumps({
        "decision": "block",
        "reason": (
            f"The test suite fails after editing {Path(path).name}. Fix this "
            f"before doing anything else — it was passing before the edit.\n\n{tail}"
        ),
    }))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # A broken hook must never block work. Failing open here is the right
        # trade: the tests are also run explicitly, so this is a safety net and
        # not the only line of defence.
        sys.exit(0)
