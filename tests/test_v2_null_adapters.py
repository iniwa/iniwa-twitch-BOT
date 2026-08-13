import pytest
from dataclasses import fields

from twitchbot.adapters import (
    AdapterSet,
    AdapterUnavailableError,
    NullCredentialRegistry,
)
from twitchbot.container import Container


def test_default_containers_have_independent_inert_dependencies():
    first, second = Container(), Container()
    assert first.settings == second.settings
    assert first.settings is not second.settings
    assert first.adapters is not second.adapters
    assert first.adapters.twitch.status().available is False
    assert first.adapters.twitch.status().code == "not_configured"


def test_null_adapters_fail_explicitly():
    adapters = AdapterSet.unavailable()
    with pytest.raises(AdapterUnavailableError) as twitch:
        adapters.twitch.require()
    assert twitch.value.code == "not_configured"
    with pytest.raises(AdapterUnavailableError):
        adapters.media.require()


def test_null_credentials_allow_only_role_status_and_never_resolve():
    registry = NullCredentialRegistry()
    status = registry.status("bot")
    assert status.role == "bot"
    assert status.code == "not_configured"
    assert [field.name for field in fields(status)] == ["role", "code"]
    assert registry.status("broadcaster") == type(status)("broadcaster")
    with pytest.raises(AdapterUnavailableError):
        registry.resolve("bot")
    with pytest.raises(ValueError):
        registry.status("other")
