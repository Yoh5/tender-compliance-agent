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


def build(choice: Choice | None = None, env: dict[str, str] | None = None):
    """Return a Strands model object for the resolved configuration.

    Imported lazily, per provider: installing one SDK should not require the
    other, and importing both to use one is a slow start for no reason.
    """
    choice = choice or choose(env)

    if choice.provider == ANTHROPIC:
        from strands.models.anthropic import AnthropicModel

        return AnthropicModel(model_id=choice.model_id, max_tokens=4096)

    from strands.models.openai import OpenAIModel

    return OpenAIModel(model_id=choice.model_id)
