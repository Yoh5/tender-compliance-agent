"""Which model answers, chosen from the environment.

The hackathon requires the Strands Agents SDK. It does not require a model
provider — Bedrock and AgentCore are explicitly optional — so this picks from
whichever key is present rather than forcing one.

That is not only convenience. The whole argument of this project is that the
model is a replaceable component: it proposes, and `obligations.verify` and
`evidence.resolve` decide. A design that can only run against one vendor has not
really made that separation, it has only claimed it.

KEYS ARE READ, NEVER RETURNED, NEVER LOGGED

Nothing in this module puts a key in a return value, an exception message, or a
repr. `describe()` exists so a run can state its configuration out loud without
that statement being a leak — it reports presence, never value.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

ANTHROPIC = "anthropic"
OPENAI = "openai"

_KEY_FOR = {
    ANTHROPIC: "ANTHROPIC_API_KEY",
    OPENAI: "OPENAI_API_KEY",
}

DEFAULT_MODEL = {
    ANTHROPIC: "claude-sonnet-5",
}
"""Only where the identifier is known to be current.

OpenAI is deliberately absent. Shipping a guessed model id is the defect this
project already hit once elsewhere — a retired model name sitting in config,
failing at the one moment it is used. An explicit TENDER_MODEL costs the user
ten seconds and cannot rot silently.
"""

# Preference when both keys are present. Arbitrary but fixed, and stated: an
# order decided implicitly is an order that changes between machines.
_PRECEDENCE = (ANTHROPIC, OPENAI)


class ConfigurationError(RuntimeError):
    """The environment cannot produce a usable model. Says what is missing.

    Never quotes a value — the point of the message is which variable to set,
    and a message that echoes a key is a message that ends up in a log.
    """


@dataclass(frozen=True)
class Choice:
    """The resolved configuration. Carries no secret."""

    provider: str
    model_id: str

    def describe(self) -> str:
        return f"{self.provider}:{self.model_id}"


def available(env: dict[str, str] | None = None) -> list[str]:
    """Providers whose key is present, in preference order."""
    env = os.environ if env is None else env
    return [p for p in _PRECEDENCE if env.get(_KEY_FOR[p], "").strip()]


def choose(env: dict[str, str] | None = None) -> Choice:
    """Resolve provider and model id, or say precisely what is missing."""
    env = os.environ if env is None else env

    requested = (env.get("TENDER_MODEL_PROVIDER") or "").strip().lower()
    ready = available(env)

    if requested:
        if requested not in _KEY_FOR:
            raise ConfigurationError(
                f"TENDER_MODEL_PROVIDER is {requested!r}; supported values are "
                f"{', '.join(sorted(_KEY_FOR))}"
            )
        if requested not in ready:
            raise ConfigurationError(
                f"TENDER_MODEL_PROVIDER is {requested!r} but {_KEY_FOR[requested]} "
                f"is not set"
            )
        provider = requested
    elif ready:
        provider = ready[0]
    else:
        raise ConfigurationError(
            "no model key found — set one of "
            + " or ".join(sorted(_KEY_FOR.values()))
            + " (see .env.example)"
        )

    model_id = (env.get("TENDER_MODEL") or "").strip() or DEFAULT_MODEL.get(provider, "")
    if not model_id:
        raise ConfigurationError(
            f"provider {provider!r} has no default model id — set TENDER_MODEL to the "
            f"model you want to use (a guessed default silently stops working the day "
            f"the model is retired)"
        )

    return Choice(provider=provider, model_id=model_id)


_trust_injected = False


def use_system_trust() -> bool:
    """Make every TLS client on this process trust the operating system's CAs.

    WHY THIS IS NEEDED, AND WHY IT IS NOT `verify=False`

    Both vendor SDKs speak through httpx, which verifies against certifi's
    bundle and ignores the OS trust store. On a machine behind TLS inspection —
    a corporate proxy, some antivirus products, some ISPs — the intercepting CA
    sits in the OS store and not in certifi, so every request fails with
    CERTIFICATE_VERIFY_FAILED while a browser on the same machine is fine.
    Measured on the development machine:

        httpx, certifi only          CERTIFICATE_VERIFY_FAILED
        httpx, OS trust store        401   (TLS fine; it simply had no key)

    The tempting fix is `verify=False`. It must never be used here: an API key
    travels on these connections, and turning verification off hands that key to
    whoever is doing the intercepting. Using the OS store is not a bypass — it
    trusts exactly what the machine's administrator already decided to trust,
    which is the same decision the browser makes.

    WHY A GLOBAL PATCH RATHER THAN A CLIENT WE PASS IN

    The obvious approach — hand the SDK a pre-configured httpx client — does not
    survive contact with Strands, which wraps every request in
    `async with self._get_client()` and therefore *closes* the client we gave it
    after the first call. The second call of an agent turn (tool result → final
    answer) then fails with a bare "Connection error". Patching `ssl` instead
    means each client Strands builds for itself is already correct.

    Explicit rather than an import side-effect: a module that rewrites the TLS
    stack merely by being imported is a module nobody expects to have done that.
    Idempotent, so callers need not coordinate.
    """
    global _trust_injected
    if _trust_injected:
        return True
    try:
        import truststore

        truststore.inject_into_ssl()
    except Exception:
        # No truststore, or a platform it does not support: certifi's bundle is
        # correct on any machine that is not intercepting TLS, so carry on and
        # let a genuine failure surface as itself.
        return False
    _trust_injected = True
    return True


def build(choice: Choice | None = None, env: dict[str, str] | None = None):
    """Return a Strands model object for the resolved configuration.

    Imported lazily, per provider: installing one SDK should not require the
    other, and importing both to use one is a slow start for no reason.
    """
    choice = choice or choose(env)
    use_system_trust()

    if choice.provider == ANTHROPIC:
        from strands.models.anthropic import AnthropicModel

        return AnthropicModel(model_id=choice.model_id, max_tokens=4096)

    from strands.models.openai import OpenAIModel

    return OpenAIModel(model_id=choice.model_id)
