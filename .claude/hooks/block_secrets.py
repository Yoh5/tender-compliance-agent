"""Refuse a commit that would publish a credential.

.gitignore protects `.env`. It does not protect a key pasted into a script, a
test fixture, a notebook, or a README example — which is how keys actually reach
public repositories. This reads what is *staged*, so it sees exactly what the
commit would publish.

It fails CLOSED on the scan (a match blocks) and OPEN on its own errors: a hook
that cannot run must not become a reason to skip the check by disabling it.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Each pattern is anchored on a prefix that issuers actually use, so ordinary
# prose does not trip it. The cost of a false positive is one glance; the cost
# of a false negative is a live key in a public repository, permanently.
PATTERNS = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "Anthropic API key"),
    (re.compile(r"\bsk-[A-Za-z0-9]{32,}"), "OpenAI-style API key"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"\bASIA[0-9A-Z]{16}\b"), "AWS temporary access key id"),
    (re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*\S+"), "AWS secret access key"),
    (re.compile(r"(?i)anthropic_api_key\s*[=:]\s*[^\s\"'{$]\S*"), "assigned ANTHROPIC_API_KEY"),
    (re.compile(r"(?i)\bservice_role\b[^\n]{0,40}eyJ"), "Supabase service-role key"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"), "JWT"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "private key"),
]


def staged_additions() -> list[tuple[str, str]]:
    """Return (file, added line) for every line this commit would add."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--unified=0", "--no-color"],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        return []

    additions, current = [], "?"
    for line in result.stdout.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            additions.append((current, line[1:]))
    return additions


def main() -> int:
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    findings = []
    for filename, line in staged_additions():
        for pattern, label in PATTERNS:
            if pattern.search(line):
                findings.append(f"  {filename}: {label}")
                break

    if not findings:
        return 0

    unique = sorted(set(findings))
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "This commit stages what looks like a live credential:\n\n"
                + "\n".join(unique[:10])
                + "\n\nA key pushed to a public repository is compromised the moment "
                  "it lands, and removing it from a later commit does not unpublish "
                  "it — it has to be revoked and reissued. Move the value into .env "
                  "(already gitignored) and reference it by name, then commit again."
            ),
        }
    }))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
