"""Provider selection, tested with fabricated environments and no real key.

Every case passes an explicit `env` dict. Nothing here reads os.environ, so the
suite behaves the same on a machine with keys and one without — and a developer
running it never has their own configuration decide whether a test passes.
"""

import pytest

from pathlib import Path

from tender_compliance.model import (
    ANTHROPIC,
    OPENAI,
    Choice,
    ConfigurationError,
    available,
    choose,
)

FAKE_ANTHROPIC = {"ANTHROPIC_API_KEY": "not-a-real-key"}
FAKE_OPENAI = {"OPENAI_API_KEY": "not-a-real-key"}


class TestPickingAProvider:
    def test_an_anthropic_key_alone_selects_anthropic(self):
        assert choose(FAKE_ANTHROPIC).provider == ANTHROPIC

    def test_an_openai_key_alone_selects_openai(self):
        # The hackathon requires Strands, not a model vendor.
        choice = choose({**FAKE_OPENAI, "TENDER_MODEL": "some-model"})
        assert choice.provider == OPENAI
        assert choice.model_id == "some-model"

    def test_both_keys_follow_a_fixed_stated_order(self):
        # Arbitrary, but fixed: an implicit order is one that differs between
        # machines and makes a bug reproducible only on someone else's.
        env = {**FAKE_ANTHROPIC, **FAKE_OPENAI}
        assert choose(env).provider == ANTHROPIC
        assert available(env) == [ANTHROPIC, OPENAI]

    def test_an_explicit_choice_wins_over_the_order(self):
        env = {**FAKE_ANTHROPIC, **FAKE_OPENAI,
               "TENDER_MODEL_PROVIDER": "openai", "TENDER_MODEL": "some-model"}
        assert choose(env).provider == OPENAI

    def test_a_blank_key_does_not_count_as_present(self):
        # An empty variable in a .env file is the commonest way to get a
        # confusing failure much later, at the first API call.
        assert available({"ANTHROPIC_API_KEY": "   "}) == []


class TestWhatItSaysWhenItCannot:
    def test_no_key_at_all_names_both_variables(self):
        with pytest.raises(ConfigurationError) as error:
            choose({})
        message = str(error.value)
        assert "ANTHROPIC_API_KEY" in message
        assert "OPENAI_API_KEY" in message

    def test_asking_for_a_provider_without_its_key_says_which_one(self):
        with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
            choose({**FAKE_ANTHROPIC, "TENDER_MODEL_PROVIDER": "openai"})

    def test_an_unknown_provider_lists_the_supported_ones(self):
        with pytest.raises(ConfigurationError) as error:
            choose({**FAKE_ANTHROPIC, "TENDER_MODEL_PROVIDER": "gemini"})
        assert "anthropic" in str(error.value)
        assert "openai" in str(error.value)

    def test_openai_without_a_model_id_refuses_rather_than_guessing(self):
        # Shipping a guessed model id is the defect this project already hit
        # elsewhere: a retired model name in config, failing at the one moment
        # it is used.
        with pytest.raises(ConfigurationError, match="TENDER_MODEL"):
            choose(FAKE_OPENAI)

    def test_anthropic_has_a_known_default(self):
        assert choose(FAKE_ANTHROPIC).model_id


class TestKeysNeverLeave:
    """The rule that matters more than any of the above."""

    SECRET = "sk-ant-DO-NOT-LEAK-THIS-VALUE"

    def test_the_resolved_choice_carries_no_key(self):
        choice = choose({"ANTHROPIC_API_KEY": self.SECRET})
        assert self.SECRET not in repr(choice)
        assert self.SECRET not in choice.describe()
        assert self.SECRET not in str(vars(choice))

    def test_no_error_message_quotes_a_key(self):
        # The failure path is where secrets usually escape, because that is the
        # text people paste into issues.
        with pytest.raises(ConfigurationError) as error:
            choose({"ANTHROPIC_API_KEY": self.SECRET,
                    "TENDER_MODEL_PROVIDER": "openai"})
        assert self.SECRET not in str(error.value)

    def test_availability_reports_presence_not_value(self):
        assert available({"OPENAI_API_KEY": self.SECRET}) == [OPENAI]


class TestTlsTrust:
    """The fix for a machine whose TLS is intercepted.

    No network here: these assert the contract, not the connection. The live
    proof is in the commit message — the agent turn that failed with a bare
    "Connection error" before this and completed after.
    """

    def test_it_reports_whether_the_patch_took(self):
        from tender_compliance.model import use_system_trust
        assert isinstance(use_system_trust(), bool)

    def test_calling_it_twice_is_safe(self):
        # build() calls it on every model construction, so it has to be cheap
        # and idempotent rather than something callers must coordinate.
        from tender_compliance.model import use_system_trust
        assert use_system_trust() == use_system_trust()

    def test_verification_is_never_disabled(self):
        """An API key travels on these connections, so turning verification off
        would hand it to whoever is intercepting — the failure this function
        exists to prevent, not to cause.

        Read as syntax, not as text: the first version of this test grepped the
        file and failed on the module's own docstring, which quotes the very
        thing it forbids. A test that cannot tell code from prose is a test that
        pushes the explanation out of the code to stay green.
        """
        import ast

        source = Path(__file__).resolve().parent.parent / "tender_compliance" / "model.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.keyword):
                if node.arg in {"verify", "check_hostname"}:
                    assert not (isinstance(node.value, ast.Constant)
                                and node.value.value is False), \
                        f"{node.arg}=False disables TLS verification"
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr in {
                        "check_hostname", "verify_mode",
                    }:
                        assert not (isinstance(node.value, ast.Constant)
                                    and node.value.value is False), \
                            f"{target.attr} is being switched off"
            if isinstance(node, ast.Attribute) and node.attr == "CERT_NONE":
                raise AssertionError("ssl.CERT_NONE disables certificate checking")


class TestBuildingTheModelObject:
    """Constructing a model must not touch the network — only using it does."""

    def test_openai_is_built_from_an_explicit_model_id(self):
        from tender_compliance.model import build
        model = build(env={**FAKE_OPENAI, "TENDER_MODEL": "some-model"})
        assert "some-model" in repr(model.get_config())

    def test_anthropic_uses_its_known_default(self):
        from tender_compliance.model import build
        model = build(env=FAKE_ANTHROPIC)
        assert "claude" in repr(model.get_config())


def test_describe_is_safe_to_print_in_a_report():
    # A run should be able to state which model produced it — provenance the
    # reader needs — without that statement being a leak.
    assert Choice(provider=OPENAI, model_id="some-model").describe() == "openai:some-model"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
